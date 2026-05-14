"""Integration test for ECS/AgentCore container image builds"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml

from samcli.commands.build.build_context import BuildContext


class TestContainerImageBuild(TestCase):
    """Test that samdev build correctly handles ECS and AgentCore container resources."""

    template_path = str(
        Path(__file__).resolve().parents[1] / "testdata" / "buildcmd" / "container_image" / "template.yaml"
    )

    def setUp(self):
        self.build_dir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.build_dir, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def test_build_discovers_and_builds_container_resources(self):
        """Verify that sam build discovers AgentCore and ECS resources and produces built artifacts."""
        with BuildContext(
            resource_identifier=None,
            template_file=self.template_path,
            base_dir=None,
            build_dir=self.build_dir,
            cache_dir=self.cache_dir,
            cached=False,
            parallel=False,
            mode=None,
        ) as ctx:
            ctx.run()

        # Verify the output template was created
        output_template = Path(self.build_dir) / "template.yaml"
        self.assertTrue(output_template.exists(), "Built template should exist")

        with open(output_template) as f:
            built_template = yaml.safe_load(f)

        resources = built_template["Resources"]

        # AgentCore: ContainerUri should be replaced with the built image tag
        agent_uri = resources["SimpleAgent"]["Properties"]["AgentRuntimeArtifact"]["ContainerConfiguration"][
            "ContainerUri"
        ]
        self.assertNotEqual(agent_uri, "placeholder")
        self.assertIn("simpleagent", agent_uri.lower())

        # ECS: The 'web' container (second one) should be updated, sidecar unchanged
        container_defs = resources["ECSTask"]["Properties"]["ContainerDefinitions"]
        self.assertEqual(container_defs[0]["Image"], "public.ecr.aws/envoy:latest")  # sidecar untouched
        self.assertNotEqual(container_defs[1]["Image"], "placeholder")  # web updated
        self.assertIn("ecstask", container_defs[1]["Image"].lower())
