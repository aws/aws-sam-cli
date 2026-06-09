"""Tests for ContainerBuildDefinition in build_graph.py"""

from unittest import TestCase

from samcli.lib.build.build_graph import ContainerBuildDefinition
from samcli.lib.utils.architecture import ARM64, X86_64
from samcli.lib.utils.resources import AWS_BEDROCK_AGENTCORE_RUNTIME, AWS_ECS_TASK_DEFINITION


class TestContainerBuildDefinition(TestCase):
    def test_basic_properties(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app", "DockerBuildArgs": {"ENV": "prod"}}
        cbd = ContainerBuildDefinition(
            resource_identifier="MyTask",
            resource_type=AWS_ECS_TASK_DEFINITION,
            metadata=metadata,
        )
        self.assertEqual(cbd.resource_identifier, "MyTask")
        self.assertEqual(cbd.resource_type, AWS_ECS_TASK_DEFINITION)
        self.assertEqual(cbd.dockerfile, "Dockerfile")
        self.assertEqual(cbd.docker_context, "./app")
        self.assertEqual(cbd.docker_build_args, {"ENV": "prod"})
        self.assertIsNone(cbd.docker_build_target)
        self.assertEqual(cbd.architecture, X86_64)

    def test_architecture_from_metadata(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./agent", "Architecture": "arm64"}
        cbd = ContainerBuildDefinition(
            resource_identifier="MyAgent",
            resource_type=AWS_BEDROCK_AGENTCORE_RUNTIME,
            metadata=metadata,
        )
        self.assertEqual(cbd.architecture, ARM64)

    def test_architecture_default_when_not_in_metadata(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app"}
        cbd = ContainerBuildDefinition(
            resource_identifier="MyTask",
            resource_type=AWS_ECS_TASK_DEFINITION,
            metadata=metadata,
        )
        self.assertEqual(cbd.architecture, X86_64)

    def test_docker_build_target(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app", "DockerBuildTarget": "release"}
        cbd = ContainerBuildDefinition(
            resource_identifier="MyTask",
            resource_type=AWS_ECS_TASK_DEFINITION,
            metadata=metadata,
        )
        self.assertEqual(cbd.docker_build_target, "release")

    def test_equality_same(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app"}
        cbd1 = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, metadata)
        cbd2 = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, metadata)
        self.assertEqual(cbd1, cbd2)

    def test_equality_different_resource_id(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app"}
        cbd1 = ContainerBuildDefinition("MyTask1", AWS_ECS_TASK_DEFINITION, metadata)
        cbd2 = ContainerBuildDefinition("MyTask2", AWS_ECS_TASK_DEFINITION, metadata)
        self.assertNotEqual(cbd1, cbd2)

    def test_equality_different_type(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app"}
        cbd1 = ContainerBuildDefinition("MyRes", AWS_ECS_TASK_DEFINITION, metadata)
        cbd2 = ContainerBuildDefinition("MyRes", AWS_BEDROCK_AGENTCORE_RUNTIME, metadata)
        self.assertNotEqual(cbd1, cbd2)

    def test_equality_different_metadata(self):
        cbd1 = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, {"Dockerfile": "A", "DockerContext": "."})
        cbd2 = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, {"Dockerfile": "B", "DockerContext": "."})
        self.assertNotEqual(cbd1, cbd2)

    def test_equality_not_container_build_definition(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "./app"}
        cbd = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, metadata)
        self.assertNotEqual(cbd, "not a build def")

    def test_get_resource_full_paths(self):
        cbd = ContainerBuildDefinition(
            "Stack/MyTask", AWS_ECS_TASK_DEFINITION, {"Dockerfile": "D", "DockerContext": "."}
        )
        self.assertEqual(cbd.get_resource_full_paths(), "Stack/MyTask")

    def test_str_representation(self):
        cbd = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, {"Dockerfile": "D", "DockerContext": "."})
        result = str(cbd)
        self.assertIn("ContainerBuildDefinition", result)
        self.assertIn("MyTask", result)
        self.assertIn(AWS_ECS_TASK_DEFINITION, result)

    def test_none_metadata(self):
        cbd = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, None)
        self.assertIsNone(cbd.dockerfile)
        self.assertIsNone(cbd.docker_context)
        self.assertEqual(cbd.docker_build_args, {})

    def test_strips_sam_metadata_keys(self):
        metadata = {"Dockerfile": "D", "DockerContext": ".", "SamResourceId": "should_be_removed"}
        cbd = ContainerBuildDefinition("MyTask", AWS_ECS_TASK_DEFINITION, metadata)
        self.assertNotIn("SamResourceId", cbd.metadata)
