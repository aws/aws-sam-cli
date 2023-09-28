import os
from unittest import skipIf

from parameterized import parameterized, parameterized_class

from tests.integration.buildcmd.build_integ_base import (
    BuildIntegEsbuildBase,
    BuildIntegGoBase, 
    BuildIntegJavaBase,
    BuildIntegNodeBase, 
    BuildIntegProvidedBase, 
    BuildIntegPythonBase,
    BuildIntegRubyBase
)
from tests.testing_utils import SKIP_DOCKER_TESTS, SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE, CI_OVERRIDE, IS_WINDOWS


class TestBuildCommand_PythonFunctions_With_Specified_Architecture_arm64(BuildIntegPythonBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("python3.8", "Python", False, "arm64"),
            ("python3.8", "PythonPEP600", False, "arm64"),
            ("python3.8", "Python", "use_container", "arm64"),
        ]
    )
    def test_with_default_requirements(self, runtime, codeuri, use_container, architecture):
        self._test_with_default_requirements(
            runtime, codeuri, use_container, self.test_data_path, architecture=architecture
        )


class TestBuildCommand_EsbuildFunctions_arm64(BuildIntegEsbuildBase):
    template = "template_with_metadata_esbuild.yaml"

    @parameterized.expand(
        [
            ("nodejs12.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", False, "arm64"),
            ("nodejs12.x", "Esbuild/TypeScript", {"app.js", "app.js.map"}, "app.lambdaHandler", False, "arm64"),
            ("nodejs12.x", "Esbuild/Node", {"main.js", "main.js.map"}, "main.lambdaHandler", "use_container", "arm64"),
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
    def test_building_default_package_json(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, architecture)


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
                "arm64",
            ),
            (
                "nodejs18.x",
                "Esbuild/Node_without_manifest",
                {"main.js", "main.js.map"},
                "main.lambdaHandler",
                False,
                "arm64",
            ),
            (
                "nodejs16.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
                "arm64",
            ),
            (
                "nodejs18.x",
                "Esbuild/TypeScript_without_manifest",
                {"app.js", "app.js.map"},
                "app.lambdaHandler",
                False,
                "arm64",
            ),
        ]
    )
    def test_building_default_package_json(
        self, runtime, code_uri, expected_files, handler, use_container, architecture
    ):
        self._test_with_default_package_json(runtime, use_container, code_uri, expected_files, handler, architecture)


class TestBuildCommand_NodeFunctions_With_Specified_Architecture_arm64(BuildIntegNodeBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
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
    def test_building_default_package_json(self, runtime, use_container, architecture):
        self._test_with_default_package_json(runtime, use_container, self.test_data_path, architecture)


class TestBuildCommand_RubyFunctions_With_Architecture_arm64(BuildIntegRubyBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand([("ruby2.7", "arm64", "Ruby"), ("ruby3.2", "arm64", "Ruby32")])
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_ruby_in_container_with_specified_architecture(self, runtime, architecture, code_uri):
        self._test_with_default_gemfile(runtime, "use_container", code_uri, self.test_data_path, architecture)

    @parameterized.expand([("ruby2.7", "arm64", "Ruby"), ("ruby3.2", "arm64", "Ruby32")])
    def test_building_ruby_in_process_with_specified_architecture(self, runtime, architecture, code_uri):
        self._test_with_default_gemfile(runtime, False, code_uri, self.test_data_path, architecture)


@skipIf(
    (IS_WINDOWS and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_Java_With_Specified_Architecture_arm64(BuildIntegJavaBase):
    template = "template_with_architecture.yaml"
    EXPECTED_FILES_PROJECT_MANIFEST_GRADLE = {"aws", "lib", "META-INF"}
    EXPECTED_FILES_PROJECT_MANIFEST_MAVEN = {"aws", "lib"}
    EXPECTED_GRADLE_DEPENDENCIES = {"annotations-2.1.0.jar", "aws-lambda-java-core-1.1.0.jar"}
    EXPECTED_MAVEN_DEPENDENCIES = {
        "software.amazon.awssdk.annotations-2.1.0.jar",
        "com.amazonaws.aws-lambda-java-core-1.1.0.jar",
    }

    FUNCTION_LOGICAL_ID = "Function"
    USING_GRADLE_PATH = os.path.join("Java", "gradle")
    USING_GRADLEW_PATH = os.path.join("Java", "gradlew")
    USING_GRADLE_KOTLIN_PATH = os.path.join("Java", "gradle-kotlin")
    USING_MAVEN_PATH = os.path.join("Java", "maven")

    @parameterized.expand(
        [
            (
                "java8.al2",
                "8",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                "8",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                "8",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                "8",
                USING_MAVEN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                EXPECTED_MAVEN_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                "11",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                "11",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                "11",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                "11",
                USING_MAVEN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                EXPECTED_MAVEN_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                "17",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                "17",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                "17",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                "17",
                USING_MAVEN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                EXPECTED_MAVEN_DEPENDENCIES,
                "arm64",
            ),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_java_in_container_with_arm64_architecture(
        self, runtime, runtime_version, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, runtime_version),
            expected_files,
            expected_dependencies,
            "use_container",
            self.test_data_path,
            architecture,
        )

    @parameterized.expand(
        [
            (
                "java8.al2",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java8.al2",
                USING_MAVEN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_MAVEN,
                EXPECTED_MAVEN_DEPENDENCIES,
                "arm64",
            ),
        ]
    )
    def test_building_java8_in_process_with_arm_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, "8"),
            expected_files,
            expected_dependencies,
            False,
            self.test_data_path,
            architecture,
        )

    @parameterized.expand(
        [
            (
                "java11",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java11",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            ("java11", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES, "arm64"),
        ]
    )
    def test_building_java11_in_process_with_arm_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, "11"),
            expected_files,
            expected_dependencies,
            False,
            self.test_data_path,
            architecture,
        )

    @parameterized.expand(
        [
            (
                "java17",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                USING_GRADLEW_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            (
                "java17",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
            ("java17", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES, "arm64"),
        ]
    )
    def test_building_java17_in_process_with_arm_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime,
            os.path.join(code_path, "17"),
            expected_files,
            expected_dependencies,
            False,
            self.test_data_path,
            architecture,
        )


class TestBuildCommand_Go_Modules_With_Specified_Architecture_arm64(BuildIntegGoBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("go1.x", "Go", None, "arm64"),
            ("go1.x", "Go", "debug", "arm64"),
        ]
    )
    def test_building_go(self, runtime, code_uri, mode, architecture):
        self._test_with_go(runtime, code_uri, mode, self.test_data_path, architecture)


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
            ("provided", False, None, "arm64"),
            ("provided", "use_container", "Makefile-container", "arm64"),
            ("provided.al2", False, None, "arm64"),
            ("provided.al2", "use_container", "Makefile-container", "arm64"),
        ]
    )
    def test_building_Makefile(self, runtime, use_container, manifest, architecture):
        self._test_with_Makefile(runtime, use_container, manifest, architecture)
