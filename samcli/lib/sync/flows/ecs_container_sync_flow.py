"""SyncFlow for ECS TaskDefinition container image resources"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from botocore.exceptions import ClientError
from docker.client import DockerClient

from samcli.lib.build.app_builder import ApplicationBuilder, ApplicationBuildResult
from samcli.lib.build.build_graph import ContainerBuildDefinition
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.providers.provider import ResourcesToBuildCollector, Stack
from samcli.lib.providers.sam_container_provider import SamContainerServiceProvider
from samcli.lib.sync.sync_flow import ApiCallTypes, ResourceAPICall, SyncFlow
from samcli.local.docker.utils import get_validated_container_client

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)

# ECS service ARN format: arn:aws:ecs:<region>:<account>:service/<cluster>/<name>
_ECS_SERVICE_ARN_PREFIX = "arn:aws:ecs:"
_ECS_SERVICE_ARN_SERVICE_SEGMENT = ":service/"

# Minimum number of slash-separated parts after splitting a service ARN
# e.g. arn:aws:ecs:region:account:service/cluster/name -> [..., "cluster", "name"]
_ECS_SERVICE_ARN_PARTS = 3


class ECSContainerSyncFlow(SyncFlow):
    """SyncFlow for ECS TaskDefinition container image resources.

    Builds the container image, pushes to ECR, registers a new TaskDefinition
    revision with the updated image URI, then updates any associated ECS services
    to that revision.
    """

    _resource_identifier: str
    _ecr_client: Optional[Any]
    _docker_client: Optional[DockerClient]
    _ecs_client: Optional[Any]
    _image_name: Optional[str]

    def __init__(
        self,
        resource_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
        application_build_result: Optional[ApplicationBuildResult],
    ):
        super().__init__(
            build_context,
            deploy_context,
            sync_context,
            physical_id_mapping,
            f"ECSContainer {resource_identifier}",
            stacks,
            application_build_result,
        )
        self._resource_identifier = resource_identifier
        self._ecr_client = None
        self._docker_client = None
        self._ecs_client = None
        self._image_name = None

    @property
    def sync_state_identifier(self) -> str:
        return self._resource_identifier

    def _get_docker_client(self) -> DockerClient:
        if not self._docker_client:
            self._docker_client = get_validated_container_client()
        return self._docker_client

    def _get_ecr_client(self) -> Any:
        if not self._ecr_client:
            self._ecr_client = self._boto_client("ecr")
        return self._ecr_client

    def _get_ecs_client(self) -> Any:
        if not self._ecs_client:
            self._ecs_client = self._boto_client("ecs")
        return self._ecs_client

    def gather_resources(self) -> None:
        """Build the container image."""
        if self._application_build_result:
            self._image_name = self._application_build_result.artifacts.get(self._resource_identifier)
        else:
            self._build_from_scratch()

        if self._image_name:
            docker_img = self._get_docker_client().images.get(self._image_name)
            if docker_img and docker_img.attrs.get("Id"):
                self._local_sha = str(docker_img.attrs.get("Id"))

    def _build_from_scratch(self) -> None:
        """Build the container image from scratch using the provider."""
        container_provider = SamContainerServiceProvider(self._stacks or [])
        service = container_provider.get(self._resource_identifier)
        if not service:
            LOG.warning("Cannot find container service resource '%s'", self._resource_identifier)
            return

        build_def = ContainerBuildDefinition(
            resource_identifier=service.full_path,
            resource_type=service.resource_type,
            metadata=service.metadata,
        )

        builder = ApplicationBuilder(
            ResourcesToBuildCollector(),
            self._build_context.build_dir,
            self._build_context.base_dir,
            self._build_context.cache_dir,
            cached=False,
            is_building_specific_resource=True,
            manifest_path_override=self._build_context.manifest_path_override,
            container_manager=self._build_context.container_manager,
            mode=self._build_context.mode,
            build_in_source=self._build_context.build_in_source,
        )
        artifacts = builder.build_container_images([build_def])
        self._image_name = artifacts.get(self._resource_identifier)

    def compare_remote(self) -> bool:
        return False

    def sync(self) -> None:
        if not self._image_name:
            LOG.debug("%sSkipping sync. Image name is None.", self.log_prefix)
            return

        ecr_repo = self._deploy_context.image_repository
        if (
            not ecr_repo
            and self._deploy_context.image_repositories
            and isinstance(self._deploy_context.image_repositories, dict)
        ):
            ecr_repo = self._deploy_context.image_repositories.get(self._resource_identifier)

        if not ecr_repo:
            LOG.warning(
                "%sNo ECR repository configured for %s. Use --image-repository or --image-repositories.",
                self.log_prefix,
                self._resource_identifier,
            )
            return

        ecr_uploader = ECRUploader(self._get_docker_client(), self._get_ecr_client(), ecr_repo, None)
        image_uri = ecr_uploader.upload(self._image_name, self._resource_identifier)

        new_task_def_arn = self._register_updated_task_definition(image_uri)
        if new_task_def_arn:
            self._update_services_to_task_definition(new_task_def_arn)

    def _register_updated_task_definition(self, image_uri: str) -> Optional[str]:
        """Describe the current task definition, swap the image URI, and register a new revision."""
        physical_id = self._physical_id_mapping.get(self._resource_identifier)
        if not physical_id:
            LOG.debug(
                "%sNo physical ID for %s; cannot register new task definition revision.",
                self.log_prefix,
                self._resource_identifier,
            )
            return None

        ecs_client = self._get_ecs_client()
        try:
            response = ecs_client.describe_task_definition(taskDefinition=physical_id, include=["TAGS"])
        except ClientError:
            LOG.warning(
                "%sFailed to describe task definition %s", self.log_prefix, physical_id, exc_info=True
            )
            return None

        task_def = response.get("taskDefinition", {})
        tags = response.get("tags", [])

        # Fields that are output-only and must be stripped before re-registering
        _READONLY_FIELDS = {
            "taskDefinitionArn",
            "revision",
            "status",
            "requiresAttributes",
            "compatibilities",
            "registeredAt",
            "registeredBy",
        }
        register_input = {k: v for k, v in task_def.items() if k not in _READONLY_FIELDS}

        # Update the image in the matching container definition
        container_name = self._get_container_name()
        container_defs = register_input.get("containerDefinitions", [])
        updated = False
        for cd in container_defs:
            if container_name is None or cd.get("name") == container_name:
                cd["image"] = image_uri
                updated = True
                if container_name is not None:
                    break

        if not updated:
            LOG.warning(
                "%sContainerName '%s' not found in task definition; skipping registration.",
                self.log_prefix,
                container_name,
            )
            return None

        if tags:
            register_input["tags"] = tags

        try:
            reg_response = ecs_client.register_task_definition(**register_input)
        except ClientError:
            LOG.warning("%sFailed to register new task definition revision", self.log_prefix, exc_info=True)
            return None

        new_arn = reg_response.get("taskDefinition", {}).get("taskDefinitionArn")
        LOG.info("%sRegistered new task definition revision: %s", self.log_prefix, new_arn)
        return new_arn

    def _get_container_name(self) -> Optional[str]:
        """Return ContainerName from resource metadata, if set."""
        if not self._stacks:
            return None
        provider = SamContainerServiceProvider(self._stacks)
        service = provider.get(self._resource_identifier)
        if service and isinstance(service.metadata, dict):
            return service.metadata.get("ContainerName")
        return None

    def _update_services_to_task_definition(self, task_def_arn: str) -> None:
        """Update ECS services that reference this task definition family to the new revision."""
        physical_id = self._physical_id_mapping.get(self._resource_identifier)
        if not physical_id:
            return

        ecs_client = self._get_ecs_client()
        my_family = physical_id.rsplit("/", 1)[-1].split(":", 1)[0]

        for resource_id, resource_physical_id in self._physical_id_mapping.items():
            if not resource_physical_id:
                continue
            # Only consider ECS service ARNs; skip everything else (incl. App Runner, VPC Lattice, etc.)
            if not (
                str(resource_physical_id).startswith(_ECS_SERVICE_ARN_PREFIX)
                and _ECS_SERVICE_ARN_SERVICE_SEGMENT in str(resource_physical_id)
            ):
                continue

            parts = resource_physical_id.rsplit("/", 2)
            if len(parts) < _ECS_SERVICE_ARN_PARTS:
                continue
            cluster = parts[-2]
            service_name = parts[-1]

            try:
                svc_response = ecs_client.describe_services(cluster=cluster, services=[service_name])
                for svc in svc_response.get("services", []):
                    svc_task_def = svc.get("taskDefinition", "")
                    svc_family = svc_task_def.rsplit("/", 1)[-1].split(":", 1)[0]
                    if svc_family and svc_family == my_family:
                        ecs_client.update_service(
                            cluster=cluster,
                            service=service_name,
                            taskDefinition=task_def_arn,
                        )
                        LOG.info(
                            "%sUpdated service %s to task definition %s",
                            self.log_prefix,
                            service_name,
                            task_def_arn,
                        )
            except ClientError:
                LOG.warning(
                    "%sFailed to update service %s",
                    self.log_prefix,
                    resource_id,
                    exc_info=True,
                )

    def gather_dependencies(self) -> List[SyncFlow]:
        return []

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        return [
            ResourceAPICall(
                self._resource_identifier,
                [ApiCallTypes.UPDATE_CONTAINER_IMAGE],
            )
        ]

    def _equality_keys(self) -> Any:
        return self._resource_identifier
