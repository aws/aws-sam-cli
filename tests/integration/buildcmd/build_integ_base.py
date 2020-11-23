import os
import uuid
import shutil
import tempfile
import time
import logging
import json
from unittest import TestCase

import docker
import jmespath
from pathlib import Path

from samcli.yamlhelper import yaml_parse
from tests.testing_utils import IS_WINDOWS, run_command

LOG = logging.getLogger(__name__)


class BuildIntegBase(TestCase):
    template = "template.yaml"

    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()
        integration_dir = Path(__file__).resolve().parents[1]
        cls.test_data_path = str(Path(integration_dir, "testdata", "buildcmd"))
        cls.template_path = str(Path(cls.test_data_path, cls.template))

    def setUp(self):
        # To invoke a function created by the build command, we need the built artifacts to be in a
        # location that is shared in Docker. Most temp directories are not shared. Therefore we are
        # using a scratch space within the test folder that is .gitignored. Contents of this folder
        # is also deleted after every test run
        self.scratch_dir = str(Path(__file__).resolve().parent.joinpath(str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.mkdir(self.scratch_dir)

        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)
        self.custom_build_dir = tempfile.mkdtemp(dir=self.scratch_dir)

        self.default_build_dir = Path(self.working_dir, ".aws-sam", "build")
        self.built_template = self.default_build_dir.joinpath("template.yaml")

    def tearDown(self):
        self.custom_build_dir and shutil.rmtree(self.custom_build_dir, ignore_errors=True)
        self.working_dir and shutil.rmtree(self.working_dir, ignore_errors=True)
        self.scratch_dir and shutil.rmtree(self.scratch_dir, ignore_errors=True)

    @classmethod
    def base_command(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(
        self,
        build_dir=None,
        base_dir=None,
        manifest_path=None,
        use_container=None,
        parameter_overrides=None,
        mode=None,
        function_identifier=None,
        debug=False,
        cached=False,
        cache_dir=None,
        parallel=False,
    ):

        command_list = [self.cmd, "build"]

        if function_identifier:
            command_list += [function_identifier]

        command_list += ["-t", self.template_path]

        if parameter_overrides:
            command_list += ["--parameter-overrides", self._make_parameter_override_arg(parameter_overrides)]

        if build_dir:
            command_list += ["-b", build_dir]

        if base_dir:
            command_list += ["-s", base_dir]

        if manifest_path:
            command_list += ["-m", manifest_path]

        if use_container:
            command_list += ["--use-container"]

        if debug:
            command_list += ["--debug"]

        if cached:
            command_list += ["--cached"]

        if cache_dir:
            command_list += ["-cd", cache_dir]

        if parallel:
            command_list += ["--parallel"]

        return command_list

    def verify_docker_container_cleanedup(self, runtime):
        if IS_WINDOWS:
            time.sleep(1)
        docker_client = docker.from_env()
        samcli_containers = docker_client.containers.list(
            all=True, filters={"ancestor": "lambci/lambda:build-{}".format(runtime)}
        )
        self.assertFalse(bool(samcli_containers), "Build containers have not been removed")

    def _make_parameter_override_arg(self, overrides):
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    def _verify_resource_property(self, template_path, logical_id, property, expected_value):

        with open(template_path, "r") as fp:
            template_dict = yaml_parse(fp.read())
            self.assertEqual(
                expected_value, jmespath.search(f"Resources.{logical_id}.Properties.{property}", template_dict)
            )

    def _verify_invoke_built_function(self, template_path, function_logical_id, overrides, expected_result):
        LOG.info("Invoking built function '{}'".format(function_logical_id))

        cmdlist = [
            self.cmd,
            "local",
            "invoke",
            function_logical_id,
            "-t",
            str(template_path),
            "--no-event",
            "--parameter-overrides",
            overrides,
        ]

        process_execute = run_command(cmdlist)
        process_execute.process.wait()

        process_stdout = process_execute.stdout.decode("utf-8")
        self.assertEqual(json.loads(process_stdout), expected_result)


class BuildIntegRubyBase(BuildIntegBase):
    EXPECTED_FILES_GLOBAL_MANIFEST = set()
    EXPECTED_FILES_PROJECT_MANIFEST = {"app.rb"}
    EXPECTED_RUBY_GEM = "aws-record"

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_default_gemfile(self, runtime, use_container, code_uri, relative_path):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": "ignored"}
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command:")
        LOG.info(cmdlist)
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST,
            self.EXPECTED_RUBY_GEM,
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

        self.verify_docker_container_cleanedup(runtime)

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

        ruby_version = None
        ruby_bundled_path = None

        # Walk through ruby version to get to the gem path
        for dirpath, dirname, _ in os.walk(str(resource_artifact_dir.joinpath("vendor", "bundle", "ruby"))):
            ruby_version = dirname
            ruby_bundled_path = Path(dirpath)
            break

        # If Gemfile is in root folder, vendor folder will also be created there
        if ruby_version is None:
            for dirpath, dirname, _ in os.walk(str(Path(self.working_dir).joinpath("vendor", "bundle", "ruby"))):
                ruby_version = dirname
                ruby_bundled_path = Path(dirpath)
                break

        gem_path = ruby_bundled_path.joinpath(ruby_version[0], "gems")

        self.assertTrue(any([True if self.EXPECTED_RUBY_GEM in gem else False for gem in os.listdir(str(gem_path))]))


class DedupBuildIntegBase(BuildIntegBase):
    def _verify_build_and_invoke_functions(self, expected_messages, command_result, overrides):
        self._verify_process_code_and_output(command_result)
        for expected_message in expected_messages:
            expected = f"Hello {expected_message}"
            function_id = f"Hello{expected_message}Function"
            self._verify_build_artifact(self.default_build_dir, function_id)
            self._verify_invoke_built_function(self.built_template, function_id, overrides, expected)

    def _verify_build_artifact(self, build_dir, function_logical_id):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        self.assertIn(function_logical_id, build_dir_files)

    def _verify_process_code_and_output(self, command_result):
        self.assertEqual(command_result.process.returncode, 0)
        # check HelloWorld and HelloMars functions are built in the same build
        self.assertRegex(
            command_result.stderr.decode("utf-8"),
            f"Building codeuri: .* runtime: .* metadata: .* functions: "
            f"\\['HelloWorldFunction', 'HelloMarsFunction'\\]",
        )


class CachedBuildIntegBase(DedupBuildIntegBase):
    def _verify_cached_artifact(self, cache_dir):
        self.assertTrue(cache_dir.exists(), "Cache directory should be created")
