"""Base SyncFlow for Lambda Function"""
import logging
from typing import Any, Dict, List, TYPE_CHECKING, cast

from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.sync.flows.alias_version_sync_flow import AliasVersionSyncFlow
from samcli.lib.providers.provider import Function, Stack
from samcli.local.lambdafn.exceptions import FunctionNotFound

from samcli.lib.sync.sync_flow import SyncFlow

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)


class FunctionSyncFlow(SyncFlow):
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
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
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
        physical_id_mapping : Dict[str, str]
            Physical ID Mapping
        stacks : Optional[List[Stack]]
            Stacks
        """
        super().__init__(
            build_context,
            deploy_context,
            physical_id_mapping,
            log_name="Lambda Function " + function_identifier,
            stacks=stacks,
        )
        self._function_identifier = function_identifier
        self._function_provider = self._build_context.function_provider
        self._function = cast(Function, self._function_provider.functions.get(self._function_identifier))
        self._lambda_client = None
        self._lambda_waiter = None
        self._lambda_waiter_config = {"Delay": 1, "MaxAttempts": 60}

    def set_up(self) -> None:
        super().set_up()
        self._lambda_client = self._boto_client("lambda")
        self._lambda_waiter = self._lambda_client.get_waiter("function_updated")

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
                    self._physical_id_mapping,
                    self._stacks,
                )
            )
            LOG.debug("%sCreated  Alias and Version SyncFlow", self.log_prefix)

        return sync_flows

    def _equality_keys(self):
        return self._function_identifier
