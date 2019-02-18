import sys
import os
import subprocess
import logging

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path
from parameterized import parameterized

from .build_integ_base import BuildIntegBase


LOG = logging.getLogger(__name__)


class TestBuildCommand_PythonFunctions(BuildIntegBase):

    EXPECTED_FILES_GLOBAL_MANIFEST = set()
    EXPECTED_FILES_PROJECT_MANIFEST = {'__init__.py', 'main.py', 'numpy',
                                       # 'cryptography',
                                       "jinja2",
                                       'requirements.txt'}

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand([
        ("python2.7", False),
        ("python3.6", False),
        ("python2.7", "use_container"),
        ("python3.6", "use_container"),
    ])
    def test_with_default_requirements(self, runtime, use_container):

        # Don't run test on wrong Python versions
        py_version = self._get_python_version()
        if py_version != runtime:
            self.skipTest("Current Python version '{}' does not match Lambda runtime version '{}'".format(py_version,
                                                                                                          runtime))

        overrides = {"Runtime": runtime, "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(use_container=use_container,
                                        parameter_overrides=overrides)

        LOG.info("Running Command: {}", cmdlist)
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        self._verify_built_artifact(self.default_build_dir, self.FUNCTION_LOGICAL_ID,
                                    self.EXPECTED_FILES_PROJECT_MANIFEST)

        self._verify_resource_property(str(self.built_template),
                                       "OtherRelativePathResource",
                                       "BodyS3Location",
                                       os.path.relpath(
                                           os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                                           str(self.default_build_dir))
                                       )

        expected = {
            "pi": "3.14",
            "jinja": "Hello World"
        }
        self._verify_invoke_built_function(self.built_template,
                                           self.FUNCTION_LOGICAL_ID,
                                           self._make_parameter_override_arg(overrides),
                                           expected)
        self.verify_docker_container_cleanedup(runtime)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files):

        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path),
                                       function_logical_id,
                                       "CodeUri",
                                       function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        print(all_artifacts)
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEquals(actual_files, expected_files)

    def _get_python_version(self):
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


class TestBuildCommand_ErrorCases(BuildIntegBase):

    def test_unsupported_runtime(self):
        overrides = {"Runtime": "unsupportedpython", "CodeUri": "NoThere"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        LOG.info("Running Command: {}", cmdlist)
        process = subprocess.Popen(cmdlist, cwd=self.working_dir, stdout=subprocess.PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()).strip().decode('utf-8')
        self.assertEquals(1, process.returncode)

        self.assertIn("Build Failed", process_stdout)


class TestBuildCommand_NodeFunctions(BuildIntegBase):

    EXPECTED_FILES_GLOBAL_MANIFEST = set()
    EXPECTED_FILES_PROJECT_MANIFEST = {'node_modules', 'main.js'}
    EXPECTED_NODE_MODULES = {'minimal-request-promise'}

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand([
        ("nodejs4.3", False),
        ("nodejs6.10", False),
        ("nodejs8.10", False),
        ("nodejs4.3", "use_container"),
        ("nodejs6.10", "use_container"),
        ("nodejs8.10", "use_container")
    ])
    def test_with_default_package_json(self, runtime, use_container):
        overrides = {"Runtime": runtime, "CodeUri": "Node", "Handler": "ignored"}
        cmdlist = self.get_command_list(use_container=use_container,
                                        parameter_overrides=overrides)

        LOG.info("Running Command: {}", cmdlist)
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        self._verify_built_artifact(self.default_build_dir, self.FUNCTION_LOGICAL_ID,
                                    self.EXPECTED_FILES_PROJECT_MANIFEST, self.EXPECTED_NODE_MODULES)

        self._verify_resource_property(str(self.built_template),
                                       "OtherRelativePathResource",
                                       "BodyS3Location",
                                       os.path.relpath(
                                           os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                                           str(self.default_build_dir))
                                       )
        self.verify_docker_container_cleanedup(runtime)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files, expected_modules):

        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path),
                                       function_logical_id,
                                       "CodeUri",
                                       function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEquals(actual_files, expected_files)

        all_modules = set(os.listdir(str(resource_artifact_dir.joinpath('node_modules'))))
        actual_files = all_modules.intersection(expected_modules)
        self.assertEquals(actual_files, expected_modules)


