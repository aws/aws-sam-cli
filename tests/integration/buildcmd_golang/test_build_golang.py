import logging
import os
from unittest import skipIf

import pytest
from parameterized import parameterized

from samcli.lib.utils.architecture import X86_64
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import SKIP_DOCKER_TESTS, SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE, run_command

LOG = logging.getLogger(__name__)


class BuildIntegGoBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {"hello-world"}

    def _test_with_go(self, runtime, code_uri, mode, relative_path, architecture=None, use_container=False):
        overrides = self.get_override(runtime, code_uri, architecture, "hello-world")
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        # Need to pass GOPATH ENV variable to match the test directory when running build

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info("Running with SAM_BUILD_MODE={}".format(mode))

        newenv = os.environ.copy()
        if mode:
            newenv["SAM_BUILD_MODE"] = mode

        newenv["GOPROXY"] = "direct"
        newenv["GOPATH"] = str(self.working_dir)

        run_command(cmdlist, cwd=self.working_dir, env=newenv)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
        )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(relative_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        expected = "{'message': 'Hello World'}"
        if not SKIP_DOCKER_TESTS and architecture == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime, architecture)

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


class TestBuildCommand_Go_Modules(BuildIntegGoBase):
    @parameterized.expand([("go1.x", "Go", None, False), ("go1.x", "Go", "debug", True)])
    @pytest.mark.flaky(reruns=3)
    def test_building_go(self, runtime, code_uri, mode, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        self._test_with_go(runtime, code_uri, mode, self.test_data_path, use_container=use_container)


class TestBuildCommand_Go_Modules_With_Specified_Architecture(BuildIntegGoBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("go1.x", "Go", None, "x86_64"),
            ("go1.x", "Go", "debug", "x86_64"),
            ("go1.x", "Go", None, "arm64"),
            ("go1.x", "Go", "debug", "arm64"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_go(self, runtime, code_uri, mode, architecture):
        self._test_with_go(runtime, code_uri, mode, self.test_data_path, architecture)

    @parameterized.expand([("go1.x", "Go", "unknown_architecture")])
    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_go_must_fail_with_unknown_architecture(self, runtime, code_uri, architecture):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": "hello-world", "Architectures": architecture}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        process_execute = run_command(cmdlist, cwd=self.working_dir)

        # Must error out, because container builds are not supported
        self.assertEqual(process_execute.process.returncode, 1)
