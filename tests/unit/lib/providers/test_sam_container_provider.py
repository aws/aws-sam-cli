"""Tests for SamContainerServiceProvider"""

from unittest import TestCase
from unittest.mock import MagicMock

from samcli.lib.providers.sam_container_provider import SamContainerServiceProvider, CONTAINER_IMAGE_RESOURCE_TYPES
from samcli.lib.utils.resources import AWS_BEDROCK_AGENTCORE_RUNTIME, AWS_ECS_TASK_DEFINITION


def _make_stack(resources, stack_path=""):
    stack = MagicMock()
    stack.resources = resources
    stack.stack_path = stack_path
    return stack


class TestSamContainerServiceProvider(TestCase):
    def test_discovers_ecs_task_definition(self):
        resources = {
            "MyTask": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./app"},
                "Properties": {"ContainerDefinitions": [{"Name": "web", "Image": "placeholder"}]},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].resource_id, "MyTask")
        self.assertEqual(services[0].resource_type, AWS_ECS_TASK_DEFINITION)

    def test_discovers_agentcore_runtime(self):
        resources = {
            "MyAgent": {
                "Type": AWS_BEDROCK_AGENTCORE_RUNTIME,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./agent"},
                "Properties": {"AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": "placeholder"}}},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].resource_id, "MyAgent")
        self.assertEqual(services[0].resource_type, AWS_BEDROCK_AGENTCORE_RUNTIME)

    def test_skips_resource_without_metadata(self):
        resources = {
            "MyTask": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Properties": {"ContainerDefinitions": [{"Name": "web", "Image": "some-image"}]},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 0)

    def test_skips_resource_without_dockerfile(self):
        resources = {
            "MyTask": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Metadata": {"DockerContext": "./app"},  # Missing Dockerfile
                "Properties": {},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 0)

    def test_skips_resource_without_docker_context(self):
        resources = {
            "MyTask": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Metadata": {"Dockerfile": "Dockerfile"},  # Missing DockerContext
                "Properties": {},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 0)

    def test_skips_unsupported_resource_type(self):
        resources = {
            "MyFunction": {
                "Type": "AWS::Lambda::Function",
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./app"},
                "Properties": {},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 0)

    def test_get_by_full_path(self):
        resources = {
            "MyAgent": {
                "Type": AWS_BEDROCK_AGENTCORE_RUNTIME,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./agent"},
                "Properties": {},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        result = provider.get("MyAgent")
        self.assertIsNotNone(result)
        self.assertEqual(result.resource_id, "MyAgent")

    def test_get_returns_none_for_unknown(self):
        provider = SamContainerServiceProvider([_make_stack({})])
        self.assertIsNone(provider.get("NonExistent"))

    def test_nested_stack_full_path(self):
        resources = {
            "MyTask": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./app"},
                "Properties": {},
            }
        }
        provider = SamContainerServiceProvider([_make_stack(resources, stack_path="ChildStack")])
        services = list(provider.get_all())
        self.assertEqual(services[0].full_path, "ChildStack/MyTask")

    def test_multiple_resources(self):
        resources = {
            "Task1": {
                "Type": AWS_ECS_TASK_DEFINITION,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./app1"},
                "Properties": {},
            },
            "Agent1": {
                "Type": AWS_BEDROCK_AGENTCORE_RUNTIME,
                "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "./agent"},
                "Properties": {},
            },
        }
        provider = SamContainerServiceProvider([_make_stack(resources)])
        services = list(provider.get_all())
        self.assertEqual(len(services), 2)

    def test_container_image_resource_types_list(self):
        self.assertIn(AWS_ECS_TASK_DEFINITION, CONTAINER_IMAGE_RESOURCE_TYPES)
        self.assertIn(AWS_BEDROCK_AGENTCORE_RUNTIME, CONTAINER_IMAGE_RESOURCE_TYPES)
