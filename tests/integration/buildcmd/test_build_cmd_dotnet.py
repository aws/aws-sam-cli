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
    @parameterized.expand(
        [
            ("provided.al2", "Dotnet7", None, None),
            ("provided.al2", "Dotnet7", None, MountMode.WRITE),
            ("provided.al2", "Dotnet", None, None),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_dotnet_al2(self, runtime, code_uri, mode, mount_mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        if mode == "Dotnet":
            self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet.yaml")
        else:
            self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet_7.yaml")

        self.validate_build_command(overrides, mode, mount_mode)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED)
        self.validate_invoke_command(overrides, runtime)

    @parameterized.expand(
        [
            ("dotnet6", "Dotnet6", None, None),
            ("dotnet6", "Dotnet6", None, MountMode.WRITE),
            ("dotnet6", "Dotnet6", "debug", None),
            ("dotnet6", "Dotnet6", "debug", MountMode.WRITE),
        ]
    )
    def test_dotnet_6(self, runtime, code_uri, mode, mount_mode):
        if mount_mode and SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.validate_build_command(overrides, mode, mount_mode)
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)

        if not SKIP_DOCKER_TESTS:
            self.validate_invoke_command(overrides, runtime)

    @parameterized.expand(
        [
            ("dotnet8", "Dotnet8", None, None),
            ("dotnet8", "Dotnet8", None, MountMode.WRITE),
            ("dotnet8", "Dotnet8", "debug", None),
            ("dotnet8", "Dotnet8", "debug", MountMode.WRITE),
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


@pytest.mark.dotnet
@skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
class TestBuildCommand_Dotnet_cli_package_interactive(BuildIntegDotnetBase):
    @parameterized.expand(
        [
            ("provided.al2", "Dotnet7", None),
        ]
    )
    def test_dotnet_al2(self, runtime, code_uri, mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet_7.yaml")

        self.validate_build_command(overrides, mode, use_container=True, input="y")
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED)
        self.validate_invoke_command(overrides, runtime)

    @parameterized.expand(
        [
            ("dotnet6", "Dotnet6", None),
            ("dotnet6", "Dotnet6", "debug"),
        ]
    )
    def test_dotnet_6(self, runtime, code_uri, mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.validate_build_command(overrides, mode, use_container=True, input="y")
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, runtime)

    @parameterized.expand(
        [
            ("dotnet8", "Dotnet8", None),
            ("dotnet8", "Dotnet8", "debug"),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_dotnet_al2023(self, runtime, code_uri, mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": "x86_64",
        }

        self.validate_build_command(overrides, mode, use_container=True, input="y")
        self.validate_build_artifacts(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.validate_invoke_command(overrides, runtime)

    @parameterized.expand([("dotnet6", "Dotnet6"), ("dotnet8", "Dotnet8")])
    def test_must_fail_on_container_mount_without_write_interactive(self, runtime, code_uri):
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
