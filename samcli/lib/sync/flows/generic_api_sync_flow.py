"""SyncFlow interface for HttpApi and RestApi"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from samcli.lib.sync.sync_flow import SyncFlow, ResourceAPICall, get_definition_path
from samcli.lib.providers.provider import Stack, get_resource_by_id, ResourceIdentifier

# BuildContext and DeployContext will only be imported for type checking to improve performance
# since no istances of contexts will be instantiated in this class
if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext

LOG = logging.getLogger(__name__)


class GenericApiSyncFlow(SyncFlow):
    """SyncFlow interface for HttpApi and RestApi"""

    _api_client: Any
    _api_identifier: str
    _definition_uri: Optional[Path]
    _stacks: List[Stack]
    _swagger_body: Optional[bytes]

    def __init__(
        self,
        api_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        physical_id_mapping: Dict[str, str],
        log_name: str,
        stacks: List[Stack],
    ):
        """
        Parameters
        ----------
        api_identifier : str
            HttpApi resource identifier that needs to have associated Api updated.
        build_context : BuildContext
            BuildContext used for build related parameters
        deploy_context : BuildContext
            DeployContext used for this deploy related parameters
        physical_id_mapping : Dict[str, str]
            Mapping between resource logical identifier and physical identifier
        log_name: str
            Log name passed from subclasses, HttpApi or RestApi
        stacks : List[Stack], optional
            List of stacks containing a root stack and optional nested stacks
        """
        super().__init__(
            build_context,
            deploy_context,
            physical_id_mapping,
            log_name=log_name,
            stacks=stacks,
        )
        self._api_identifier = api_identifier

    def gather_resources(self) -> None:
        self._definition_uri = self._get_definition_file(self._api_identifier)
        self._swagger_body = self._process_definition_file()

    def _process_definition_file(self) -> Optional[bytes]:
        if self._definition_uri is None:
            return None
        with open(str(self._definition_uri), "rb") as swagger_file:
            swagger_body = swagger_file.read()
            return swagger_body

    def _get_definition_file(self, api_identifier: str) -> Optional[Path]:
        api_resource = get_resource_by_id(self._stacks, ResourceIdentifier(api_identifier))
        if not api_resource:
            return None
        return get_definition_path(
            api_resource,
            self._api_identifier,
            self._build_context.use_base_dir,
            self._build_context.base_dir,
            self._stacks,
        )

    def compare_remote(self) -> bool:
        return False

    def gather_dependencies(self) -> List[SyncFlow]:
        return []

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        return []

    def _equality_keys(self) -> Any:
        return self._api_identifier
