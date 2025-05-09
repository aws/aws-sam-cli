import os
from unittest import skipIf
import pytest

from parameterized import parameterized, parameterized_class

from samcli.lib.utils.architecture import ARM64
from tests.integration.buildcmd.build_integ_base import (
    BuildIntegEsbuildBase,
    BuildIntegGoBase,
    BuildIntegJavaBase,
    BuildIntegNodeBase,
    BuildIntegProvidedBase,
    BuildIntegPythonBase,
    BuildIntegRubyBase,
    BuildIntegRustBase,
    rust_parameterized_class,
)
from tests.testing_utils import (
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    CI_OVERRIDE,
    IS_WINDOWS,
    RUNNING_ON_CI,
)


@pytest.mark.python
class TestBuildCommand_PythonFunctions_With_Specified_Architecture_arm64(BuildIntegPythonBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("python3.9", "Python", False),
            ("python3.10", "Python", False),
            ("python3.11", "Python", False),
            ("python3.12", "Python", False),
            ("python3.13", "Python", False),
            ("python3.9", "PythonPEP600", False),
            ("python3.10", "PythonPEP600", False),
            ("python3.11", "PythonPEP600", False),
            ("python3.12", "PythonPEP600", False),
            ("python3.13", "PythonPEP600", False),
            ("python3.9", "Python", "use_container"),
            ("python3.10", "Python", "use_container"),
            ("python3.11", "Python", "use_container"),
        ]
    )
    def test_with_default_requirements(self, runtime, codeuri, use_container):
        self._test_with_default_requirements(runtime, codeuri, use_container, self.test_data_path, architecture=ARM64)

    @parameterized.expand(
        [
            ("python3.12", "Python", "use_container"),
            ("python3.13", "Python", "use_container"),
        ]
    )
    @pytest.mark.al2023
    def test_with_default_requirements_al2023(self, runtime, codeuri, use_container):
        self._test_with_default_requirements(runtime, codeuri, use_container, self.test_data_path, architecture=ARM64)


class TestBuildCommand_EsbuildFunctions_arm64(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"

    @parameterized.expand(
        [
            ("nodejs20.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", False),
            ("nodejs20.x", "Esbuild/TypeScript", {"app.js", "app.js.map"}, "app.lambdaHandler", False),
            ("nodejs20.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", "use_container"),
            (
                "nodejs20.x",
                "Esbuild/TypeScript",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                "use_container",
            ),
        ]
    )
    def test_building_default_package_json(self, runtime, code_uri, expected_files, handler, use_container):
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, ARM64)


@pytest.mark.nodejs
class TestBuildCommand_EsbuildFunctions_With_External_Manifest_arm64(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"
    MANIFEST_PATH = "Esbuild/npm_manifest/package.json"

    @parameterized.expand(
        [
            (
                "nodejs16.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
            ),
            (
                "nodejs18.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
            ),
            (
                "nodejs20.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
            ),
            (
                "nodejs22.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
            ),
            (
                "nodejs16.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
            ),
            (
                "nodejs18.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
            ),
            (
                "nodejs20.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
            ),
            (
                "nodejs22.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
            ),
        ]
    )
    def test_building_default_package_json(self, runtime, code_uri, expected_files, handler, use_container):
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, ARM64)


@pytest.mark.nodejs
class TestBuildCommand_NodeFunctions_With_Specified_Architecture_arm64(BuildIntegNodeBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("nodejs16.x", False),
            ("nodejs18.x", False),
            ("nodejs20.x", False),
            ("nodejs22.x", False),
            ("nodejs16.x", "use_container"),
            ("nodejs18.x", "use_container"),
        ]
    )
    def test_building_default_package_json(self, runtime, use_container):
        self._test_with_default_package_json(runtime, use_container, self.test_data_path, ARM64)

    @parameterized.expand(
        [
            ("nodejs20.x", "use_container"),
            ("nodejs22.x", "use_container"),
        ]
    )
    @pytest.mark.al2023
    def test_building_default_package_json_al2023(self, runtime, use_container):
        self._test_with_default_package_json(runtime, use_container, self.test_data_path, ARM64)


