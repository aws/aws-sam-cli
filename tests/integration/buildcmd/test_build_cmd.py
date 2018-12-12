import sys
import os
import subprocess
import json
import logging

from parameterized import parameterized

from samcli.yamlhelper import yaml_parse
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

        overrides = {"Runtime": runtime, "CodeUri": "Python"}
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

    def _verify_invoke_built_function(self, template_path, function_logical_id, overrides, expected_result):
        LOG.info("Invoking built function '{}'", function_logical_id)

        cmdlist = [self.cmd, "local", "invoke", function_logical_id, "-t", str(template_path), "--no-event",
                   "--parameter-overrides", overrides]

        process = subprocess.Popen(cmdlist, stdout=subprocess.PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()).strip().decode('utf-8')
        print(process_stdout)
        self.assertEquals(json.loads(process_stdout), expected_result)

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

    def _verify_resource_property(self, template_path, logical_id, property, expected_value):

        with open(template_path, 'r') as fp:
            template_dict = yaml_parse(fp.read())
            self.assertEquals(expected_value, template_dict["Resources"][logical_id]["Properties"][property])

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
        overrides = {"Runtime": runtime, "CodeUri": "Node"}
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

    def _verify_resource_property(self, template_path, logical_id, property, expected_value):

        with open(template_path, 'r') as fp:
            template_dict = yaml_parse(fp.read())
            self.assertEquals(expected_value, template_dict["Resources"][logical_id]["Properties"][property])
