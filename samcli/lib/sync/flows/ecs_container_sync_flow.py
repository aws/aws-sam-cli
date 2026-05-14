"""SyncFlow for ECS TaskDefinition container image resources"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from docker.client import DockerClient

from samcli.lib.build.app_builder import ApplicationBuilder, ApplicationBuildResult
from samcli.lib.build.build_graph import ContainerBuildDefinition
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_container_provider import SamContainerServiceProvider
from samcli.lib.sync.sync_flow import ApiCallTypes, ResourceAPICall, SyncFlow
from botocore.exceptions import ClientError
from samcli.local.docker.utils import get_validated_container_client

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)


class ECSContainerSyncFlow(SyncFlow):
    """SyncFlow for ECS TaskDefinition and AgentCore container image resources.

    Builds the container image, pushes to ECR, and triggers an ECS service update.
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
            (
                self._build_context.collect_build_resources(self._resource_identifier)
                if hasattr(self._build_context, "collect_build_resources")
                else self._build_context.get_resources_to_build()
            ),
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

        # Get ECR repo from deploy context
        ecr_repo = self._deploy_context.image_repository
        if (
            not ecr_repo
            and self._deploy_context.image_repositories
            and isinstance(self._deploy_context.image_repositories, dict)
        ):
            ecr_repo = self._deploy_context.image_repositories.get(self._resource_identifier)

        if not ecr_repo:
            LOG.warning(
                "%sNo ECR repository configured for %s. " "Use --image-repository or --image-repositories.",
                self.log_prefix,
                self._resource_identifier,
            )
            return

        # Push image to ECR
        ecr_uploader = ECRUploader(self._get_docker_client(), self._get_ecr_client(), ecr_repo, None)
        ecr_uploader.upload(self._image_name, self._resource_identifier)

        # Force new deployment of ECS service if one is associated
        self._force_ecs_deployment()

    def _force_ecs_deployment(self) -> None:
        """Find and force-update any ECS service using this task definition."""
        physical_id = self._physical_id_mapping.get(self._resource_identifier)
        if not physical_id:
            LOG.debug("%sNo physical ID found for %s, skipping ECS update", self.log_prefix, self._resource_identifier)
            return

        try:
            ecs_client = self._get_ecs_client()
            LOG.info("%sForcing new deployment for task definition %s", self.log_prefix, physical_id)

            response = ecs_client.describe_task_definition(taskDefinition=physical_id)
            task_def = response.get("taskDefinition", {})
            family = task_def.get("family")

            if family:
                # Paginate through all clusters
                cluster_paginator = ecs_client.get_paginator("list_clusters")
                for clusters_page in cluster_paginator.paginate():
                    for cluster_arn in clusters_page.get("clusterArns", []):
                        # Paginate through all services in this cluster
                        service_paginator = ecs_client.get_paginator("list_services")
                        for services_page in service_paginator.paginate(cluster=cluster_arn):
                            service_arns = services_page.get("serviceArns", [])
                            if not service_arns:
                                continue
                            # Batch into chunks of 10 (ECS DescribeServices limit)
                            for i in range(0, len(service_arns), 10):
                                batch = service_arns[i : i + 10]
                                try:
                                    svc_response = ecs_client.describe_services(cluster=cluster_arn, services=batch)
                                    for svc in svc_response.get("services", []):
                                        svc_task_def = svc.get("taskDefinition", "")
                                        deployed_family = svc_task_def.rsplit("/", 1)[-1].split(":", 1)[0]
                                        if deployed_family == family:
                                            ecs_client.update_service(
                                                cluster=cluster_arn,
                                                service=svc["serviceName"],
                                                forceNewDeployment=True,
                                            )
                                            LOG.info(
                                                "%sForced new deployment for service %s",
                                                self.log_prefix,
                                                svc["serviceName"],
                                            )
                                except ClientError:
                                    LOG.warning(
                                        "%sFailed to update services in %s",
                                        self.log_prefix,
                                        cluster_arn,
                                        exc_info=True,
                                    )
        except ClientError:
            LOG.warning("Failed to force ECS deployment", exc_info=True)

    def gather_dependencies(self) -> List[SyncFlow]:
        return []

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        return [
            ResourceAPICall(
                self._resource_identifier,
                [ApiCallTypes.UPDATE_FUNCTION_CODE],
            )
        ]

    def _equality_keys(self) -> Any:
        return self._resource_identifier
