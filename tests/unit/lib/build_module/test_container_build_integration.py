"""Tests for ECS/AgentCore container build integration across modules"""

from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock
from copy import deepcopy

from samcli.lib.build.app_builder import ApplicationBuilder
from samcli.lib.build.build_graph import ContainerBuildDefinition
from samcli.lib.package.packageable_resources import (
    AgentCoreRuntimeImageResource,
    ECSTaskDefinitionImageResource,
)
from samcli.lib.sync.sync_flow_factory import SyncFlowFactory
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resources import (
    AWS_BEDROCK_AGENTCORE_RUNTIME,
    AWS_ECS_TASK_DEFINITION,
    RESOURCES_WITH_IMAGE_COMPONENT,
)


class TestResourceConstants(TestCase):
    def test_ecs_task_definition_in_image_components(self):
        self.assertIn(AWS_ECS_TASK_DEFINITION, RESOURCES_WITH_IMAGE_COMPONENT)
        self.assertEqual(RESOURCES_WITH_IMAGE_COMPONENT[AWS_ECS_TASK_DEFINITION], ["ContainerDefinitions.Image"])

    def test_agentcore_in_image_components(self):
        self.assertIn(AWS_BEDROCK_AGENTCORE_RUNTIME, RESOURCES_WITH_IMAGE_COMPONENT)
        self.assertEqual(
            RESOURCES_WITH_IMAGE_COMPONENT[AWS_BEDROCK_AGENTCORE_RUNTIME],
            ["AgentRuntimeArtifact.ContainerConfiguration.ContainerUri"],
        )

    def test_resource_type_values(self):
        self.assertEqual(AWS_ECS_TASK_DEFINITION, "AWS::ECS::TaskDefinition")
        self.assertEqual(AWS_BEDROCK_AGENTCORE_RUNTIME, "AWS::BedrockAgentCore::Runtime")


class TestECSTaskDefinitionImageResource(TestCase):
    def test_resource_type(self):
        self.assertEqual(ECSTaskDefinitionImageResource.RESOURCE_TYPE, AWS_ECS_TASK_DEFINITION)

    def test_property_name(self):
        self.assertEqual(ECSTaskDefinitionImageResource.PROPERTY_NAME, "ContainerDefinitions.Image")

    def test_artifact_type_is_zip(self):
        # ZIP so it passes the PackageType filter (ECS has no PackageType property)
        self.assertEqual(ECSTaskDefinitionImageResource.ARTIFACT_TYPE, ZIP)


class TestAgentCoreRuntimeImageResource(TestCase):
    def test_resource_type(self):
        self.assertEqual(AgentCoreRuntimeImageResource.RESOURCE_TYPE, AWS_BEDROCK_AGENTCORE_RUNTIME)

    def test_property_name(self):
        self.assertEqual(
            AgentCoreRuntimeImageResource.PROPERTY_NAME,
            "AgentRuntimeArtifact.ContainerConfiguration.ContainerUri",
        )

    def test_artifact_type_is_zip(self):
        self.assertEqual(AgentCoreRuntimeImageResource.ARTIFACT_TYPE, ZIP)


