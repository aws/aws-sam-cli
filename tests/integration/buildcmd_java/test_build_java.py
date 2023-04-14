import logging
import os
from unittest import skipIf

import pytest
from parameterized import parameterized

from samcli.lib.utils import osutils
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import (
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    IS_WINDOWS,
    run_command,
    CI_OVERRIDE,
)

LOG = logging.getLogger(__name__)


class BuildIntegJavaBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_building_java(
        self,
        runtime,
        code_path,
        expected_files,
        expected_dependencies,
        use_container,
        relative_path,
        architecture=None,
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = self.get_override(runtime, code_path, architecture, "aws.example.Hello::myHandler")
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)
        cmdlist += ["--skip-pull-image"]
        if code_path == self.USING_GRADLEW_PATH and use_container and IS_WINDOWS:
            osutils.convert_to_unix_line_ending(os.path.join(self.test_data_path, self.USING_GRADLEW_PATH, "gradlew"))

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir, timeout=900)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, expected_files, expected_dependencies
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

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(relative_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        # If we are testing in the container, invoke the function as well. Otherwise we cannot guarantee docker is on appveyor
        if use_container:
            expected = "Hello World"
            if not SKIP_DOCKER_TESTS:
                self._verify_invoke_built_function(
                    self.built_template,
                    self.FUNCTION_LOGICAL_ID,
                    self._make_parameter_override_arg(overrides),
                    expected,
                )

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

        lib_dir_contents = set(os.listdir(str(resource_artifact_dir.joinpath("lib"))))
        self.assertEqual(lib_dir_contents, expected_modules)


class TestBuildCommand_Java(BuildIntegJavaBase):
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
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8.al2", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            (
                "java8.al2",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
            ),
            ("java8.al2", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_building_java_in_container(self, runtime, code_path, expected_files, expected_dependencies):
        self._test_with_building_java(
            runtime, code_path, expected_files, expected_dependencies, "use_container", self.test_data_path
        )

    @parameterized.expand(
        [
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java8.al2", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            (
                "java8.al2",
                USING_GRADLE_KOTLIN_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
            ),
            ("java8.al2", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java8_in_process(self, runtime, code_path, expected_files, expected_dependencies):
        self._test_with_building_java(
            runtime, code_path, expected_files, expected_dependencies, False, self.test_data_path
        )

    @parameterized.expand(
        [
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
            ("java11", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN, EXPECTED_MAVEN_DEPENDENCIES),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE, EXPECTED_GRADLE_DEPENDENCIES),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java11_in_process(self, runtime, code_path, expected_files, expected_dependencies):
        self._test_with_building_java(
            runtime, code_path, expected_files, expected_dependencies, False, self.test_data_path
        )


@skipIf(
    (IS_WINDOWS and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_Java_With_Specified_Architecture(BuildIntegJavaBase):
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
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_building_java_in_container_with_arm64_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime,
            code_path,
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
            (
                "java8.al2",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java8_in_process_with_arm_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime, code_path, expected_files, expected_dependencies, False, self.test_data_path, architecture
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
            (
                "java11",
                USING_GRADLE_PATH,
                EXPECTED_FILES_PROJECT_MANIFEST_GRADLE,
                EXPECTED_GRADLE_DEPENDENCIES,
                "arm64",
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java11_in_process_with_arm_architecture(
        self, runtime, code_path, expected_files, expected_dependencies, architecture
    ):
        self._test_with_building_java(
            runtime, code_path, expected_files, expected_dependencies, False, self.test_data_path, architecture
        )
