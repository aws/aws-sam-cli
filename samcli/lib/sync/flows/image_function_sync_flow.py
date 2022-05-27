"""SyncFlow for Image based Lambda Functions"""
from contextlib import ExitStack
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import docker
from docker.client import DockerClient

from samcli.lib.providers.provider import Stack
from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow, wait_for_function_update_complete
from samcli.lib.package.ecr_uploader import ECRUploader

from samcli.lib.build.app_builder import ApplicationBuilder
from samcli.lib.sync.sync_flow import ApiCallTypes, ResourceAPICall

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)


class ImageFunctionSyncFlow(FunctionSyncFlow):
    _ecr_client: Any
    _docker_client: Optional[DockerClient]
    _image_name: Optional[str]

    def __init__(
        self,
        function_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        docker_client: Optional[DockerClient] = None,
    ):
        """
        Parameters
        ----------
        function_identifier : str
            Image function resource identifier that need to be synced.
        build_context : BuildContext
            BuildContext
        deploy_context : DeployContext
            DeployContext
        physical_id_mapping : Dict[str, str]
            Physical ID Mapping
        stacks : Optional[List[Stack]]
            Stacks
        docker_client : Optional[DockerClient]
            Docker client to be used for building and uploading images.
            Defaults to docker.from_env() if None is provided.
        """
        super().__init__(function_identifier, build_context, deploy_context, physical_id_mapping, stacks)
        self._ecr_client = None
        self._image_name = None
        self._docker_client = docker_client

    def set_up(self) -> None:
        super().set_up()
        self._ecr_client = self._boto_client("ecr")
        if not self._docker_client:
            self._docker_client = docker.from_env()

    def gather_resources(self) -> None:
        """Build function image and save it in self._image_name"""
        builder = ApplicationBuilder(
            self._build_context.collect_build_resources(self._function_identifier),
            self._build_context.build_dir,
            self._build_context.base_dir,
            self._build_context.cache_dir,
            cached=False,
            is_building_specific_resource=True,
            manifest_path_override=self._build_context.manifest_path_override,
            container_manager=self._build_context.container_manager,
            mode=self._build_context.mode,
        )
        self._image_name = builder.build().artifacts.get(self._function_identifier)

    def compare_remote(self) -> bool:
        return False

    def sync(self) -> None:
        if not self._image_name:
            LOG.debug("%sSkipping sync. Image name is None.", self.log_prefix)
            return
        function_physical_id = self.get_physical_id(self._function_identifier)
        # Load ECR Repo from --image-repository
        ecr_repo = self._deploy_context.image_repository

        # Load ECR Repo from --image-repositories
        if (
            not ecr_repo
            and self._deploy_context.image_repositories
            and isinstance(self._deploy_context.image_repositories, dict)
        ):
            ecr_repo = self._deploy_context.image_repositories.get(self._function_identifier)

        # Load ECR Repo directly from remote function
        if not ecr_repo:
            LOG.debug("%sGetting ECR Repo from Remote Function", self.log_prefix)
            function_result = self._lambda_client.get_function(FunctionName=function_physical_id)
            ecr_repo = function_result.get("Code", dict()).get("ImageUri", "").split(":")[0]
        ecr_uploader = ECRUploader(self._docker_client, self._ecr_client, ecr_repo, None)
        image_uri = ecr_uploader.upload(self._image_name, self._function_identifier)

        with ExitStack() as exit_stack:
            if self.has_locks():
                exit_stack.enter_context(self._get_lock_chain())

            self._lambda_client.update_function_code(FunctionName=function_physical_id, ImageUri=image_uri)

            # We need to wait for the cloud side update to finish
            # Otherwise even if the call is finished and lockchain is released
            # It is still possible that we have a race condition on cloud updating the same function
            wait_for_function_update_complete(self._lambda_client, self.get_physical_id(self._function_identifier))

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        # We need to acquire lock for both API calls since they would conflict on cloud
        # Any UPDATE_FUNCTION_CODE and UPDATE_FUNCTION_CONFIGURATION on the same function
        # Cannot take place in parallel
        return [
            ResourceAPICall(
                self._function_identifier,
                [ApiCallTypes.UPDATE_FUNCTION_CODE, ApiCallTypes.UPDATE_FUNCTION_CONFIGURATION],
            )
        ]
