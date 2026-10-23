"""Integration tests for building MicrovmImage resources."""

import logging
import os
from pathlib import Path
from unittest import skipIf

import pytest
from parameterized import parameterized_class

from samcli.local.docker.image_build_client import CLIBuildClient
from samcli.local.docker.container_client_factory import ContainerClientFactory
from samcli.local.docker.utils import get_validated_container_client
from samcli.yamlhelper import yaml_parse
from tests.testing_utils import (
    run_command,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_MESSAGE,
)
from tests.integration.buildcmd.build_integ_base import BuildIntegBase

LOG = logging.getLogger(__name__)


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
@parameterized_class(
    ("use_buildkit",),
    [
        (False,),
        (True,),
    ],
)
@pytest.mark.filterwarnings("ignore::ResourceWarning")
class TestBuildMicrovmImage(BuildIntegBase):
    """Test building MicrovmImage resources with sam build."""

    template = "template_microvm_image.yaml"

    def setUp(self):
        super().setUp()
        if self.use_buildkit:
            client = ContainerClientFactory.create_client()
            is_available, error_msg = CLIBuildClient.is_available(client.get_runtime_type())
            if not is_available:
                self.skipTest(f"Buildkit not available: {error_msg}")

    @pytest.mark.tier1
    def test_build_microvm_image_succeeds(self):
        """sam build should succeed and create a Docker image tagged <logical_id_lowercase>:latest."""
        cmdlist = self.get_command_list(use_buildkit=self.use_buildkit)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)

        # Verify the image was created with convention-based tag
        expected_tag = "mymicrovmimage:latest"
        container_client = get_validated_container_client()
        images = container_client.images.list(name=expected_tag)
        self.assertTrue(bool(images), f"Docker image '{expected_tag}' should exist")

    def test_built_template_code_uri_resolved(self):
        """Built template should have intrinsic CodeUri resolved to a literal path.

        When CodeUri is an intrinsic (e.g. !Ref), update_template resolves it to the
        literal value so that move_template can correctly rebase the relative path.
        The Docker image itself is local-only — CodeUri is not replaced with an artifact
        path like ZIP functions, but the relative path is valid from .aws-sam/build/.
        """
        cmdlist = self.get_command_list(use_buildkit=self.use_buildkit)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)

        # Read built template
        self.assertTrue(self.built_template.exists(), "Built template should exist")
        with open(str(self.built_template), "r") as f:
            built_template_dict = yaml_parse(f.read())
        built_code_uri = built_template_dict["Resources"]["MyMicrovmImage"]["Properties"]["CodeUri"]

        # CodeUri should be a string (resolved from the intrinsic), not the original dict.
        # The exact value depends on the relative path from .aws-sam/build/ to the source.
        self.assertIsInstance(built_code_uri, str)
        self.assertNotEqual(built_code_uri, "")

    def test_no_artifact_directory_created(self):
        """MicrovmImage should NOT create an artifact subdirectory in .aws-sam/build/ (unlike ZIP functions)."""
        cmdlist = self.get_command_list(use_buildkit=self.use_buildkit)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)

        build_dir_files = os.listdir(str(self.default_build_dir))
        self.assertNotIn("MyMicrovmImage", build_dir_files)

    def test_build_microvm_image_with_run_step_succeeds(self):
        """A Dockerfile RUN step executes arm64 code, so on an x86 host this exercises emulation."""
        overrides = {"CodeUri": "./MicrovmImageWithRun"}
        cmdlist = self.get_command_list(parameter_overrides=overrides, use_buildkit=self.use_buildkit)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, command_result.stderr.decode())

    def test_build_foreach_dynamic_code_uri(self):
        """With --language-extensions, each Fn::ForEach image builds from its own directory and the
        built template keeps Fn::ForEach, with per-image paths in a generated Mapping."""
        source_dir = Path(self.test_data_path, "microvm-image-foreach")
        self.template_path = str(source_dir.joinpath("template.yaml"))
        cmdlist = self.get_command_list(use_buildkit=self.use_buildkit) + ["--language-extensions"]
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, command_result.stderr.decode())

        container_client = get_validated_container_client()
        for tag in ("alphaimage:latest", "betaimage:latest"):
            self.assertTrue(container_client.images.list(name=tag), f"Docker image '{tag}' should exist")

        with open(str(self.built_template), "r") as f:
            built_template = yaml_parse(f.read())
        self.assertIn("Fn::ForEach::Images", built_template["Resources"])
        mapping = built_template["Mappings"]["SAMCodeUriImages"]
        for name in ("Alpha", "Beta"):
            built_path = Path(self.default_build_dir, mapping[name]["CodeUri"]).resolve()
            self.assertEqual(built_path, source_dir.joinpath(name).resolve())

    def test_build_fails_when_dockerfile_not_found(self):
        """sam build should fail when CodeUri directory doesn't contain a Dockerfile."""
        overrides = {"CodeUri": "./NonExistentDirectory"}
        cmdlist = self.get_command_list(parameter_overrides=overrides, use_buildkit=self.use_buildkit)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 1)
        self.assertIn("Dockerfile not found", command_result.stderr.decode())

    def tearDown(self):
        # Clean up the image created during the test (works across Docker and Finch)
        try:
            container_client = get_validated_container_client()
            for tag in ("mymicrovmimage:latest", "alphaimage:latest", "betaimage:latest"):
                container_client.remove_image_safely(tag)
        except Exception:
            pass
        super().tearDown()
