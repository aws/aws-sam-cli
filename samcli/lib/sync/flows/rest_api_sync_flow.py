"""SyncFlow for RestApi"""
import logging
from typing import Dict, List, TYPE_CHECKING, cast

from boto3.session import Session

from samcli.lib.sync.flows.generic_api_sync_flow import GenericApiSyncFlow
from samcli.lib.providers.provider import ResourceIdentifier, Stack
from samcli.lib.providers.exceptions import MissingLocalDefinition

# BuildContext and DeployContext will only be imported for type checking to improve performance
# since no instances of contexts will be instantiated in this class
if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext

LOG = logging.getLogger(__name__)


class RestApiSyncFlow(GenericApiSyncFlow):
    """SyncFlow for RestApi's"""

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
            RestApi resource identifier that needs to have associated RestApi updated.
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
            log_name="RestApi " + api_identifier,
            stacks=stacks,
        )

    def set_up(self) -> None:
        super().set_up()
        self._api_client = cast(Session, self._session).client("apigateway")

    def sync(self) -> None:
        api_physical_id = self.get_physical_id(self._api_identifier)
        if self._definition_uri is None:
            raise MissingLocalDefinition(ResourceIdentifier(self._api_identifier), "DefinitionUri")
        LOG.debug("%sTrying to put RestAPI through client", self.log_prefix)
        response = self._api_client.put_rest_api(restApiId=api_physical_id, mode="overwrite", body=self._swagger_body)
        LOG.debug("%sPut RestApi Result: %s", self.log_prefix, response)
