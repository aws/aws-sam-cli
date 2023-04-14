import logging
import os
import sys
from pathlib import Path
from unittest import skip

import pytest
from parameterized import parameterized_class, parameterized

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import SKIP_DOCKER_TESTS, SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE, run_command

LOG = logging.getLogger(__name__)


class BuildIntegProvidedBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requests", "requirements.txt"}

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_Makefile(
        self, runtime, use_container, manifest, architecture=None, code_uri="Provided", build_in_source=None
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = self.get_override(runtime, code_uri, architecture, "main.handler")
        manifest_path = None
        if manifest:
            manifest_path = os.path.join(self.test_data_path, "Provided", manifest)

        cmdlist = self.get_command_list(
            use_container=use_container,
            parameter_overrides=overrides,
            manifest_path=manifest_path,
            build_in_source=build_in_source,
        )

        LOG.info("Running Command: {}".format(cmdlist))
        # Built using Makefile for a python project.
        run_command(cmdlist, cwd=self.working_dir)

        if self.is_nested_parent:
            self._verify_built_artifact_in_subapp(
                self.default_build_dir, "SubApp", self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
            )
        else:
            self._verify_built_artifact(
                self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
            )

        expected = "2.23.0"
        # Building was done with a makefile, but invoke should be checked with corresponding python image.
        overrides["Runtime"] = self._get_python_version()
        if not SKIP_DOCKER_TESTS:
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

    def _verify_built_artifact_in_subapp(self, build_dir, subapp_path, function_logical_id, expected_files):
        self.assertTrue(build_dir.exists(), "Build directory should be created")
        subapp_build_dir = Path(build_dir, subapp_path)
        self.assertTrue(subapp_build_dir.exists(), f"Build directory for sub app {subapp_path} should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)

        subapp_build_dir_files = os.listdir(str(subapp_build_dir))
        self.assertIn("template.yaml", subapp_build_dir_files)
        self.assertIn(function_logical_id, subapp_build_dir_files)

        template_path = subapp_build_dir.joinpath("template.yaml")
        resource_artifact_dir = subapp_build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path), function_logical_id, "CodeUri", function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEqual(actual_files, expected_files)

    def _get_python_version(self):
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


@parameterized_class(
    ("template", "is_nested_parent"),
    [
        (os.path.join("nested-parent", "template-parent.yaml"), "is_nested_parent"),
        ("template.yaml", False),
    ],
)
class TestBuildCommand_ProvidedFunctions(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None),
            ("provided", "use_container", "Makefile-container"),
            ("provided.al2", False, None),
            ("provided.al2", "use_container", "Makefile-container"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_Makefile(self, runtime, use_container, manifest):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_Makefile(runtime, use_container, manifest)


@parameterized_class(
    ("template", "is_nested_parent"),
    [
        (os.path.join("nested-parent", "template-parent.yaml"), "is_nested_parent"),
        ("template.yaml", False),
    ],
)
class TestBuildCommand_ProvidedFunctions_With_Specified_Architecture(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None, "x86_64"),
            ("provided", "use_container", "Makefile-container", "x86_64"),
            ("provided.al2", False, None, "x86_64"),
            ("provided.al2", "use_container", "Makefile-container", "x86_64"),
            ("provided", False, None, "arm64"),
            ("provided", "use_container", "Makefile-container", "arm64"),
            ("provided.al2", False, None, "arm64"),
            ("provided.al2", "use_container", "Makefile-container", "arm64"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_Makefile(self, runtime, use_container, manifest, architecture):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_Makefile(runtime, use_container, manifest, architecture)


@parameterized_class(
    ("template", "code_uri", "is_nested_parent"),
    [
        ("custom_build_with_custom_root_project_path.yaml", "empty_src_code", False),
        ("custom_build_with_custom_make_file_path.yaml", "provided_src_code_without_makefile", False),
        ("custom_build_with_custom_working_dir.yaml", "custom_working_dir_src_code", False),
        ("custom_build_with_custom_root_project_path_and_custom_makefile_path.yaml", "empty_src_code", False),
        (
            "custom_build_with_custom_root_project_path_custom_makefile_path_and_custom_working_dir.yaml",
            "empty_src_code",
            False,
        ),
    ],
)
class TestBuildCommand_ProvidedFunctionsWithCustomMetadata(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None),
            ("provided.al2", False, None),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_Makefile(self, runtime, use_container, manifest):
        self._test_with_Makefile(runtime, use_container, manifest)


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
class TestBuildCommand_BuildInSource_Makefile(BuildIntegProvidedBase):
    template = "template.yaml"
    is_nested_parent = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code_uri = "provided_create_new_file"
        cls.code_uri_path = os.path.join(cls.test_data_path, cls.code_uri)
        cls.file_created_from_make_command = "file-created-from-make-command.txt"

    def tearDown(self):
        super().tearDown()
        new_file_in_codeuri_path = os.path.join(self.code_uri_path, self.file_created_from_make_command)
        if os.path.isfile(new_file_in_codeuri_path):
            os.remove(new_file_in_codeuri_path)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_makefile(self, build_in_source, new_file_should_be_in_codeuri):
        self._test_with_Makefile(
            runtime="provided.al2",
            use_container=False,
            manifest=None,
            code_uri=self.code_uri,
            build_in_source=build_in_source,
        )

        self.assertEqual(
            self.file_created_from_make_command in os.listdir(self.code_uri_path), new_file_should_be_in_codeuri
        )