class TestUpdateBuiltResource(TestCase):
    def test_ecs_task_definition_updates_first_container(self):
        properties = {"ContainerDefinitions": [{"Name": "web", "Image": "placeholder"}]}
        ApplicationBuilder._update_built_resource("myimage:latest", properties, AWS_ECS_TASK_DEFINITION, "/path")
        self.assertEqual(properties["ContainerDefinitions"][0]["Image"], "myimage:latest")

    def test_ecs_task_definition_empty_container_defs(self):
        properties = {"ContainerDefinitions": []}
        # Should not raise
        ApplicationBuilder._update_built_resource("myimage:latest", properties, AWS_ECS_TASK_DEFINITION, "/path")

    def test_ecs_task_definition_targets_container_by_name(self):
        properties = {
            "ContainerDefinitions": [
                {"Name": "sidecar", "Image": "sidecar:latest"},
                {"Name": "web", "Image": "placeholder"},
            ]
        }
        metadata = {"ContainerName": "web"}
        ApplicationBuilder._update_built_resource(
            "myimage:latest", properties, AWS_ECS_TASK_DEFINITION, "/path", metadata
        )
        self.assertEqual(properties["ContainerDefinitions"][0]["Image"], "sidecar:latest")  # unchanged
        self.assertEqual(properties["ContainerDefinitions"][1]["Image"], "myimage:latest")  # updated

    def test_ecs_task_definition_falls_back_to_first_without_container_name(self):
        properties = {
            "ContainerDefinitions": [
                {"Name": "web", "Image": "placeholder"},
                {"Name": "sidecar", "Image": "sidecar:latest"},
            ]
        }
        ApplicationBuilder._update_built_resource("myimage:latest", properties, AWS_ECS_TASK_DEFINITION, "/path")
        self.assertEqual(properties["ContainerDefinitions"][0]["Image"], "myimage:latest")
        self.assertEqual(properties["ContainerDefinitions"][1]["Image"], "sidecar:latest")

    def test_agentcore_updates_nested_container_uri(self):
        properties = {"AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": "placeholder"}}}
        ApplicationBuilder._update_built_resource("myimage:latest", properties, AWS_BEDROCK_AGENTCORE_RUNTIME, "/path")
        self.assertEqual(properties["AgentRuntimeArtifact"]["ContainerConfiguration"]["ContainerUri"], "myimage:latest")

    def test_agentcore_creates_nested_structure_if_missing(self):
        properties = {}
        ApplicationBuilder._update_built_resource("myimage:latest", properties, AWS_BEDROCK_AGENTCORE_RUNTIME, "/path")
        self.assertEqual(properties["AgentRuntimeArtifact"]["ContainerConfiguration"]["ContainerUri"], "myimage:latest")


class TestBuildContainerImages(TestCase):
    @patch.object(ApplicationBuilder, "_build_lambda_image", return_value="myimage:latest")
    def test_builds_all_definitions(self, mock_build):
        builder = ApplicationBuilder.__new__(ApplicationBuilder)
        builder._base_dir = "/base"
        builder._stream_writer = MagicMock()
        builder._use_buildkit = False
        builder._image_build_client = None

        defs = [
            ContainerBuildDefinition("Task1", AWS_ECS_TASK_DEFINITION, {"Dockerfile": "D", "DockerContext": "."}),
            ContainerBuildDefinition(
                "Agent1", AWS_BEDROCK_AGENTCORE_RUNTIME, {"Dockerfile": "D", "DockerContext": "."}
            ),
        ]
        result = builder.build_container_images(defs)
        self.assertEqual(len(result), 2)
        self.assertIn("Task1", result)
        self.assertIn("Agent1", result)
        self.assertEqual(mock_build.call_count, 2)

    @patch.object(ApplicationBuilder, "_build_lambda_image", return_value="img:tag")
    def test_skips_definition_without_metadata(self, mock_build):
        builder = ApplicationBuilder.__new__(ApplicationBuilder)
        builder._base_dir = "/base"
        builder._stream_writer = MagicMock()
        builder._use_buildkit = False
        builder._image_build_client = None

        defs = [ContainerBuildDefinition("Task1", AWS_ECS_TASK_DEFINITION, None)]
        result = builder.build_container_images(defs)
        self.assertEqual(len(result), 0)
        mock_build.assert_not_called()


