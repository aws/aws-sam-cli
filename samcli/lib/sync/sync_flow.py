"""SyncFlow base class """
import logging

from abc import ABC, abstractmethod
from threading import Lock
from typing import Any, Dict, List, NamedTuple, Optional, TYPE_CHECKING, cast
from boto3.session import Session

from samcli.lib.providers.provider import get_resource_by_id

from samcli.lib.providers.provider import ResourceIdentifier, Stack
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.lock_distributor import LockDistributor, LockChain
from samcli.lib.sync.exceptions import MissingLockException, MissingPhysicalResourceError

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.build.build_context import BuildContext

# Logging with multiple processes is not safe. Use a log queue in the future.
# https://docs.python.org/3/howto/logging-cookbook.html#:~:text=Although%20logging%20is%20thread%2Dsafe,across%20multiple%20processes%20in%20Python.
LOG = logging.getLogger(__name__)


class ResourceAPICall(NamedTuple):
    """Named tuple for a resource and its potential API calls"""

    resource_identifier: str
    api_calls: List[str]


class SyncFlow(ABC):
    """Base class for a SyncFlow"""

    _log_name: str
    _build_context: "BuildContext"
    _deploy_context: "DeployContext"
    _stacks: Optional[List[Stack]]
    _session: Optional[Session]
    _physical_id_mapping: Dict[str, str]
    _locks: Optional[Dict[str, Lock]]

    def __init__(
        self,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        physical_id_mapping: Dict[str, str],
        log_name: str,
        stacks: Optional[List[Stack]] = None,
    ):
        """
        Parameters
        ----------
        build_context : BuildContext
            BuildContext used for build related parameters
        deploy_context : BuildContext
            DeployContext used for this deploy related parameters
        physical_id_mapping : Dict[str, str]
            Mapping between resource logical identifier and physical identifier
        log_name : str
            Name to be used for logging purposes
        stacks : List[Stack], optional
            List of stacks containing a root stack and optional nested stacks
        """
        self._build_context = build_context
        self._deploy_context = deploy_context
        self._log_name = log_name
        self._stacks = stacks
        self._session = None
        self._physical_id_mapping = physical_id_mapping
        self._locks = None

    def set_up(self) -> None:
        """Clients and other expensives setups should be handled here instead of constructor"""
        self._session = Session(profile_name=self._deploy_context.profile, region_name=self._deploy_context.region)

    def _boto_client(self, client_name: str):
        return get_boto_client_provider_from_session_with_config(cast(Session, self._session))(client_name)

    @abstractmethod
    def gather_resources(self) -> None:
        """Local operations that need to be done before comparison and syncing with remote
        Ex: Building lambda functions
        """
        raise NotImplementedError("gather_resources")

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

    def get_lock_keys(self) -> List[str]:
        """Get a list of function + API calls that can be used as keys for LockDistributor

        Returns
        -------
        List[str]
            List of keys for all resources and their API calls
        """
        lock_keys = list()
        for resource_api_calls in self._get_resource_api_calls():
            for api_call in resource_api_calls.api_calls:
                lock_keys.append(SyncFlow._get_lock_key(resource_api_calls.resource_identifier, api_call))
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
    def _get_lock_key(logical_id: str, api_call: str) -> str:
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
        return logical_id + "_" + api_call

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
        if not self.compare_remote():
            LOG.debug("%sSyncing", self.log_prefix)
            self.sync()
            LOG.debug("%sGathering Dependencies", self.log_prefix)
            dependencies = self.gather_dependencies()
        LOG.debug("%sFinished", self.log_prefix)
        return dependencies
