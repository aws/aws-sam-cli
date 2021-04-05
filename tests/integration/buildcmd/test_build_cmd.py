import re
import shutil
import sys
import os
import logging
import random
from unittest import skipIf
from pathlib import Path
from parameterized import parameterized, parameterized_class
from subprocess import Popen, PIPE, TimeoutExpired

import pytest

from samcli.lib.utils import osutils
from .build_integ_base import (
    BuildIntegBase,
    DedupBuildIntegBase,
    CachedBuildIntegBase,
    BuildIntegRubyBase,
    NestedBuildIntegBase,
    IntrinsicIntegBase,
)
from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    CI_OVERRIDE,
    run_command,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_MESSAGE,
)

LOG = logging.getLogger(__name__)

TIMEOUT = 420  # 7 mins


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_PythonFunctions_Images(BuildIntegBase):
    template = "template_image.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    @parameterized.expand([("3.6", False), ("3.7", False), ("3.8", False)])
    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self, runtime, use_container):
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": "Dockerfile",
            "Tag": f"{random.randint(1,100)}",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)
        run_command(cmdlist, cwd=self.working_dir)

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_PythonFunctions(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand(
        [
            ("python2.7", False),
            ("python3.6", False),
            ("python3.7", False),
            ("python3.8", False),
            ("python2.7", "use_container"),
            ("python3.6", "use_container"),
            ("python3.7", "use_container"),
            ("python3.8", "use_container"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self, runtime, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
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

        self._verify_resource_property(
            str(self.built_template),
            "ExampleNestedStack",
            "TemplateURL",
            "https://s3.amazonaws.com/examplebucket/exampletemplate.yml",
        )

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )
        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

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

    def _get_python_version(self):
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_ErrorCases(BuildIntegBase):
    @pytest.mark.flaky(reruns=3)
    def test_unsupported_runtime(self):
        overrides = {"Runtime": "unsupportedpython", "CodeUri": "Python"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info(cmdlist)
        process_execute = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(1, process_execute.process.returncode)

        self.assertIn("Build Failed", str(process_execute.stdout))


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_NodeFunctions(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"node_modules", "main.js"}
    EXPECTED_NODE_MODULES = {"minimal-request-promise"}

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand(
        [
            ("nodejs10.x", False),
            ("nodejs12.x", False),
            ("nodejs14.x", False),
            ("nodejs10.x", "use_container"),
            ("nodejs12.x", "use_container"),
            ("nodejs14.x", "use_container"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_default_package_json(self, runtime, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": "Node", "Handler": "ignored"}
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

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

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


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_RubyFunctions(BuildIntegRubyBase):
    @parameterized.expand(["ruby2.5", "ruby2.7"])
    @pytest.mark.flaky(reruns=3)
    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    def test_building_ruby_in_container(self, runtime):
        self._test_with_default_gemfile(runtime, "use_container", "Ruby", self.test_data_path)

    @parameterized.expand(["ruby2.5", "ruby2.7"])
    @pytest.mark.flaky(reruns=3)
    def test_building_ruby_in_process(self, runtime):
        self._test_with_default_gemfile(runtime, False, "Ruby", self.test_data_path)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_RubyFunctionsWithGemfileInTheRoot(BuildIntegRubyBase):
    """
    Tests use case where Gemfile will present in the root of the project folder.
    This doesn't apply to containerized build, since it copies only the function folder to the container
    """

    @parameterized.expand([("ruby2.5"), ("ruby2.7")])
    @pytest.mark.flaky(reruns=3)
    def test_building_ruby_in_process_with_root_gemfile(self, runtime):
        self._prepare_application_environment()
        self._test_with_default_gemfile(runtime, False, "RubyWithRootGemfile", self.working_dir)

    def _prepare_application_environment(self):
        """
        Create an application environment where Gemfile will be in the root folder of the app;
        ├── RubyWithRootGemfile
        │   └── app.rb
        ├── Gemfile
        └── template.yaml
        """
        # copy gemfile to the root of the project
        shutil.copyfile(Path(self.template_path).parent.joinpath("Gemfile"), Path(self.working_dir).joinpath("Gemfile"))
        # copy function source code in its folder
        osutils.copytree(
            Path(self.template_path).parent.joinpath("RubyWithRootGemfile"),
            Path(self.working_dir).joinpath("RubyWithRootGemfile"),
        )
        # copy template to the root folder
        shutil.copyfile(Path(self.template_path), Path(self.working_dir).joinpath("template.yaml"))
        # update template path with new location
        self.template_path = str(Path(self.working_dir).joinpath("template.yaml"))


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_Java(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST_GRADLE = {"aws", "lib", "META-INF"}
    EXPECTED_FILES_PROJECT_MANIFEST_MAVEN = {"aws", "lib"}
    EXPECTED_DEPENDENCIES = {"annotations-2.1.0.jar", "aws-lambda-java-core-1.1.0.jar"}

    FUNCTION_LOGICAL_ID = "Function"
    USING_GRADLE_PATH = os.path.join("Java", "gradle")
    USING_GRADLEW_PATH = os.path.join("Java", "gradlew")
    USING_GRADLE_KOTLIN_PATH = os.path.join("Java", "gradle-kotlin")
    USING_MAVEN_PATH = os.path.join("Java", "maven")

    @parameterized.expand(
        [
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_building_java_in_container(self, runtime, code_path, expected_files):
        self._test_with_building_java(runtime, code_path, expected_files, "use_container")

    @parameterized.expand(
        [
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java8", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java8.al2", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java8.al2", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java8_in_process(self, runtime, code_path, expected_files):
        self._test_with_building_java(runtime, code_path, expected_files, False)

    @parameterized.expand(
        [
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_GRADLEW_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_GRADLE_KOTLIN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
            ("java11", USING_MAVEN_PATH, EXPECTED_FILES_PROJECT_MANIFEST_MAVEN),
            ("java11", USING_GRADLE_PATH, EXPECTED_FILES_PROJECT_MANIFEST_GRADLE),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_building_java11_in_process(self, runtime, code_path, expected_files):
        self._test_with_building_java(runtime, code_path, expected_files, False)

    def _test_with_building_java(self, runtime, code_path, expected_files, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": code_path, "Handler": "aws.example.Hello::myHandler"}
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)
        cmdlist += ["--skip-pull-image"]
        if code_path == self.USING_GRADLEW_PATH and use_container and IS_WINDOWS:
            osutils.convert_to_unix_line_ending(os.path.join(self.test_data_path, self.USING_GRADLEW_PATH, "gradlew"))

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, expected_files, self.EXPECTED_DEPENDENCIES
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
            self.verify_pulling_only_latest_tag(runtime)

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


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_Dotnet_cli_package(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {
        "Amazon.Lambda.APIGatewayEvents.dll",
        "HelloWorld.pdb",
        "Amazon.Lambda.Core.dll",
        "HelloWorld.runtimeconfig.json",
        "Amazon.Lambda.Serialization.Json.dll",
        "Newtonsoft.Json.dll",
        "HelloWorld.deps.json",
        "HelloWorld.dll",
    }

    @parameterized.expand(
        [
            ("dotnetcore2.1", "Dotnetcore2.1", None),
            ("dotnetcore3.1", "Dotnetcore3.1", None),
            ("dotnetcore2.1", "Dotnetcore2.1", "debug"),
            ("dotnetcore3.1", "Dotnetcore3.1", "debug"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_dotnetcore(self, runtime, code_uri, mode):
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        LOG.info("Running with SAM_BUILD_MODE={}".format(mode))

        newenv = os.environ.copy()
        if mode:
            newenv["SAM_BUILD_MODE"] = mode

        run_command(cmdlist, cwd=self.working_dir, env=newenv)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
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

    @parameterized.expand([("dotnetcore2.1", "Dotnetcore2.1"), ("dotnetcore3.1", "Dotnetcore3.1")])
    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_must_fail_with_container(self, runtime, code_uri):
        use_container = True
        overrides = {
            "Runtime": runtime,
            "CodeUri": code_uri,
            "Handler": "HelloWorld::HelloWorld.Function::FunctionHandler",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        process_execute = run_command(cmdlist, cwd=self.working_dir)

        # Must error out, because container builds are not supported
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


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_Go_Modules(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {"hello-world"}

    @parameterized.expand([("go1.x", "Go", None), ("go1.x", "Go", "debug")])
    @pytest.mark.flaky(reruns=3)
    def test_with_go(self, runtime, code_uri, mode):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": "hello-world"}
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

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

    @parameterized.expand([("go1.x", "Go")])
    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    @pytest.mark.flaky(reruns=3)
    def test_go_must_fail_with_container(self, runtime, code_uri):
        use_container = True
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": "hello-world"}
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        process_execute = run_command(cmdlist, cwd=self.working_dir)

        # Must error out, because container builds are not supported
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


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_SingleFunctionBuilds(BuildIntegBase):
    template = "many-functions-template.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    @pytest.mark.flaky(reruns=3)
    def test_function_not_found(self):
        overrides = {"Runtime": "python3.7", "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(parameter_overrides=overrides, function_identifier="FunctionNotInTemplate")

        process_execute = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 1)
        self.assertIn("FunctionNotInTemplate not found", str(process_execute.stderr))

    @parameterized.expand(
        [
            ("python3.7", False, "FunctionOne"),
            ("python3.7", "use_container", "FunctionOne"),
            ("python3.7", False, "FunctionTwo"),
            ("python3.7", "use_container", "FunctionTwo"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_build_single_function(self, runtime, use_container, function_identifier):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=function_identifier
        )

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(self.default_build_dir, function_identifier, self.EXPECTED_FILES_PROJECT_MANIFEST)

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, function_identifier, self._make_parameter_override_arg(overrides), expected
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

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

    def _get_python_version(self):
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_LayerBuilds(BuildIntegBase):
    template = "layers-functions-template.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requirements.txt"}
    EXPECTED_LAYERS_FILES_PROJECT_MANIFEST = {"__init__.py", "layer.py", "numpy", "requirements.txt"}

    @parameterized.expand([("python3.7", False, "LayerOne"), ("python3.7", "use_container", "LayerOne")])
    def test_build_single_layer(self, runtime, use_container, layer_identifier):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": runtime, "LayerContentUri": "PyLayer"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        LOG.info("Running Command: {}".format(cmdlist))

        run_command(cmdlist, cwd=self.working_dir)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir,
            layer_identifier,
            self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST,
            "ContentUri",
            "python",
        )

    @parameterized.expand(
        [("makefile", False, "LayerWithMakefile"), ("makefile", "use_container", "LayerWithMakefile")]
    )
    def test_build_layer_with_makefile(self, build_method, use_container, layer_identifier):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": build_method, "LayerMakeContentUri": "PyLayerMake"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        LOG.info("Running Command: {}".format(cmdlist))

        run_command(cmdlist, cwd=self.working_dir)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir,
            layer_identifier,
            self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST,
            "ContentUri",
            "python",
        )

    @parameterized.expand([("python3.7", False, "LayerTwo"), ("python3.7", "use_container", "LayerTwo")])
    def test_build_fails_with_missing_metadata(self, runtime, use_container, layer_identifier):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": runtime, "LayerContentUri": "PyLayer"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        LOG.info("Running Command: {}".format(cmdlist))

        run_command(cmdlist, cwd=self.working_dir)

        self.assertFalse(self.default_build_dir.joinpath(layer_identifier).exists())

    @parameterized.expand([("python3.7", False), ("python3.7", "use_container")])
    def test_build_function_and_layer(self, runtime, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {
            "LayerBuildMethod": runtime,
            "LayerContentUri": "PyLayer",
            "LayerMakeContentUri": "PyLayerMake",
            "Runtime": runtime,
            "CodeUri": "PythonWithLayer",
            "Handler": "main.handler",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))

        run_command(cmdlist, cwd=self.working_dir)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir, "FunctionOne", self.EXPECTED_FILES_PROJECT_MANIFEST, "CodeUri"
        )
        self._verify_built_artifact(
            self.default_build_dir, "LayerOne", self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST, "ContentUri", "python"
        )

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, "FunctionOne", self._make_parameter_override_arg(overrides), expected
            )
        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

    @parameterized.expand([("python3.7", False), ("python3.7", "use_container")])
    def test_build_function_with_dependent_layer(self, runtime, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {
            "LayerBuildMethod": runtime,
            "LayerContentUri": "PyLayer",
            "Runtime": runtime,
            "CodeUri": "PythonWithLayer",
            "Handler": "main.handler",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier="FunctionOne"
        )

        LOG.info("Running Command: {}".format(cmdlist))

        run_command(cmdlist, cwd=self.working_dir)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir, "FunctionOne", self.EXPECTED_FILES_PROJECT_MANIFEST, "CodeUri"
        )
        self._verify_built_artifact(
            self.default_build_dir, "LayerOne", self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST, "ContentUri", "python"
        )

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, "FunctionOne", self._make_parameter_override_arg(overrides), expected
            )
        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

    def _verify_built_artifact(
        self, build_dir, resource_logical_id, expected_files, code_property_name, artifact_subfolder=""
    ):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(resource_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(resource_logical_id, artifact_subfolder)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path), resource_logical_id, code_property_name, resource_logical_id)

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
class TestBuildCommand_ProvidedFunctions(BuildIntegBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.

    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requests", "requirements.txt"}

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand(
        [
            ("provided", False, None),
            ("provided", "use_container", "Makefile-container"),
            ("provided.al2", False, None),
            ("provided.al2", "use_container", "Makefile-container"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_Makefile(self, runtime, use_container, manifest):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": "Provided", "Handler": "main.handler"}
        manifest_path = None
        if manifest:
            manifest_path = os.path.join(self.test_data_path, "Provided", manifest)

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
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
            self.verify_pulling_only_latest_tag(runtime)

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


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithBuildMethod(BuildIntegBase):
    # Test Suite where `BuildMethod` is explicitly specified.

    template = "custom-build-function.yaml"
    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requests", "requirements.txt"}

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand([(False, None, "makefile"), ("use_container", "Makefile-container", "makefile")])
    @pytest.mark.flaky(reruns=3)
    def test_with_makefile_builder_specified_python_runtime(self, use_container, manifest, build_method):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        # runtime is chosen based off current python version.
        runtime = self._get_python_version()
        # Codeuri is still Provided, since that directory has the makefile.
        overrides = {"Runtime": runtime, "CodeUri": "Provided", "Handler": "main.handler", "BuildMethod": build_method}
        manifest_path = None
        if manifest:
            manifest_path = os.path.join(self.test_data_path, "Provided", manifest)

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
        )

        LOG.info("Running Command: {}".format(cmdlist))
        # Built using Makefile for a python project.
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
        )

        expected = "2.23.0"
        # Building was done with a makefile, invoke is checked with the same runtime image.
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

    @parameterized.expand([(False,), ("use_container")])
    @pytest.mark.flaky(reruns=3)
    def test_with_native_builder_specified_python_runtime(self, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        # runtime is chosen based off current python version.
        runtime = self._get_python_version()
        # Codeuri is still Provided, since that directory has the makefile, but it also has the
        # actual manifest file of `requirements.txt`.
        # BuildMethod is set to the same name as of the runtime.
        overrides = {"Runtime": runtime, "CodeUri": "Provided", "Handler": "main.handler", "BuildMethod": runtime}
        manifest_path = os.path.join(self.test_data_path, "Provided", "requirements.txt")

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
        )

        LOG.info("Running Command: {}".format(cmdlist))
        # Built using `native` python-pip builder for a python project.
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
        )

        expected = "2.23.0"
        # Building was done with a `python-pip` builder, invoke is checked with the same runtime image.
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulling_only_latest_tag(runtime)

    @parameterized.expand([(False,), ("use_container")])
    @pytest.mark.flaky(reruns=3)
    def test_with_wrong_builder_specified_python_runtime(self, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        # runtime is chosen based off current python version.
        runtime = self._get_python_version()
        # BuildMethod is set to the ruby2.7, this should cause failure.
        overrides = {"Runtime": runtime, "CodeUri": "Provided", "Handler": "main.handler", "BuildMethod": "ruby2.7"}
        manifest_path = os.path.join(self.test_data_path, "Provided", "requirements.txt")

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
        )

        LOG.info("Running Command: {}".format(cmdlist))
        # This will error out.
        command = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command.process.returncode, 1)
        self.assertEqual(command.stdout.strip(), b"Build Failed")

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

    def _get_python_version(self):
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithDedupBuilds(DedupBuildIntegBase):
    template = "dedup-functions-template.yaml"

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnetcore3.1",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnetcore3.1",
            ),
            (False, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
            # container
            (True, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_dedup_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "FunctionCodeUri": code_uri,
            "Function1Handler": function1_handler,
            "Function2Handler": function2_handler,
            "FunctionRuntime": runtime,
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]

        if not SKIP_DOCKER_TESTS:
            self._verify_build_and_invoke_functions(
                expected_messages, command_result, self._make_parameter_override_arg(overrides)
            )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithDedupImageBuilds(DedupBuildIntegBase):
    template = "dedup-functions-image-template.yaml"

    @parameterized.expand([(True,), (False,)])
    @pytest.mark.flaky(reruns=3)
    def test_dedup_build(self, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Function1Handler": "main.first_function_handler",
            "Function2Handler": "main.second_function_handler",
            "FunctionRuntime": "3.7",
            "DockerFile": "Dockerfile",
            "Tag": f"{random.randint(1,100)}",
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, "HelloWorldFunction", self._make_parameter_override_arg(overrides), "Hello World"
            )
            self._verify_invoke_built_function(
                self.built_template, "HelloMarsFunction", self._make_parameter_override_arg(overrides), "Hello Mars"
            )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithDedupBuildsMakefile(DedupBuildIntegBase):
    template = "dedup-functions-makefile-template.yaml"

    @pytest.mark.flaky(reruns=3)
    def test_dedup_build_makefile(self):
        """
        Build template above in the container and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list()

        LOG.info("Running Command: {}".format(cmdlist))
        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]

        if not SKIP_DOCKER_TESTS:
            self._verify_build_and_invoke_functions(expected_messages, command_result, "")

    def _verify_process_code_and_output(self, command_result):
        """
        Override, because functions should be build individually
        """
        self.assertEqual(command_result.process.returncode, 0)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithCacheBuilds(CachedBuildIntegBase):
    template = "dedup-functions-template.yaml"

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnetcore3.1",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnetcore3.1",
            ),
            (False, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
            # container
            (True, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_cache_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "FunctionCodeUri": code_uri,
            "Function1Handler": function1_handler,
            "Function2Handler": function2_handler,
            "FunctionRuntime": runtime,
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides, cached=True)

        LOG.info("Running Command: %s", cmdlist)
        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]

        if not SKIP_DOCKER_TESTS:
            self._verify_build_and_invoke_functions(
                expected_messages, command_result, self._make_parameter_override_arg(overrides)
            )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestParallelBuilds(DedupBuildIntegBase):
    template = "dedup-functions-template.yaml"

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnetcore3.1",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnetcore3.1",
            ),
            (False, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
            # container
            (True, "Java/gradlew", "aws.example.Hello::myHandler", "aws.example.SecondFunction::myHandler", "java8"),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs14.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.8"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby2.5"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_dedup_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        """
        Build template above and verify that each function call returns as expected
        """
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {
            "FunctionCodeUri": code_uri,
            "Function1Handler": function1_handler,
            "Function2Handler": function2_handler,
            "FunctionRuntime": runtime,
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides, parallel=True)

        LOG.info("Running Command: %s", cmdlist)
        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]

        if not SKIP_DOCKER_TESTS:
            self._verify_build_and_invoke_functions(
                expected_messages, command_result, self._make_parameter_override_arg(overrides)
            )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithInlineCode(BuildIntegBase):
    template = "inline_template.yaml"

    @parameterized.expand(
        [
            (False,),
            ("use_container",),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_inline_not_built(self, use_container):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.7")
            self.verify_pulling_only_latest_tag("python3.7")

    def _verify_built_artifact(self, build_dir):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        codeuri_logical_id = "CodeUriFunction"
        inline_logical_id = "InlineCodeFunction"

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(codeuri_logical_id, build_dir_files)
        self.assertNotIn(inline_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path), codeuri_logical_id, "CodeUri", codeuri_logical_id)
        # Make sure the template has correct InlineCode for resource
        self._verify_resource_property(str(template_path), inline_logical_id, "InlineCode", "def handler(): pass")


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithJsonContainerEnvVars(BuildIntegBase):
    template = "container_env_vars_template.yml"

    @parameterized.expand(
        [
            ("use_container", "env_vars_function.json"),
            ("use_container", "env_vars_parameters.json"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_json_env_vars_passed(self, use_container, env_vars_file):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(
            use_container=use_container, container_env_var_file=self.get_env_file(env_vars_file)
        )

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_env_var(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.7")
            self.verify_pulling_only_latest_tag("python3.7")

    @staticmethod
    def get_env_file(filename):
        test_data_path = Path(__file__).resolve().parents[2].joinpath("integration", "testdata")
        return str(test_data_path.joinpath("buildcmd", filename))

    def _verify_built_env_var(self, build_dir):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("CheckEnvVarsFunction", build_dir_files)

        function_files = os.listdir(str(build_dir.joinpath("CheckEnvVarsFunction")))
        self.assertIn("env_vars_result.txt", function_files)

        output_file = build_dir.joinpath("CheckEnvVarsFunction", "env_vars_result.txt")
        with open(str(output_file), "r", encoding="utf-8") as r:
            actual = r.read()
            self.assertEqual(actual.strip(), "MyVar")


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithInlineContainerEnvVars(BuildIntegBase):
    template = "container_env_vars_template.yml"

    @parameterized.expand(
        [
            ("use_container", "TEST_ENV_VAR=MyVar"),
            ("use_container", "CheckEnvVarsFunction.TEST_ENV_VAR=MyVar"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_inline_env_vars_passed(self, use_container, inline_env_var):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container, container_env_var=inline_env_var)

        LOG.info("Running Command: {}".format(cmdlist))
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_env_var(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.7")
            self.verify_pulling_only_latest_tag("python3.7")

    def _verify_built_env_var(self, build_dir):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("CheckEnvVarsFunction", build_dir_files)

        function_files = os.listdir(str(build_dir.joinpath("CheckEnvVarsFunction")))
        self.assertIn("env_vars_result.txt", function_files)

        output_file = build_dir.joinpath("CheckEnvVarsFunction", "env_vars_result.txt")
        with open(str(output_file), "r", encoding="utf-8") as r:
            actual = r.read()
            self.assertEqual(actual.strip(), "MyVar")


class TestBuildWithNestedStacks(NestedBuildIntegBase):
    # we put the root template in its own directory to test the scenario where codeuri and children templates
    # are not located in the same folder.
    template = os.path.join("nested-parent", "nested-root-template.yaml")

    @parameterized.expand(
        [
            (
                "use_container",
                True,
                True,
            ),
            (
                "use_container",
                False,
                False,
            ),
            (
                False,
                True,
                True,
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_nested_build(self, use_container, cached, parallel):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Runtime": "python3.7",
            "CodeUri": "../Python",  # root stack is one level deeper than the code
            "ChildStackCodeUri": "./Python",  # chidl stack is in the same folder as the code
            "LocalNestedFuncHandler": "main.handler",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, cached=cached, parallel=parallel
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        # make sure functions are deduplicated properly, in stderr they will show up in the same line.
        self.assertRegex(command_result.stderr.decode("utf-8"), r"Building .+'Function2',.+LocalNestedStack/Function2")

        function_full_paths = ["Function", "Function2", "LocalNestedStack/Function1", "LocalNestedStack/Function2"]
        stack_paths = ["", "LocalNestedStack"]
        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                function_full_paths,
                stack_paths,
                command_result,
            )

            overrides = self._make_parameter_override_arg(overrides)
            self._verify_invoke_built_functions(
                self.built_template,
                overrides,
                [
                    # invoking function in root stack using function name
                    ("Function", "Hello World"),
                    # there is only 1 Function1 in these two stacks, so invoking either by name and by full_path are the same
                    ("Function1", {"pi": "3.14"}),
                    ("LocalNestedStack/Function1", {"pi": "3.14"}),
                    # Function2 appears in both stacks and have different handler:
                    # - invoking using function name will match the root stack one by default
                    # - invoking using full path to avoid ambiguity
                    ("Function2", "Hello Mars"),
                    ("LocalNestedStack/Function2", {"pi": "3.14"}),
                ],
            )


@parameterized_class(
    ("template", "use_base_dir"),
    [
        (os.path.join("deep-nested", "template.yaml"), False),
        (os.path.join("base-dir", "template", "template.yaml"), "use_base_dir"),
    ],
)
class TestBuildWithNestedStacks3Level(NestedBuildIntegBase):
    """
    In this template, it has the same structure as .aws-sam/build
    build
        - template.yaml
        - FunctionA
        - ChildStackX
            - template.yaml
            - FunctionB
            - ChildStackY
                - template.yaml
                - FunctionA
                - MyLayerVersion
    """

    template = os.path.join("deep-nested", "template.yaml")

    @pytest.mark.flaky(reruns=3)
    def test_nested_build(self):
        if SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(
            use_container=True,
            cached=True,
            parallel=True,
            base_dir=(os.path.join(self.test_data_path, "base-dir") if self.use_base_dir else None),
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        function_full_paths = [
            "FunctionA",
            "ChildStackX/FunctionB",
            "ChildStackX/ChildStackY/FunctionA",
        ]
        stack_paths = [
            "",
            "ChildStackX",
            "ChildStackX/ChildStackY",
        ]
        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                function_full_paths,
                stack_paths,
                command_result,
            )

            self._verify_invoke_built_functions(
                self.built_template,
                "",
                [
                    ("FunctionA", {"body": '{"hello": "a"}', "statusCode": 200}),
                    ("FunctionB", {"body": '{"hello": "b"}', "statusCode": 200}),
                    ("ChildStackX/FunctionB", {"body": '{"hello": "b"}', "statusCode": 200}),
                    ("ChildStackX/ChildStackY/FunctionA", {"body": '{"hello": "a2"}', "statusCode": 200}),
                ],
            )


@skipIf(IS_WINDOWS, "symlink is not resolved consistently on windows")
class TestBuildWithNestedStacks3LevelWithSymlink(NestedBuildIntegBase):
    """
    In this template, it has the same structure as .aws-sam/build
    build
        - template.yaml
        - child-stack-x-template-symlink.yaml (symlink to ChildStackX/template.yaml)
        - FunctionA
        - ChildStackX
            - template.yaml
            - FunctionB
            - ChildStackY
                - template.yaml
                - FunctionA
                - MyLayerVersion
    """

    template = os.path.join("deep-nested", "template-with-symlink.yaml")

    @pytest.mark.flaky(reruns=3)
    def test_nested_build(self):
        if SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=True, cached=True, parallel=True)

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        function_full_paths = [
            "FunctionA",
            "ChildStackX/FunctionB",
            "ChildStackX/ChildStackY/FunctionA",
            "ChildStackXViaSymlink/FunctionB",
            "ChildStackXViaSymlink/ChildStackY/FunctionA",
        ]
        stack_paths = [
            "",
            "ChildStackX",
            "ChildStackX/ChildStackY",
            "ChildStackXViaSymlink",
            "ChildStackXViaSymlink/ChildStackY",
        ]
        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                function_full_paths,
                stack_paths,
                command_result,
            )

            self._verify_invoke_built_functions(
                self.built_template,
                "",
                [
                    ("FunctionA", {"body": '{"hello": "a"}', "statusCode": 200}),
                    ("FunctionB", {"body": '{"hello": "b"}', "statusCode": 200}),
                    ("ChildStackX/FunctionB", {"body": '{"hello": "b"}', "statusCode": 200}),
                    ("ChildStackX/ChildStackY/FunctionA", {"body": '{"hello": "a2"}', "statusCode": 200}),
                    ("ChildStackXViaSymlink/FunctionB", {"body": '{"hello": "b"}', "statusCode": 200}),
                    ("ChildStackXViaSymlink/ChildStackY/FunctionA", {"body": '{"hello": "a2"}', "statusCode": 200}),
                ],
            )


@parameterized_class(
    ("template", "use_base_dir"),
    [
        (os.path.join("nested-parent", "nested-root-template-image.yaml"), False),
        (os.path.join("base-dir-image", "template", "template.yaml"), "use_base_dir"),
    ],
)
class TestBuildWithNestedStacksImage(NestedBuildIntegBase):

    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    @parameterized.expand(
        [
            (
                "use_container",
                True,
                True,
            ),
            (
                "use_container",
                False,
                False,
            ),
            (
                False,
                True,
                True,
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_nested_build(self, use_container, cached, parallel):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Runtime": "3.7",
            "DockerFile": "Dockerfile",
            "Tag": f"{random.randint(1,100)}",
            "LocalNestedFuncHandler": "main.handler",
        }
        cmdlist = self.get_command_list(
            use_container=use_container,
            parameter_overrides=overrides,
            cached=cached,
            parallel=parallel,
            base_dir=(os.path.join(self.test_data_path, "base-dir-image") if self.use_base_dir else None),
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        stack_paths = ["", "LocalNestedStack"]
        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                [],  # there is no function artifact dirs to check
                stack_paths,
                command_result,
            )

            overrides = self._make_parameter_override_arg(overrides)
            self._verify_invoke_built_functions(
                self.built_template,
                overrides,
                [
                    # invoking function in root stack using function name
                    ("Function", "Hello World"),
                    # there is only 1 Function1 in these two stacks, so invoking either by name and by full_path are the same
                    ("Function1", {"pi": "3.14"}),
                    ("LocalNestedStack/Function1", {"pi": "3.14"}),
                    # Function2 appears in both stacks and have different handler:
                    # - invoking using function name will match the root stack one by default
                    # - invoking using full path to avoid ambiguity
                    ("Function2", "Hello Mars"),
                    ("LocalNestedStack/Function2", {"pi": "3.14"}),
                ],
            )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithCustomBuildImage(BuildIntegBase):
    template = "build_image_function.yaml"

    @parameterized.expand(
        [
            ("use_container", None),
            ("use_container", "amazon/aws-sam-cli-build-image-python3.7:latest"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_custom_build_image_succeeds(self, use_container, build_image):
        if use_container and SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container, build_image=build_image)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        stderr = command_result.stderr
        process_stderr = stderr.strip()

        self._verify_right_image_pulled(build_image, process_stderr)
        self._verify_build_succeeds(self.default_build_dir)

        self.verify_docker_container_cleanedup("python3.7")

    def _verify_right_image_pulled(self, build_image, process_stderr):
        image_name = build_image if build_image is not None else "public.ecr.aws/sam/build-python3.7:latest"
        processed_name = bytes(image_name, encoding="utf-8")
        self.assertIn(
            processed_name,
            process_stderr,
        )

    def _verify_build_succeeds(self, build_dir):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("BuildImageFunction", build_dir_files)


@parameterized_class(
    ("template", "stack_paths", "layer_full_path", "function_full_paths", "invoke_error_message"),
    [
        (
            os.path.join("nested-with-intrinsic-functions", "template-pass-down.yaml"),
            ["", "AppUsingRef", "AppUsingJoin"],
            "MyLayerVersion",
            ["AppUsingRef/FunctionInChild", "AppUsingJoin/FunctionInChild"],
            # Note(xinhol), intrinsic function passed by parameter are resolved as string,
            # therefore it is being treated as an Arn, it is a bug in intrinsic resolver
            "Invalid Layer Arn",
        ),
        (
            os.path.join("nested-with-intrinsic-functions", "template-pass-up.yaml"),
            ["", "ChildApp"],
            "ChildApp/MyLayerVersion",
            ["FunctionInRoot"],
            # for this pass-up use case, since we are not sure whether there are valid local invoke cases out there,
            # so we don't want to block customers from local invoking it.
            None,
        ),
    ],
)
class TestBuildPassingLayerAcrossStacks(IntrinsicIntegBase):
    @pytest.mark.flaky(reruns=3)
    def test_nested_build(self):
        if SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
            cached=True,
            parallel=True,
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                self.function_full_paths,
                self.layer_full_path,
                self.stack_paths,
                command_result,
            )

            self._verify_invoke_built_functions(
                self.built_template, self.function_full_paths, self.invoke_error_message
            )


class TestBuildWithS3FunctionsOrLayers(NestedBuildIntegBase):
    template = "template-with-s3-code.yaml"
    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    @pytest.mark.flaky(reruns=3)
    def test_functions_layers_with_s3_codeuri(self):
        if SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        if not SKIP_DOCKER_TESTS:
            self._verify_build(
                ["ServerlessFunction", "LambdaFunction"],
                [""],  # there is only one stack
                command_result,
            )
            # these two functions are buildable and `sam build` would build it.
            # but since the two functions both depends on layers with s3 uri,
            # sam-cli does support local invoking it but the local invoke is likely
            # to fail due to missing layers. We don't want to introduce breaking
            # change so only a warning is added when `local invoke` is used on such functions.
            # skip the invoke test here because the invoke result is not meaningful.


class TestBuildWithZipFunctionsOrLayers(NestedBuildIntegBase):
    template = "template-with-zip-code.yaml"

    @pytest.mark.flaky(reruns=3)
    def test_functions_layers_with_s3_codeuri(self):
        if SKIP_DOCKER_TESTS:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
        )

        LOG.info("Running Command: %s", cmdlist)
        LOG.info(self.working_dir)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        if not SKIP_DOCKER_TESTS:
            # no functions/layers should be built since they all have zip code/content
            # which are
            self._verify_build(
                [],
                [""],  # there is only one stack
                command_result,
            )
