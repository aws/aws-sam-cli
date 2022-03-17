"""SyncFlow for RestApi"""
import logging
from typing import Dict, List, TYPE_CHECKING, Set, cast, Optional

from botocore.exceptions import ClientError

from samcli.lib.sync.flows.generic_api_sync_flow import GenericApiSyncFlow
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id, get_resource_ids_by_type
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.resources import AWS_SERVERLESS_API, AWS_APIGATEWAY_STAGE, AWS_APIGATEWAY_DEPLOYMENT

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
        self._api_physical_id = ""

    def set_up(self) -> None:
        super().set_up()
        self._api_client = self._boto_client("apigateway")
        self._api_physical_id = self.get_physical_id(self._api_identifier)

    def sync(self) -> None:
        if self._definition_uri is None:
            raise MissingLocalDefinition(ResourceIdentifier(self._api_identifier), "DefinitionUri")

        self._update_api()
        new_dep_id = self._create_deployment()
        stages = self._collect_stages()
        prev_dep_ids = self._update_stages(stages, new_dep_id)
        self._delete_deployments(prev_dep_ids)

    def _update_api(self) -> None:
        """
        Update the API content
        """
        LOG.debug("%sTrying to update RestAPI through client", self.log_prefix)
        response_put = cast(
            Dict,
            self._api_client.put_rest_api(restApiId=self._api_physical_id, mode="overwrite", body=self._swagger_body),
        )
        LOG.debug("%sPut RestApi Result: %s", self.log_prefix, response_put)

    def _create_deployment(self) -> Optional[str]:
        """
        Create a deployment using the updated API and record the created deployment ID

        Returns
        ----------
        Optional[str]: The newly created deployment ID
        """
        LOG.debug("%sTrying to create a deployment through client", self.log_prefix)
        response_dep = cast(
            Dict, self._api_client.create_deployment(restApiId=self._api_physical_id, description="Created by SAM Sync")
        )
        new_dep_id = response_dep.get("id")
        LOG.debug("%sCreate Deployment Result: %s", self.log_prefix, response_dep)
        return new_dep_id

    def _collect_stages(self) -> Set[str]:
        """
        Collect all stages needed to be updated

        Returns
        ----------
        Set[str]: The set of stage names to be updated
        """
        # Get the stage name associated with the previous deployment and update stage
        # Stage needs to be flushed so that new changes will be visible immediately
        api_resource = get_resource_by_id(self._stacks, ResourceIdentifier(self._api_identifier))
        stage_resources = get_resource_ids_by_type(self._stacks, AWS_APIGATEWAY_STAGE)
        deployment_resources = get_resource_ids_by_type(self._stacks, AWS_APIGATEWAY_DEPLOYMENT)

        stages = set()
        # If it is a SAM resource, get the StageName property
        if api_resource:
            if api_resource.get("Type") == AWS_SERVERLESS_API:
                # The customer defined stage name
                stage_name = api_resource.get("Properties", {}).get("StageName")
                if stage_name:
                    stages.add(cast(str, stage_name))

                # The stage called "Stage"
                if stage_name != "Stage":
                    response_sta = cast(Dict, self._api_client.get_stages(restApiId=self._api_physical_id))
                    for item in response_sta.get("item"):  # type: ignore
                        if item.get("stageName") == "Stage":
                            stages.add("Stage")

        # For both SAM and ApiGateway resource, check if any refs from stage resources
        for stage_resource in stage_resources:
            # RestApiId is a required field in stage
            stage_dict = get_resource_by_id(self._stacks, stage_resource)
            if not stage_dict:
                continue
            rest_api_id = stage_dict.get("Properties", {}).get("RestApiId")
            dep_id = stage_dict.get("Properties", {}).get("DeploymentId")
            # If the stage doesn't have a deployment associated then no need to update
            if dep_id is None:
                continue
            # If the stage's deployment ID is not static and the rest API ID matchs, then update
            for deployment_resource in deployment_resources:
                if deployment_resource.resource_iac_id == dep_id and rest_api_id == self._api_identifier:
                    stages.add(cast(str, stage_dict.get("Properties", {}).get("StageName")))
                    break

        return stages

    def _update_stages(self, stages: Set[str], deployment_id: Optional[str]) -> Set[str]:
        """
        Update all the relevant stages

        Parameters
        ----------
        stages: Set[str]
            The set of stage names to be updated
        deployment_id: Optional[str]
            The newly created deployment ID to be used in the stages
        Returns
        ----------
        Set[str]: A set of previous deployment IDs to be cleaned up
        """
        prev_dep_ids = set()
        for stage in stages:
            # Collects previous deployment IDs to clean up
            response_get = cast(Dict, self._api_client.get_stage(restApiId=self._api_physical_id, stageName=stage))
            prev_dep_id = response_get.get("deploymentId")
            if prev_dep_id:
                prev_dep_ids.add(cast(str, prev_dep_id))

            # Updates the stage with newest deployment
            LOG.debug("%sTrying to update the stage %s through client", self.log_prefix, stage)
            response_upd = cast(
                Dict,
                self._api_client.update_stage(
                    restApiId=self._api_physical_id,
                    stageName=stage,
                    patchOperations=[{"op": "replace", "path": "/deploymentId", "value": deployment_id}],
                ),
            )
            LOG.debug("%sUpdate Stage Result: %s", self.log_prefix, response_upd)

            # Flushes the cache so that the changes are calleable
            self._api_client.flush_stage_cache(restApiId=self._api_physical_id, stageName=stage)
            self._api_client.flush_stage_authorizers_cache(restApiId=self._api_physical_id, stageName=stage)
        return prev_dep_ids

    def _delete_deployments(self, prev_deployment_ids: Set[str]) -> None:
        """
        Delete the previous deployment

        Parameters
        ----------
        prev_deployment_ids: Set[str]
            A set of previous deployment IDs to be cleaned up
        """
        for prev_dep_id in prev_deployment_ids:
            try:
                LOG.debug("%sTrying to delete the previous deployment %s through client", self.log_prefix, prev_dep_id)
                response_del = cast(
                    Dict, self._api_client.delete_deployment(restApiId=self._api_physical_id, deploymentId=prev_dep_id)
                )
                LOG.debug("%sDelete Deployment Result: %s", self.log_prefix, response_del)
            except ClientError:
                LOG.warning(
                    Colored().yellow(
                        "Delete deployment for %s failed, it may be due to the it being used by another stage. \
please check the console to see if you have other stages that needs to be updated."
                    ),
                    prev_dep_id,
                )