class TestSyncFlowFactoryMapping(TestCase):
    def test_ecs_task_definition_registered(self):
        self.assertIn(AWS_ECS_TASK_DEFINITION, SyncFlowFactory.GENERATOR_MAPPING)

    def test_agentcore_registered(self):
        self.assertIn(AWS_BEDROCK_AGENTCORE_RUNTIME, SyncFlowFactory.GENERATOR_MAPPING)

    def test_ecs_and_agentcore_use_same_flow_creator(self):
        self.assertEqual(
            SyncFlowFactory.GENERATOR_MAPPING[AWS_ECS_TASK_DEFINITION],
            SyncFlowFactory.GENERATOR_MAPPING[AWS_BEDROCK_AGENTCORE_RUNTIME],
        )


class TestSyncEcrStackIncludesContainerResources(TestCase):
    @patch("samcli.lib.providers.sam_container_provider.SamContainerServiceProvider")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamFunctionProvider")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamLocalStackProvider")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.CompanionStackManager")
    def test_includes_container_services(
        self, mock_manager_cls, mock_stack_provider, mock_func_provider, mock_container_provider
    ):
        from samcli.lib.bootstrap.companion_stack.companion_stack_manager import sync_ecr_stack

        # Setup mocks
        mock_stack_provider.get_stacks.return_value = ([MagicMock()], None)

        mock_func = MagicMock()
        mock_func.packagetype = IMAGE
        mock_func.full_path = "MyFunction"
        mock_func_provider.return_value.get_all.return_value = [mock_func]

        mock_service = MagicMock()
        mock_service.full_path = "MyAgent"
        mock_container_provider.return_value.get_all.return_value = [mock_service]

        mock_manager = MagicMock()
        mock_manager.get_repository_mapping.return_value = {"MyFunction": "uri1", "MyAgent": "uri2"}
        mock_manager_cls.return_value = mock_manager

        result = sync_ecr_stack("template.yaml", "stack", "us-east-1", "bucket", "prefix", {})

        # Verify both function and container service were passed
        call_args = mock_manager.set_functions.call_args[0]
        logical_ids = call_args[0]
        self.assertIn("MyFunction", logical_ids)
        self.assertIn("MyAgent", logical_ids)


class TestECSContainerSyncFlow(TestCase):
    def test_sync_state_identifier(self):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        flow._resource_identifier = "MyTask"
        self.assertEqual(flow.sync_state_identifier, "MyTask")

    def test_equality_keys(self):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        flow._resource_identifier = "MyTask"
        self.assertEqual(flow._equality_keys(), "MyTask")

    def test_gather_dependencies_empty(self):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        self.assertEqual(flow.gather_dependencies(), [])

    def test_compare_remote_always_false(self):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        self.assertFalse(flow.compare_remote())

    @patch("samcli.lib.sync.flows.ecs_container_sync_flow.ECRUploader")
    @patch("samcli.lib.sync.flows.ecs_container_sync_flow.get_validated_container_client")
    def test_sync_pushes_image(self, mock_docker, mock_ecr_uploader_cls):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        flow._resource_identifier = "MyAgent"
        flow._log_name = "ECSContainer MyAgent"
        flow._image_name = "myimage:latest"
        flow._docker_client = None
        flow._ecr_client = None
        flow._ecs_client = None
        flow._physical_id_mapping = {}
        flow._deploy_context = MagicMock()
        flow._deploy_context.image_repository = "123.dkr.ecr.us-east-1.amazonaws.com/repo"
        flow._deploy_context.image_repositories = None

        mock_docker.return_value = MagicMock()

        flow._get_session = MagicMock()
        flow._boto_client = MagicMock()

        flow.sync()

        mock_ecr_uploader_cls.assert_called_once()
        mock_ecr_uploader_cls.return_value.upload.assert_called_once_with("myimage:latest", "MyAgent")

    def test_sync_skips_when_no_image(self):
        from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow

        flow = ECSContainerSyncFlow.__new__(ECSContainerSyncFlow)
        flow._resource_identifier = "MyAgent"
        flow._log_name = "ECSContainer MyAgent"
        flow._image_name = None
        flow._physical_id_mapping = {}
        # Should not raise
        flow.sync()
