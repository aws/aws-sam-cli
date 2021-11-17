"""SyncFlow for RestApi"""
import logging
from typing import Dict, List, TYPE_CHECKING, Set, cast

from boto3.session import Session
from botocore.exceptions import ClientError

from samcli.lib.sync.flows.generic_api_sync_flow import GenericApiSyncFlow
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id, get_resource_ids_by_type
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.utils.colors import Colored

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
        self._api_physical_id = self.get_physical_id(self._api_identifier)

    def set_up(self) -> None:
        super().set_up()
        self._api_client = self._boto_client("apigateway")

    def sync(self) -> None:
        if self._definition_uri is None:
            raise MissingLocalDefinition(ResourceIdentifier(self._api_identifier), "DefinitionUri")

        self._update_api()
        new_dep_id = self._create_deployment()
        stages = self._collect_stages()
        prev_dep_ids = self._update_stages(stages, new_dep_id)
        self._delete_deployments(prev_dep_ids)

    def _update_stages(self, stages: Set[str], dep_id: str) -> Set[str]:
        """Update all the relevant stages"""
        prev_dep_ids = set()
        for stage in stages:
            response_get = self._api_client.get_stage(restApiId=self._api_physical_id, stageName=stage)
            prev_dep_ids.add(response_get.get("deploymentId"))
            LOG.debug("%sTrying to update the stage %s through client", self.log_prefix, stage)
            response_upd = self._api_client.update_stage(
                restApiId=self._api_physical_id,
                stageName=stage,
                patchOperations=[{"op": "replace", "path": "/deploymentId", "value": dep_id}],
            )
            LOG.debug("%sUpdate Stage Result: %s", self.log_prefix, response_upd)
            self._api_client.flush_stage_cache(restApiId=self._api_physical_id, stageName=stage)
            self._api_client.flush_stage_authorizers_cache(restApiId=self._api_physical_id, stageName=stage)
        return prev_dep_ids

    def _delete_deployments(self, prev_dep_ids: Set[str]) -> None:
        """Delete the previous deployment"""
        for prev_dep_id in prev_dep_ids:
            LOG.debug("%sTrying to delete the previous deployment %s through client", self.log_prefix, prev_dep_id)
            try:
                response_del = self._api_client.delete_deployment(
                    restApiId=self._api_physical_id, deploymentId=prev_dep_id
                )
                LOG.debug("%sDelete Deployment Result: %s", self.log_prefix, response_del)
            except ClientError:
                LOG.warning(
                    Colored().yellow(
                        "Delete deployment for %s failed, it may be due to the it being used by another stage. \
    please check the console if you want to delete it"
                    ),
                    prev_dep_id,
                )

    def _create_deployment(self) -> str:
        """Create a deployment using the updated API and record the created deployment ID"""
        LOG.debug("%sTrying to create a deployment through client", self.log_prefix)
        response_dep = self._api_client.create_deployment(
            restApiId=self._api_physical_id, description="Created by SAM Sync"
        )
        new_dep_id = response_dep.get("id")
        LOG.debug("%sCreate Deployment Result: %s", self.log_prefix, response_dep)
        return new_dep_id

    def _update_api(self) -> None:
        """Update the API content"""
        LOG.debug("%sTrying to update RestAPI through client", self.log_prefix)
        response_put = self._api_client.put_rest_api(
            restApiId=self._api_physical_id, mode="overwrite", body=self._swagger_body
        )
        LOG.debug("%sPut RestApi Result: %s", self.log_prefix, response_put)

    def _collect_stages(self) -> Set[str]:
        """Collect all stages needed to be updated"""
        # Get the stage name associated with the previous deployment and update stage
        # Stage needs to be flushed so that new changes will be visible immediately
        api_resource = get_resource_by_id(self._stacks, ResourceIdentifier(self._api_identifier))
        stage_resources = get_resource_ids_by_type(self._stacks, "AWS::ApiGateway::Stage")

        stages = set()
        # If it is a SAM resource, get the StageName property
        if api_resource.get("Type") == "AWS::Serverless::Api":
            # The customer defined stage name
            stage_name = api_resource.get("Properties").get("StageName")
            stages.add(stage_name)

            # The Stage stage
            if stage_name != "Stage":
                response_sta = self._api_client.get_stages(restApiId=self._api_physical_id)
                for item in response_sta.get("item"):
                    if item.get("stageName") == "Stage":
                        stages.add("Stage")

        # For both SAM and ApiGateway resource, check if any refs from stage resources
        for stage_resource in stage_resources:
            # RestApiId is a required field in stage
            stage_dict = get_resource_by_id(self._stacks, stage_resource)
            rest_api_id = stage_dict.get("Properties").get("RestApiId")
            dep_id = stage_dict.get("Properties").get("DeploymentId")
            # If the stage doesn't have a deployment associated then no need to update
            if dep_id is None:
                continue
            # If the stage's deployment ID is not static and the rest API ID matchs, then update
            for item in get_resource_ids_by_type(self._stacks, "AWS::ApiGateway::Deployment"):
                if item.logical_id == dep_id:
                    if rest_api_id == self._api_identifier:
                        stages.add(stage_dict.get("Properties").get("StageName"))

        return stages