class TestBuildCommand_RubyFunctions_With_Architecture_arm64(BuildIntegRubyBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand([("ruby3.2", "Ruby32"), ("ruby3.4", "Ruby34")])
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_ruby_in_container_with_specified_architecture(self, runtime, code_uri):
        self._test_with_default_gemfile(runtime, "use_container", code_uri, self.test_data_path, ARM64)

    @parameterized.expand([("ruby3.2", "Ruby32")])
    def test_building_ruby_in_process_with_specified_architecture(self, runtime, code_uri):
        self._test_with_default_gemfile(runtime, False, code_uri, self.test_data_path, ARM64)


@skipIf(
    (IS_WINDOWS and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@pytest.mark.java
class TestBuildCommand_Java_With_Specified_Architecture_arm64(BuildIntegJavaBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_java_in_container_with_arm64_architecture(
        self, runtime, runtime_version, code_path, expected_files, expected_dependencies
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, runtime_version),
            expected_files,
            expected_dependencies,
            "use_container",
            self.test_data_path,
            ARM64,
        )

    @parameterized.expand(
        [
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_building_java_in_container_with_arm64_architecture_al2023(
        self, runtime, runtime_version, code_path, expected_files, expected_dependencies
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, runtime_version),
            expected_files,
            expected_dependencies,
            "use_container",
            self.test_data_path,
            ARM64,
        )

    @parameterized.expand(
        [
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java8.al2",
                "8",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java11",
                "11",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java17",
                "17",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLE_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLEW_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_GRADLE_KOTLIN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                BuildIntegJavaBase.EXPECTED_GRADLE_DEPENDENCIES,
            ),
            (
                "java21",
                "21",
                BuildIntegJavaBase.USING_MAVEN_PATH,
                BuildIntegJavaBase.EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                BuildIntegJavaBase.EXPECTED_MAVEN_DEPENDENCIES,
            ),
        ]
    )
    def test_building_java_in_process_with_arm_architecture(
        self, runtime, runtime_version, code_path, expected_files, expected_dependencies
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, runtime_version),
            expected_files,
            expected_dependencies,
            False,
            self.test_data_path,
            ARM64,
        )


class TestBuildCommand_Go_Modules_With_Specified_Architecture_arm64(BuildIntegGoBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            (
                "go1.x",
                "Go",
                None,
            ),
            (
                "go1.x",
                "Go",
                "debug",
            ),
        ]
    )
    def test_building_go(self, runtime, code_uri, mode):
        self._test_with_go(runtime, code_uri, mode, self.test_data_path, ARM64)


@parameterized_class(
    ("template", "is_nested_parent"),
    [
        (os.path.join("nested-parent", "template-parent.yaml"), "is_nested_parent"),
        ("template.yaml", False),
    ],
)
class TestBuildCommand_ProvidedFunctions_With_Specified_Architecture_arm64(BuildIntegProvidedBase):
    @parameterized.expand(
        [
            (
                "provided",
                False,
                None,
            ),
            (
                "provided.al2023",
                False,
                None,
            ),
            (
                "provided",
                "use_container",
                "Makefile-container",
            ),
            (
                "provided.al2",
                False,
                None,
            ),
            (
                "provided.al2",
                "use_container",
                "Makefile-container",
            ),
        ]
    )
    def test_building_Makefile(self, runtime, use_container, manifest):
        self._test_with_Makefile(runtime, use_container, manifest, ARM64)

    @parameterized.expand(
        [
            (
                "provided.al2023",
                "use_container",
                "Makefile-container",
            ),
        ]
    )
    @pytest.mark.al2023
    def test_building_Makefile_al2023(self, runtime, use_container, manifest):
        self._test_with_Makefile(runtime, use_container, manifest, ARM64)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@rust_parameterized_class
@pytest.mark.provided
class TestBuildCommand_Rust_arm64(BuildIntegRustBase):
    @parameterized.expand(
        [
            ("provided.al2", None, False),
            ("provided.al2", "debug", False),
            ("provided.al2023", None, False),
            ("provided.al2023", "debug", False),
        ]
    )
    def test_build(self, runtime, build_mode, use_container):
        self._test_with_rust_cargo_lambda(
            runtime=runtime,
            code_uri=self.code_uri,
            binary=self.binary,
            architecture=ARM64,
            build_mode=build_mode,
            expected_invoke_result=self.expected_invoke_result,
            use_container=use_container,
        )
