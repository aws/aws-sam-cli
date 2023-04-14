import logging
import os
import shutil
from pathlib import Path
from unittest import skipIf, skip

import pytest
from parameterized import parameterized, parameterized_class

from samcli.lib.utils.architecture import X86_64
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import (
    run_command,
    SKIP_DOCKER_TESTS,
    IS_WINDOWS,
    RUNNING_ON_CI,
    CI_OVERRIDE,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
)

LOG = logging.getLogger(__name__)


class BuildIntegEsbuildBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    # Everything should be minifed to one line and a second line for the sourcemap mapping
    MAX_MINIFIED_LINE_COUNT = 2

    def _test_with_default_package_json(
        self, runtime, use_container, code_uri, expected_files, handler, architecture=None, build_in_source=None
    ):
        overrides = self.get_override(runtime, code_uri, architecture, handler)
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, build_in_source=build_in_source
        )

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            expected_files,
        )

        expected = {"body": '{"message":"hello world!"}', "statusCode": 200}
        if not SKIP_DOCKER_TESTS and architecture == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        self._verify_esbuild_properties(self.default_build_dir, self.FUNCTION_LOGICAL_ID, handler)

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime, architecture)

    def _test_with_various_properties(self, overrides):
        overrides = self.get_override(**overrides)
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        expected = {"body": '{"message":"hello world!"}', "statusCode": 200}
        if not SKIP_DOCKER_TESTS and overrides["Architectures"] == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        self._verify_esbuild_properties(self.default_build_dir, self.FUNCTION_LOGICAL_ID, overrides["Handler"])

    def _verify_esbuild_properties(self, build_dir, function_logical_id, handler):
        filename = self._extract_filename_from_handler(handler)
        resource_artifact_dir = build_dir.joinpath(function_logical_id)
        self._verify_sourcemap_created(filename, resource_artifact_dir)
        self._verify_function_minified(filename, resource_artifact_dir)

    @staticmethod
    def _extract_filename_from_handler(handler):
        # Takes a handler in the form /a/b/c/file.function and returns file
        return str(Path(handler).stem)

    def _verify_function_minified(self, filename, resource_artifact_dir):
        with open(Path(resource_artifact_dir, f"{filename}.js"), "r") as handler_file:
            x = len(handler_file.readlines())
        self.assertLessEqual(x, self.MAX_MINIFIED_LINE_COUNT)

    def _verify_sourcemap_created(self, filename, resource_artifact_dir):
        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        self.assertIn(f"{filename}.js.map", all_artifacts)

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


class TestBuildCommand_EsbuildFunctions(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"

    @parameterized.expand(
        [
            ("nodejs14.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", False, "x86_64"),
            ("nodejs12.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", False, "arm64"),
            ("nodejs14.x", "Esbuild/TypeScript", {"app.js", "app.js.map"}, "app.lambdaHandler", False, "x86_64"),
            ("nodejs12.x", "Esbuild/TypeScript", {"app.js", "app.js.map"}, "app.lambdaHandler", False, "arm64"),
            ("nodejs14.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", "use_container", "x86_64"),
            ("nodejs12.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", "use_container", "arm64"),
            (
                "nodejs14.x",
                "Esbuild/TypeScript",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                "use_container",
                "x86_64",
            ),
            (
                "nodejs12.x",
                "Esbuild/TypeScript",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                "use_container",
                "arm64",
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_default_package_json(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, architecture)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@parameterized_class(
    ("template",),
    [
        ("esbuild_templates/template_with_metadata_node_options.yaml",),
        ("esbuild_templates/template_with_metadata_global_node_options.yaml",),
    ],
)
class TestBuildCommand_EsbuildFunctionProperties(BuildIntegEsbuildBase):
    @parameterized.expand(
        [
            ("nodejs16.x", "../Esbuild/TypeScript", "app.lambdaHandler", "x86_64"),
            ("nodejs18.x", "../Esbuild/TypeScript", "app.lambdaHandler", "x86_64"),
            ("nodejs16.x", "../Esbuild/TypeScript", "nested/function/app.lambdaHandler", "x86_64"),
            ("nodejs18.x", "../Esbuild/TypeScript", "nested/function/app.lambdaHandler", "x86_64"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_environment_generates_sourcemap(self, runtime, code_uri, handler, architecture):
        overrides = {
            "runtime": runtime,
            "code_uri": code_uri,
            "handler": handler,
            "architecture": architecture,
        }
        self._test_with_various_properties(overrides)


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
class TestBuildCommand_BuildInSource_Esbuild(BuildIntegEsbuildBase):
    is_nested_parent = False

    def setUp(self):
        super().setUp()
        self.source_directories = []

    def tearDown(self):
        super().tearDown()
        # clean up dependencies installed in source directories
        for source in self.source_directories:
            shutil.rmtree(os.path.join(source, "node_modules"), ignore_errors=True)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, dependencies_expected_in_source):
        self.template_path = os.path.join(self.test_data_path, "template_with_metadata.yaml")
        codeuri = os.path.join(self.test_data_path, "Esbuild", "Node")
        self.source_directories = [codeuri]

        self._test_with_default_package_json(
            build_in_source=build_in_source,
            runtime="nodejs16.x",
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture="x86_64",
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), dependencies_expected_in_source)

    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        self.template_path = os.path.join(self.test_data_path, "template_with_metadata.yaml")
        codeuri = os.path.join(self.test_data_path, "Esbuild", "NodeWithLocalDependency")
        self.source_directories = [codeuri]
        runtime = "nodejs16.x"
        architecture = "x86_64"

        self._test_with_default_package_json(
            build_in_source=True,
            runtime=runtime,
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture=architecture,
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), True)
