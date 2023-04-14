import logging
import os

import pytest
from parameterized import parameterized

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command, SKIP_DOCKER_TESTS, SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE

LOG = logging.getLogger(__name__)


class BuildIntegNodeBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"node_modules", "main.js"}
    EXPECTED_NODE_MODULES = {"minimal-request-promise"}

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_default_package_json(self, runtime, use_container, relative_path, architecture=None):
        overrides = self.get_override(runtime, "Node", architecture, "ignored")
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST,
            self.EXPECTED_NODE_MODULES,
        )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(str(relative_path)), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(str(relative_path)), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime, architecture)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files, expected_modules):
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

        all_modules = set(os.listdir(str(resource_artifact_dir.joinpath("node_modules"))))
        actual_files = all_modules.intersection(expected_modules)
        self.assertEqual(actual_files, expected_modules)


class TestBuildCommand_NodeFunctions(BuildIntegNodeBase):
    @parameterized.expand(
        [
            ("nodejs12.x", False),
            ("nodejs14.x", False),
            ("nodejs16.x", False),
            ("nodejs18.x", False),
            ("nodejs12.x", "use_container"),
            ("nodejs14.x", "use_container"),
            ("nodejs16.x", "use_container"),
            ("nodejs18.x", "use_container"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_default_package_json(self, runtime, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_package_json(runtime, use_container, self.test_data_path)


class TestBuildCommand_NodeFunctions_With_Specified_Architecture(BuildIntegNodeBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("nodejs12.x", False, "x86_64"),
            ("nodejs14.x", False, "x86_64"),
            ("nodejs16.x", False, "x86_64"),
            ("nodejs18.x", False, "x86_64"),
            ("nodejs12.x", "use_container", "x86_64"),
            ("nodejs14.x", "use_container", "x86_64"),
            ("nodejs16.x", "use_container", "x86_64"),
            ("nodejs18.x", "use_container", "x86_64"),
            ("nodejs12.x", False, "arm64"),
            ("nodejs14.x", False, "arm64"),
            ("nodejs16.x", False, "arm64"),
            ("nodejs18.x", False, "arm64"),
            ("nodejs12.x", "use_container", "arm64"),
            ("nodejs14.x", "use_container", "arm64"),
            ("nodejs16.x", "use_container", "arm64"),
            ("nodejs18.x", "use_container", "arm64"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_default_package_json(self, runtime, use_container, architecture):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_package_json(runtime, use_container, self.test_data_path, architecture)
