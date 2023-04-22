import logging
import os
from unittest import skipIf

import pytest
from parameterized import parameterized

from samcli.commands.build.utils import MountMode
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import (
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    run_command,
    run_command_with_input,
)

LOG = logging.getLogger(__name__)


class TestBuildCommand_Dotnet_cli_package(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {
        "Amazon.Lambda.APIGatewayEvents.dll",
        "Amazon.Lambda.Core.dll",
        "HelloWorld.runtimeconfig.json",
        "Amazon.Lambda.Serialization.Json.dll",
        "Newtonsoft.Json.dll",
        "HelloWorld.deps.json",
        "HelloWorld.dll",
    }

    EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED = {
        "bootstrap",
    }

    @parameterized.expand(
        [
            ("dotnetcore3.1", "Dotnetcore3.1", None),
            ("dotnet6", "Dotnet6", None),
            ("dotnetcore3.1", "Dotnetcore3.1", "debug"),
            ("dotnet6", "Dotnet6", "debug"),
            ("provided.al2", "Dotnet7", None),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_dotnetcore_in_process(self, runtime, code_uri, mode, architecture="x86_64"):
        # dotnet7 requires docker to build the function
        if code_uri == "Dotnet7" and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": architecture,
        }

        if runtime == "provided.al2":
            self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet_7.yaml")

        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info("Running with SAM_BUILD_MODE={}".format(mode))

        newenv = os.environ.copy()
        if mode:
            newenv["SAM_BUILD_MODE"] = mode

        command_result = run_command(cmdlist, cwd=self.working_dir, env=newenv)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST
            if runtime != "provided.al2"
            else self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED,
        )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        expected = "{'message': 'Hello World'}"
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )
            self.verify_docker_container_cleanedup(runtime)

    @parameterized.expand(
        [
            ("dotnetcore3.1", "Dotnetcore3.1", None),
            ("dotnet6", "Dotnet6", None),
            ("dotnetcore3.1", "Dotnetcore3.1", "debug"),
            ("dotnet6", "Dotnet6", "debug"),
            # force to run tests on arm64 machines may cause dotnet7 test failing
            # because Native AOT Lambda functions require the host and lambda architectures to match
            ("provided.al2", "Dotnet7", None),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_dotnetcore_in_container_mount_with_write_explicit(self, runtime, code_uri, mode, architecture="x86_64"):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": architecture,
        }

        if runtime == "provided.al2":
            self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet_7.yaml")

        # test with explicit mount_with_write flag
        cmdlist = self.get_command_list(use_container=True, parameter_overrides=overrides, mount_with=MountMode.WRITE)
        # env vars needed for testing unless set by dotnet images on public.ecr.aws
        cmdlist += ["--container-env-var", "DOTNET_CLI_HOME=/tmp/dotnet"]
        cmdlist += ["--container-env-var", "XDG_DATA_HOME=/tmp/xdg"]

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info("Running with SAM_BUILD_MODE={}".format(mode))

        newenv = os.environ.copy()
        if mode:
            newenv["SAM_BUILD_MODE"] = mode

        command_result = run_command(cmdlist, cwd=self.working_dir, env=newenv)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST
            if runtime != "provided.al2"
            else self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED,
        )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        expected = "{'message': 'Hello World'}"
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
        )
        self.verify_docker_container_cleanedup(runtime)

    @parameterized.expand(
        [
            ("dotnetcore3.1", "Dotnetcore3.1", None),
            ("dotnet6", "Dotnet6", None),
            ("dotnetcore3.1", "Dotnetcore3.1", "debug"),
            ("dotnet6", "Dotnet6", "debug"),
            # force to run tests on arm64 machines may cause dotnet7 test failing
            # because Native AOT Lambda functions require the host and lambda architectures to match
            ("provided.al2", "Dotnet7", None),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_dotnetcore_in_container_mount_with_write_interactive(
        self,
        runtime,
        code_uri,
        mode,
        architecture="x86_64",
    ):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
            "Architectures": architecture,
        }

        if runtime == "provided.al2":
            self.template_path = self.template_path.replace("template.yaml", "template_build_method_dotnet_7.yaml")

        # test without explicit mount_with_write flag
        cmdlist = self.get_command_list(use_container=True, parameter_overrides=overrides)
        # env vars needed for testing unless set by dotnet images on public.ecr.aws
        cmdlist += ["--container-env-var", "DOTNET_CLI_HOME=/tmp/dotnet"]
        cmdlist += ["--container-env-var", "XDG_DATA_HOME=/tmp/xdg"]

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info("Running with SAM_BUILD_MODE={}".format(mode))

        # mock user input to mount with write
        user_click_confirm_input = "y"
        command_result = run_command_with_input(cmdlist, user_click_confirm_input.encode(), cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST
            if runtime != "provided.al2"
            else self.EXPECTED_FILES_PROJECT_MANIFEST_PROVIDED,
        )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        expected = "{'message': 'Hello World'}"
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
        )
        self.verify_docker_container_cleanedup(runtime)

    @parameterized.expand([("dotnetcore3.1", "Dotnetcore3.1"), ("dotnet6", "Dotnet6")])
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_must_fail_on_container_mount_without_write_interactive(self, runtime, code_uri):
        use_container = True
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        # mock user input to not allow mounting with write
        user_click_confirm_input = "N"
        process_execute = run_command_with_input(cmdlist, user_click_confirm_input.encode())

        # Must error out, because mounting with write is not allowed
        self.assertEqual(process_execute.process.returncode, 1)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path), function_logical_id, "CodeUri", function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEqual(actual_files, expected_files)
