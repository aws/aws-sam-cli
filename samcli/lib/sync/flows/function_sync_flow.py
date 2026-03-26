"""Base SyncFlow for Lambda Function"""

import logging
import time
from abc import ABC
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from botocore.client import BaseClient

from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.providers.provider import Function, Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.flows.alias_version_sync_flow import AliasVersionSyncFlow
from samcli.lib.sync.sync_flow import SyncFlow
from samcli.local.lambdafn.exceptions import FunctionNotFound

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)
FUNCTION_SLEEP = 1  # used to wait for lambda function last update to be successful


@dataclass
class FunctionUpdateParams:
    FunctionName: str
    ZipFile: Optional[bytes] = None
    S3Bucket: Optional[str] = None
    S3Key: Optional[str] = None
    S3ObjectVersion: Optional[str] = None
    ImageUri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v for k, v in asdict(self).items() if v is not None and v != "" and not (isinstance(v, list) and not v)
        }


class FunctionPublishTarget:
    """Constants for function version publishing options"""

    LATEST_PUBLISHED = "LATEST_PUBLISHED"


@dataclass
class FunctionPublishVersionParams:
    FunctionName: str
    CodeSha256: Optional[str] = None
    Description: Optional[str] = None
    PublishTo: str = FunctionPublishTarget.LATEST_PUBLISHED
    RevisionId: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        # Filter out None, empty strings, and empty lists
        return {
            k: v for k, v in asdict(self).items() if v is not None and v != "" and not (isinstance(v, list) and not v)
        }


