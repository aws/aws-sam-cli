"""SyncFlow base class """
import logging
from abc import ABC, abstractmethod
from enum import Enum
from os import environ
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Set, cast

from boto3.session import Session

from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id
from samcli.lib.sync.exceptions import MissingLockException, MissingPhysicalResourceError
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.lock_distributor import LockChain, LockDistributor
from samcli.lib.utils.resources import RESOURCES_WITH_LOCAL_PATHS

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

# Logging with multiple processes is not safe. Use a log queue in the future.
# https://docs.python.org/3/howto/logging-cookbook.html#:~:text=Although%20logging%20is%20thread%2Dsafe,across%20multiple%20processes%20in%20Python.
LOG = logging.getLogger(__name__)


def get_default_retry_config() -> Optional[Dict]:
    """
    Returns a default retry config if nothing is overriden by environment variables
    """
    if environ.get("AWS_MAX_ATTEMPTS") or environ.get("AWS_RETRY_MODE"):
        return None
    return {"max_attempts": 10, "mode": "standard"}


class ApiCallTypes(Enum):
    """API call stages that can be locked on"""

    BUILD = "Build"
    UPDATE_FUNCTION_CONFIGURATION = "UpdateFunctionConfiguration"
    UPDATE_FUNCTION_CODE = "UpdateFunctionCode"


class ResourceAPICall(NamedTuple):
    """Named tuple for a resource and its potential API calls"""

    shared_resource: str
    api_calls: List[ApiCallTypes]


