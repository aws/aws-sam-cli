"""SyncFlow for HttpApi"""
import logging
from typing import Dict, List, TYPE_CHECKING

from samcli.lib.sync.flows.generic_api_sync_flow import GenericApiSyncFlow
from samcli.lib.providers.provider import ResourceIdentifier, Stack
from samcli.lib.providers.exceptions import MissingLocalDefinition

# BuildContext and DeployContext will only be imported for type checking to improve performance
# since no instances of contexts will be instantiated in this class
if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext

LOG = logging.getLogger(__name__)


class HttpApiSyncFlow(GenericApiSyncFlow):
    """SyncFlow for HttpApi's"""

    def __init__(
        self,
        api_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
    ):
        """
        Parameters
        ----------
        api_identifier : str
            HttpApi resource identifier that needs to have associated HttpApi updated.
        build_context : BuildContext
            BuildContext used for build related parameters
        deploy_context : BuildContext
            DeployContext used for this deploy related parameters
        physical_id_mapping : Dict[str, str]
            Mapping between resource logical identifier and physical identifier
        stacks : List[Stack], optional
            List of stacks containing a root stack and optional nested stacks
        """
        super().__init__(
            api_identifier,
            build_context,
            deploy_context,
            physical_id_mapping,
            log_name="HttpApi " + api_identifier,
            stacks=stacks,
        )

    def set_up(self) -> None:
        super().set_up()
        self._api_client = self._boto_client("apigatewayv2")

    def sync(self) -> None:
        api_physical_id = self.get_physical_id(self._api_identifier)
        if self._definition_uri is None:
            raise MissingLocalDefinition(ResourceIdentifier(self._api_identifier), "DefinitionUri")
        if self._swagger_body:
            LOG.debug("%sTrying to import HttpAPI through client", self.log_prefix)
            response = self._api_client.reimport_api(ApiId=api_physical_id, Body=self._swagger_body.decode())
            LOG.debug("%sImport HttpApi Result: %s", self.log_prefix, response)
        else:
            LOG.debug("%sEmpty OpenApi definition, skipping the sync for %s", self.log_prefix, self._api_identifier)