class FunctionSyncFlow(SyncFlow, ABC):
    _function_identifier: str
    _function_provider: SamFunctionProvider
    _function: Function
    _lambda_client: Any
    _lambda_waiter: Any
    _lambda_waiter_config: Dict[str, Any]

    def __init__(
        self,
        function_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        application_build_result: Optional[ApplicationBuildResult],
    ):
        """
        Parameters
        ----------
        function_identifier : str
            Function resource identifier that need to be synced.
        build_context : BuildContext
            BuildContext
        deploy_context : DeployContext
            DeployContext
        sync_context: SyncContext
            SyncContext object that obtains sync information.
        physical_id_mapping : Dict[str, str]
            Physical ID Mapping
        stacks : Optional[List[Stack]]
            Stacks
        application_build_result: Optional[ApplicationBuildResult]
            Pre-build ApplicationBuildResult which can be re-used during SyncFlows
        """
        super().__init__(
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            log_name="Lambda Function " + function_identifier,
            stacks=stacks,
            application_build_result=application_build_result,
        )
        self._function_identifier = function_identifier
        self._function_provider = self._build_context.function_provider
        self._function = cast(Function, self._function_provider.get(self._function_identifier))
        self._lambda_client = None
        self._lambda_waiter = None
        self._lambda_waiter_config = {"Delay": 1, "MaxAttempts": 60}

    def set_up(self) -> None:
        super().set_up()
        self._lambda_client = self._boto_client("lambda")
        self._lambda_waiter = self._lambda_client.get_waiter("function_updated")

    @property
    def auto_publish_latest_invocable(self) -> bool:
        # Publish when a function has capacity provider configuration and publish_to_latest_published:true
        return bool(self._function.publish_to_latest_published) and bool(self._function.capacity_provider_configuration)

    @property
    def sync_state_identifier(self) -> str:
        """
        Sync state is the unique identifier for each sync flow
        In sync state toml file we will store
        Key as ZipFunctionSyncFlow:FunctionLogicalId
        Value as function ZIP hash
        """
        return self.__class__.__name__ + ":" + self._function_identifier

    def gather_dependencies(self) -> List[SyncFlow]:
        """Gathers alias and versions related to a function.
        Currently only handles serverless function AutoPublishAlias field
        since a manually created function version resource behaves statically in a stack.
        Redeploying a version resource through CFN will not create a new version.
        """
        LOG.debug("%sWaiting on Remote Function Update", self.log_prefix)
        self._lambda_waiter.wait(
            FunctionName=self.get_physical_id(self._function_identifier), WaiterConfig=self._lambda_waiter_config
        )
        LOG.debug("%sRemote Function Updated", self.log_prefix)
        sync_flows: List[SyncFlow] = list()

        function_resource = self._get_resource(self._function_identifier)
        if not function_resource:
            raise FunctionNotFound(f"Unable to find function {self._function_identifier}")

        auto_publish_alias_name = function_resource.get("Properties", dict()).get("AutoPublishAlias", None)
        if auto_publish_alias_name:
            sync_flows.append(
                AliasVersionSyncFlow(
                    self._function_identifier,
                    auto_publish_alias_name,
                    self._build_context,
                    self._deploy_context,
                    self._sync_context,
                    self._physical_id_mapping,
                    self._stacks,
                )
            )
            LOG.debug("%sCreated Alias and Version SyncFlow", self.log_prefix)

        return sync_flows

    def _equality_keys(self):
        return self._function_identifier

    def update_function_with_lock(self, update_params: FunctionUpdateParams) -> None:
        """
        Helper function to update Lambda function code with lock management

        Parameters:
            update_params: FunctionUpdateParams - Object containing function update parameters
        """
        with ExitStack() as exit_stack:
            if self.has_locks():
                exit_stack.enter_context(self._get_lock_chain())

            self._lambda_client.update_function_code(**update_params.to_dict())

            # We need to wait for the cloud side update to finish
            # Otherwise even if the call is finished and lockchain is released
            # It is still possible that we have a race condition on cloud updating the same function
            wait_for_function_update_complete(self._lambda_client, update_params.FunctionName)

    def publish_function_version_with_lock(self, publish_params: FunctionPublishVersionParams) -> None:
        """
        Publishes a new version of the Lambda function.

        Parameters
        ----------
        function_name : str
            The name or ARN of the Lambda function
        description : Optional[str]
            Description for the version

        Returns
        -------
        Dict
            Response from the publish_version API call
        """
        LOG.debug("%sPublishing new version for function %s", self.log_prefix, publish_params.FunctionName)

        with ExitStack() as exit_stack:
            if self.has_locks():
                exit_stack.enter_context(self._get_lock_chain())

            response = self._lambda_client.publish_version(**publish_params.to_dict())

            new_version = response["Version"]
            LOG.debug(
                "%sPublishing new version for function %s: %s",
                self.log_prefix,
                publish_params.FunctionName,
                new_version,
            )

            # Wait for the publish version to complete to prevent a new publishVersion call
            # before previous one completes.
            wait_for_function_update_complete(self._lambda_client, publish_params.FunctionName, new_version)


class FunctionUpdateStatus(Enum):
    """Function update return types"""

    SUCCESS = "Successful"
    FAILED = "Failed"
    IN_PROGRESS = "InProgress"


def wait_for_function_update_complete(
    lambda_client: BaseClient, physical_id: str, qualifier: Optional[str] = None
) -> None:
    """
    Checks on cloud side to wait for the function update status to be complete

    Parameters
    ----------
    lambda_client : boto.core.BaseClient
        Lambda client that performs get_function API call.
    physical_id : str
        Physical identifier of the function resource
    qualifier : str
        A string indicating a version or an alias of the function
    """
    get_function_params = (
        {"FunctionName": physical_id} if not qualifier else {"FunctionName": physical_id, "Qualifier": qualifier}
    )
    status = FunctionUpdateStatus.IN_PROGRESS.value
    while status == FunctionUpdateStatus.IN_PROGRESS.value:
        response = lambda_client.get_function(**get_function_params)  # type: ignore
        status = response.get("Configuration", {}).get("LastUpdateStatus", "")

        if status == FunctionUpdateStatus.IN_PROGRESS.value:
            time.sleep(FUNCTION_SLEEP)

    LOG.debug("Function update status on %s is now %s on cloud.", physical_id, status)