class SyncFlow(ABC):
    """Base class for a SyncFlow"""

    _log_name: str
    _build_context: "BuildContext"
    _deploy_context: "DeployContext"
    _sync_context: "SyncContext"
    _stacks: Optional[List[Stack]]
    _session: Optional[Session]
    _physical_id_mapping: Dict[str, str]
    _locks: Optional[Dict[str, Lock]]
    # Local hash represents the state of a particular sync flow
    # We store the hash value in sync state toml file as value
    _local_sha: Optional[str]
    _application_build_result: Optional[ApplicationBuildResult]

    def __init__(
        self,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        log_name: str,
        stacks: Optional[List[Stack]] = None,
        application_build_result: Optional[ApplicationBuildResult] = None,
    ):
        """
        Parameters
        ----------
        build_context : BuildContext
            BuildContext used for build related parameters
        deploy_context : BuildContext
            DeployContext used for this deploy related parameters
        sync_context: SyncContext
            SyncContext object that obtains sync information.
        physical_id_mapping : Dict[str, str]
            Mapping between resource logical identifier and physical identifier
        log_name : str
            Name to be used for logging purposes
        stacks : List[Stack], optional
            List of stacks containing a root stack and optional nested stacks
         application_build_result: Optional[ApplicationBuildResult]
            Pre-build ApplicationBuildResult which can be re-used during SyncFlows
        """
        self._build_context = build_context
        self._deploy_context = deploy_context
        self._sync_context = sync_context
        self._log_name = log_name
        self._stacks = stacks
        self._session = None
        self._physical_id_mapping = physical_id_mapping
        self._locks = None
        self._local_sha = None
        self._application_build_result = application_build_result

    def set_up(self) -> None:
        """Clients and other expensives setups should be handled here instead of constructor"""
        pass

    def _get_session(self) -> Session:
        if not self._session:
            self._session = Session(profile_name=self._deploy_context.profile, region_name=self._deploy_context.region)
        return self._session

    def _boto_client(self, client_name: str):
        default_retry_config = get_default_retry_config()
        if not default_retry_config:
            LOG.debug("Creating boto client (%s) with user's retry config", client_name)
            return get_boto_client_provider_from_session_with_config(self._get_session())(client_name)

        LOG.debug("Creating boto client (%s) with default retry config", client_name)
        return get_boto_client_provider_from_session_with_config(self._get_session(), retries=default_retry_config)(
            client_name
        )

    @property
    @abstractmethod
    def sync_state_identifier(self) -> str:
        """
        Sync state is the unique identifier for each sync flow
        We store the identifier in sync state toml file as key
        """
        raise NotImplementedError("sync_state_identifier")

    @abstractmethod
    def gather_resources(self) -> None:
        """Local operations that need to be done before comparison and syncing with remote
        Ex: Building lambda functions
        """
        raise NotImplementedError("gather_resources")

    def _update_local_hash(self) -> None:
        """Updates the latest local hash of the sync flow which then can be used for comparison for next run"""
        if not self._local_sha:
            LOG.debug("%sNo local hash is configured, skipping to update local hash", self.log_prefix)
            return

        self._sync_context.update_resource_sync_state(self.sync_state_identifier, self._local_sha)

    def compare_local(self) -> bool:
        """Comparison between local resource and its local stored state.
        If the resources are identical, sync and gather dependencies will be skipped.
        Simply return False if there is no comparison needed.
        Ex: Comparing local Lambda function artifact with stored SHA256

        Returns
        -------
        bool
            Return True if current resource and cached are in sync. Skipping rest of the execution.
            Return False otherwise.
        """
        stored_sha = self._sync_context.get_resource_latest_sync_hash(self.sync_state_identifier)
        LOG.debug("%sLocal SHA: %s Stored SHA: %s", self.log_prefix, self._local_sha, stored_sha)
        if self._local_sha and stored_sha and self._local_sha == stored_sha:
            return True
        return False

    @abstractmethod
    def compare_remote(self) -> bool:
        """Comparison between local and remote resources.
        This can be used for optimization if comparison is a lot faster than sync.
        If the resources are identical, sync and gather dependencies will be skipped.
        Simply return False if there is no comparison needed.
        Ex: Comparing local Lambda function artifact with remote SHA256

        Returns
        -------
        bool
            Return True if local and remote are in sync. Skipping rest of the execution.
            Return False otherwise.
        """
        raise NotImplementedError("compare_remote")

    @abstractmethod
    def sync(self) -> None:
        """Step that syncs local resources with remote.
        Ex: Call UpdateFunctionCode for Lambda Functions
        """
        raise NotImplementedError("sync")

    @abstractmethod
    def gather_dependencies(self) -> List["SyncFlow"]:
        """Gather a list of SyncFlows that should be executed after the current change.
        This can be sync flows for other resources that depends on the current one.
        Ex: Update Lambda functions if a layer sync flow creates a new version.

        Returns
        ------
        List[SyncFlow]
            List of sync flows that need to be executed after the current one finishes.
        """
        raise NotImplementedError("update_dependencies")

    @abstractmethod
    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        """Get resources and their associating API calls. This is used for locking purposes.
        Returns
        -------
        Dict[str, List[str]]
            Key as resource logical ID
            Value as list of api calls that the resource can make
        """
        raise NotImplementedError("_get_resource_api_calls")

    def has_locks(self) -> bool:
        """Check if a sync flow has locks and needs to enter a lock context
        Returns
        -------
        bool
            whether or not a sync flow contains locks
        """
        return bool(self._locks)

    def get_lock_keys(self) -> Set[str]:
        """Get a list of function + API calls that can be used as keys for LockDistributor

        Returns
        -------
        Set[str]
            Set of keys for all resources and their API calls
        """
        lock_keys = set()
        for resource_api_calls in self._get_resource_api_calls():
            for api_call in resource_api_calls.api_calls:
                lock_keys.add(SyncFlow._get_lock_key(resource_api_calls.shared_resource, api_call))
        return lock_keys

    def set_locks_with_distributor(self, distributor: LockDistributor):
        """Set locks to be used with a LockDistributor. Keys should be generated using get_lock_keys().

        Parameters
        ----------
        distributor : LockDistributor
            Lock distributor
        """
        self.set_locks_with_dict(distributor.get_locks(self.get_lock_keys()))

    def set_locks_with_dict(self, locks: Dict[str, Lock]):
        """Set locks to be used. Keys should be generated using get_lock_keys().

        Parameters
        ----------
        locks : Dict[str, Lock]
            Dict of locks with keys from get_lock_keys()
        """
        self._locks = locks

    @staticmethod
    def _get_lock_key(logical_id: str, api_call: ApiCallTypes) -> str:
        """Get a single lock key for a pair of resource and API call.

        Parameters
        ----------
        logical_id : str
            Logical ID of a resource.
        api_call : str
            API call the resource will use.

        Returns
        -------
        str
            String key created with logical ID and API call name.
        """
        return f"{logical_id}_{api_call.value}"

    def _get_lock_chain(self) -> LockChain:
        """Return a LockChain object for all the locks

        Returns
        -------
        Optional[LockChain]
            A LockChain object containing all locks. None if there are no locks.
        """
        if self._locks:
            return LockChain(self._locks)
        raise MissingLockException("Missing Locks for LockChain")

    def _get_resource(self, resource_identifier: str) -> Optional[Dict[str, Any]]:
        """Get a resource dict with resource identifier

        Parameters
        ----------
        resource_identifier : str
            Resource identifier

        Returns
        -------
        Optional[Dict[str, Any]]
            Resource dict containing its template fields.
        """
        return get_resource_by_id(self._stacks, ResourceIdentifier(resource_identifier)) if self._stacks else None

    def get_physical_id(self, resource_identifier: str) -> str:
        """Get the physical ID of a resource using physical_id_mapping. This does not directly check with remote.

        Parameters
        ----------
        resource_identifier : str
            Resource identifier

        Returns
        -------
        str
            Resource physical ID

        Raises
        ------
        MissingPhysicalResourceError
            Resource does not exist in the physical ID mapping.
            This could mean remote and local templates are not in sync.
        """
        physical_id = self._physical_id_mapping.get(resource_identifier)
        if not physical_id:
            raise MissingPhysicalResourceError(resource_identifier)

        return physical_id

    @abstractmethod
    def _equality_keys(self) -> Any:
        """This method needs to be overridden to distinguish between multiple instances of SyncFlows
        If the return values of two instances are the same, then those two instances will be assumed to be equal.

        Returns
        -------
        Any
            Anything that can be hashed and compared with "=="
        """
        raise NotImplementedError("_equality_keys is not implemented.")

    def __hash__(self) -> int:
        return hash((type(self), self._equality_keys()))

    def __eq__(self, o: object) -> bool:
        if type(o) is not type(self):
            return False
        return cast(bool, self._equality_keys() == cast(SyncFlow, o)._equality_keys())

    @property
    def log_name(self) -> str:
        """
        Returns
        -------
        str
            Human readable name/identifier for logging purposes
        """
        return self._log_name

    @property
    def log_prefix(self) -> str:
        """
        Returns
        -------
        str
            Log prefix to be used for logging.
        """
        return f"SyncFlow [{self.log_name}]: "

    def execute(self) -> List["SyncFlow"]:
        """Execute the sync flow and returns a list of dependent sync flows.
        Skips sync() and gather_dependencies() if compare() is True

        Returns
        -------
        List[SyncFlow]
            A list of dependent sync flows
        """
        dependencies: List["SyncFlow"] = list()
        LOG.debug("%sSetting Up", self.log_prefix)
        self.set_up()
        LOG.debug("%sGathering Resources", self.log_prefix)
        self.gather_resources()
        LOG.debug("%sComparing with Remote", self.log_prefix)
        if (not self.compare_local()) and (not self.compare_remote()):
            LOG.debug("%sSyncing", self.log_prefix)
            self.sync()
            LOG.debug("%sUpdating local hash of the sync flow", self.log_prefix)
            self._update_local_hash()
            LOG.debug("%sGathering Dependencies", self.log_prefix)
            dependencies = self.gather_dependencies()
        else:
            LOG.info("%sSkipping resource update as the content didn't change", self.log_prefix)
        LOG.debug("%sFinished", self.log_prefix)
        return dependencies