class TestBuildCommand_RubyFunctions(BuildIntegBase):

    EXPECTED_FILES_GLOBAL_MANIFEST = set()
    EXPECTED_FILES_PROJECT_MANIFEST = {'app.rb'}
    EXPECTED_RUBY_GEM = 'httparty'

    FUNCTION_LOGICAL_ID = "Function"

    @parameterized.expand([
        ("ruby2.5", False),
        ("ruby2.5", "use_container")
    ])
    def test_with_default_gemfile(self, runtime, use_container):
        overrides = {"Runtime": runtime, "CodeUri": "Ruby", "Handler": "ignored"}
        cmdlist = self.get_command_list(use_container=use_container,
                                        parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        self._verify_built_artifact(self.default_build_dir, self.FUNCTION_LOGICAL_ID,
                                    self.EXPECTED_FILES_PROJECT_MANIFEST, self.EXPECTED_RUBY_GEM)

        self._verify_resource_property(str(self.built_template),
                                       "OtherRelativePathResource",
                                       "BodyS3Location",
                                       os.path.relpath(
                                           os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                                           str(self.default_build_dir))
                                       )
        self.verify_docker_container_cleanedup(runtime)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files, expected_modules):

        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path),
                                       function_logical_id,
                                       "CodeUri",
                                       function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEquals(actual_files, expected_files)

        ruby_version = None
        ruby_bundled_path = None

        # Walk through ruby version to get to the gem path
        for dirpath, dirname, _ in os.walk(str(resource_artifact_dir.joinpath('vendor', 'bundle', 'ruby'))):
            ruby_version = dirname
            ruby_bundled_path = Path(dirpath)
            break
        gem_path = ruby_bundled_path.joinpath(ruby_version[0], 'gems')

        self.assertTrue(any([True if self.EXPECTED_RUBY_GEM in gem else False for gem in os.listdir(str(gem_path))]))


class TestBuildCommand_JavaGradle(BuildIntegBase):

    EXPECTED_FILES_PROJECT_MANIFEST = {'aws', 'lib', "META-INF"}
    EXPECTED_DEPENDENCIES = {'annotations-2.1.0.jar', "aws-lambda-java-core-1.1.0.jar"}

    FUNCTION_LOGICAL_ID = "Function"
    USING_GRADLE_PATH = os.path.join("Java", "gradle")
    USING_GRADLEW_PATH = os.path.join("Java", "gradlew")

    @parameterized.expand([
        ("java8", USING_GRADLE_PATH, False),
        ("java8", USING_GRADLEW_PATH, False),
        ("java8", USING_GRADLE_PATH, "use_container"),
        ("java8", USING_GRADLEW_PATH, "use_container"),
    ])
    def test_with_gradle(self, runtime, code_path, use_container):
        overrides = {"Runtime": runtime, "CodeUri": code_path, "Handler": "aws.example.Hello::myHandler"}
        cmdlist = self.get_command_list(use_container=use_container,
                                        parameter_overrides=overrides)

        LOG.info("Running Command: {}".format(cmdlist))
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        self._verify_built_artifact(self.default_build_dir, self.FUNCTION_LOGICAL_ID,
                                    self.EXPECTED_FILES_PROJECT_MANIFEST, self.EXPECTED_DEPENDENCIES)

        self._verify_resource_property(str(self.built_template),
                                       "OtherRelativePathResource",
                                       "BodyS3Location",
                                       os.path.relpath(
                                           os.path.normpath(os.path.join(str(self.test_data_path), "SomeRelativePath")),
                                           str(self.default_build_dir))
                                       )

        expected = "Hello World"
        self._verify_invoke_built_function(self.built_template,
                                           self.FUNCTION_LOGICAL_ID,
                                           self._make_parameter_override_arg(overrides),
                                           expected)

        self.verify_docker_container_cleanedup(runtime)

    def _verify_built_artifact(self, build_dir, function_logical_id, expected_files, expected_modules):

        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

        template_path = build_dir.joinpath("template.yaml")
        resource_artifact_dir = build_dir.joinpath(function_logical_id)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path),
                                       function_logical_id,
                                       "CodeUri",
                                       function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEquals(actual_files, expected_files)

        lib_dir_contents = set(os.listdir(str(resource_artifact_dir.joinpath("lib"))))
        self.assertEquals(lib_dir_contents, expected_modules)
