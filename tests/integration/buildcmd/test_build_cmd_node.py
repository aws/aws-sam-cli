import logging
from unittest import skipIf
from parameterized import parameterized, parameterized_class
import pytest

from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    CI_OVERRIDE,
)
from tests.integration.buildcmd.build_integ_base import (
    BuildIntegNodeBase,
    BuildIntegEsbuildBase,
)


LOG = logging.getLogger(__name__)

# SAR tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SAR_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@pytest.mark.nodejs
class TestBuildCommand_NodeFunctions_With_External_Manifest(BuildIntegNodeBase):
    CODE_URI = "Node_without_manifest"
    TEST_INVOKE = True
    MANIFEST_PATH = "npm_manifest/package.json"

    @parameterized.expand(
        [
            ("nodejs16.x",),
            ("nodejs18.x",),
        ]
    )
    def test_building_default_package_json(self, runtime):

        self._test_with_default_package_json(runtime, False, self.test_data_path)

    @parameterized.expand(
        [
            ("nodejs20.x",),
            ("nodejs22.x",),
        ]
    )
    @pytest.mark.al2023
    def test_building_default_package_json_al2023(self, runtime):
        self._test_with_default_package_json(runtime, False, self.test_data_path)


class TestBuildCommand_EsbuildFunctions(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"

    @parameterized.expand(
        [
            ("nodejs18.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", "use_container", "x86_64"),
            (
                "nodejs18.x",
                "Esbuild/TypeScript",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                "use_container",
                "x86_64",
            ),
        ]
    )
    def test_building_default_package_json(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, architecture)

    @parameterized.expand(
        [
            ("nodejs20.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", False, "x86_64"),
            ("nodejs20.x", "Esbuild/TypeScript", {"app.js", "app.js.map"}, "app.lambdaHandler", False, "x86_64"),
        ]
    )
    @pytest.mark.al2023
    def test_building_default_package_json_al2023(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):

        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, architecture)


class TestBuildCommand_EsbuildFunctions_With_External_Manifest(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"
    MANIFEST_PATH = "Esbuild/npm_manifest/package.json"

    @parameterized.expand(
        [
            (
                "nodejs20.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
                "x86_64",
            ),
            (
                "nodejs20.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
                "x86_64",
            ),
        ]
    )
    @pytest.mark.al2023
    def test_building_default_package_json(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):
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
    def test_environment_generates_sourcemap(self, runtime, code_uri, handler, architecture):
        overrides = {
            "runtime": runtime,
            "code_uri": code_uri,
            "handler": handler,
            "architecture": architecture,
        }
        self._test_with_various_properties(overrides, runtime)

    @parameterized.expand(
        [
            ("nodejs20.x", "../Esbuild/TypeScript", "app.lambdaHandler", "x86_64"),
            ("nodejs20.x", "../Esbuild/TypeScript", "nested/function/app.lambdaHandler", "x86_64"),
        ]
    )
    @pytest.mark.al2023
    def test_environment_generates_sourcemap_al2023(self, runtime, code_uri, handler, architecture):
        overrides = {
            "runtime": runtime,
            "code_uri": code_uri,
            "handler": handler,
            "architecture": architecture,
        }
        self._test_with_various_properties(overrides, runtime)


class TestBuildCommand_NodeFunctions_With_Specified_Architecture(BuildIntegNodeBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("nodejs16.x", False, "x86_64"),
            ("nodejs18.x", False, "x86_64"),
            ("nodejs16.x", "use_container", "x86_64"),
            ("nodejs18.x", "use_container", "x86_64"),
            ("nodejs20.x", False, "x86_64"),
            ("nodejs22.x", False, "x86_64"),
        ]
    )
    def test_building_default_package_json(self, runtime, use_container, architecture):
        self._test_with_default_package_json(runtime, use_container, self.test_data_path, architecture)
