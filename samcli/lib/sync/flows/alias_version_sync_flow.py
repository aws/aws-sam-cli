"""SyncFlow for Lambda Function Alias and Version"""
import hashlib
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from samcli.lib.providers.provider import Stack
from samcli.lib.sync.sync_flow import ResourceAPICall, SyncFlow
from samcli.lib.utils.hash import str_checksum

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)


class AliasVersionSyncFlow(SyncFlow):
    """This SyncFlow is used for updating Lambda Function version and its associating Alias.
    Currently, this is created after a FunctionSyncFlow is finished.
    """

    _function_identifier: str
    _alias_name: str
    _lambda_client: Any

    def __init__(
        self,
        function_identifier: str,
        alias_name: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: Optional[List[Stack]] = None,
    ):
        """
        Parameters
        ----------
        function_identifier : str
            Function resource identifier that need to have associated Alias and Version updated.
        alias_name : str
            Alias name for the function
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
        """
        super().__init__(
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            log_name=f"Alias {alias_name} and Version of {function_identifier}",
            stacks=stacks,
        )
        self._function_identifier = function_identifier
        self._alias_name = alias_name
        self._lambda_client = None

    @property
    def sync_state_identifier(self) -> str:
        """
        Sync state is the unique identifier for each sync flow
        In sync state toml file we will store
        Key as AliasVersionSyncFlow:FunctionLogicalId:AliasName
        Value as alias version number
        """
        return self.__class__.__name__ + ":" + self._function_identifier + ":" + self._alias_name

    def set_up(self) -> None:
        super().set_up()
        self._lambda_client = self._boto_client("lambda")

    def gather_resources(self) -> None:
        pass

    def compare_local(self) -> bool:
        return False

    def compare_remote(self) -> bool:
        return False

    def sync(self) -> None:
        function_physical_id = self.get_physical_id(self._function_identifier)
        version = self._lambda_client.publish_version(FunctionName=function_physical_id).get("Version")
        self._local_sha = str_checksum(str(version), hashlib.sha256())
        LOG.debug("%sCreated new function version: %s", self.log_prefix, version)
        if version:
            self._lambda_client.update_alias(
                FunctionName=function_physical_id, Name=self._alias_name, FunctionVersion=version
            )

    def gather_dependencies(self) -> List[SyncFlow]:
        return []

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        return []

    def _equality_keys(self) -> Any:
        """Combination of function identifier and alias name can used to identify each unique SyncFlow"""
        return self._function_identifier, self._alias_name
