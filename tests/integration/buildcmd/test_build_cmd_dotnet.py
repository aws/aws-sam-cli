import logging
from unittest import skipIf

import pytest
from parameterized import parameterized

from samcli.commands.build.utils import MountMode
from tests.testing_utils import (
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    run_command_with_input,
)
from tests.integration.buildcmd.build_integ_base import (
    BuildIntegDotnetBase,
)

LOG = logging.getLogger(__name__)


@pytest.mark.dotnet
class TestBuildCommand_Dotnet_cli_package(BuildIntegDotnetBase):
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_dotnet_al2(self):
        overrides = {
            "Runtime": "provided.al2",
            "CodeUri": "Dotnet",
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet.yaml")

        self.validate_build_command(overrides, None, None)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED)
        self.validate_invoke_command(overrides, "provided.al2")

    @parameterized.expand(
        [
            ("dotnet8", "Dotnet8", None, None),
            ("dotnet8", "Dotnet8", None, MountMode.WRITE),
            ("dotnet8", "Dotnet8", "debug", None),
            ("dotnet8", "Dotnet8", "debug", MountMode.WRITE),
            ("dotnet10", "Dotnet10", None, None),
            ("dotnet10", "Dotnet10", None, MountMode.WRITE),
            ("dotnet10", "Dotnet10", "debug", None),
            ("dotnet10", "Dotnet10", "debug", MountMode.WRITE),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_dotnet_al2023(self, runtime, code_uri, mode, mount_mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.validate_build_command(overrides, mode, mount_mode)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, runtime)

    @pytest.mark.tier1_extra
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_tier1_dotnet_build(self):
        """Single Dotnet build test for cross-platform validation."""
        overrides = {
            "Runtime": "dotnet10",
            "CodeUri": "Dotnet10",
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }
        self.validate_build_command(overrides, None)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, "dotnet10")

    @pytest.mark.tier1_extra
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_tier1_dotnet_build_in_container(self):
        """Single Dotnet container build test for cross-platform validation."""
        overrides = {
            "Runtime": "dotnet8",
            "CodeUri": "Dotnet8",
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }
        self.validate_build_command(overrides, None, MountMode.WRITE)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, "dotnet8")


@pytest.mark.dotnet
@skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
class TestBuildCommand_Dotnet_cli_package_interactive(BuildIntegDotnetBase):
    @parameterized.expand(
        [
            ("dotnet8", "Dotnet8", None),
            ("dotnet8", "Dotnet8", "debug"),
            ("dotnet10", "Dotnet10", None),
            ("dotnet10", "Dotnet10", "debug"),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_dotnet_al2023_in_container(self, runtime, code_uri, mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.validate_build_command(overrides, mode, use_container=True, input="y")
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, runtime)

    @parameterized.expand([("dotnet10", "Dotnet10"), ("dotnet8", "Dotnet8")])
    def test_must_fail_in_container_mount_without_write_interactive(self, runtime, code_uri):
        use_container = True
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        # mock user input to not allow mounting with write
        user_click_confirm_input = "N"
        process_execute = run_command_with_input(cmdlist, user_click_confirm_input.encode())

        # Must error out, because mounting with write is not allowed
        self.assertEqual(process_execute.process.returncode, 1)