def get_definition_path(
    resource: Dict, identifier: str, use_base_dir: bool, base_dir: str, stacks: List[Stack]
) -> Optional[Path]:
    """
    A helper method used by non-function sync flows to resolve definition file path
    that are relative to the child stack to absolute path for nested stacks

    Parameters
    -------
    resource: Dict
        The resource's template dict
    identifier: str
        The logical ID identifier of the resource
    use_base_dir: bool
        Whether or not the base_dir option was used
    base_dir: str
        Base directory if provided, otherwise the root template directory
    stacks: List[Stack]
        The list of stacks for the application

    Returns
    -------
    Optional[Path]
        A resolved absolute path for the definition file
    """
    definition_field_names = RESOURCES_WITH_LOCAL_PATHS.get(resource.get("Type", ""))
    if not definition_field_names:
        LOG.error("Couldn't find definition field name for resource {}", identifier)
        return None
    definition_field_name = definition_field_names[0]
    LOG.debug("Found definition field name as {}", definition_field_name)

    properties = resource.get("Properties", {})
    definition_file = properties.get(definition_field_name)
    definition_path = None
    if definition_file:
        definition_path = Path(base_dir).joinpath(definition_file)
        if not use_base_dir:
            child_stack = Stack.get_stack_by_full_path(ResourceIdentifier(identifier).stack_path, stacks)
            if child_stack:
                definition_path = Path(child_stack.location).parent.joinpath(definition_file)
    return definition_path
