import os
import posixpath
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
        container_env_var=None,
        container_env_var_file=None,
        build_image=None,
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

        if container_env_var:
            command_list += ["--container-env-var", container_env_var]

        if container_env_var_file:
            command_list += ["--container-env-var-file", container_env_var_file]

        if build_image:
            command_list += ["--build-image", build_image]

        return command_list

    def verify_docker_container_cleanedup(self, runtime):
        if IS_WINDOWS:
            time.sleep(1)
        docker_client = docker.from_env()
        samcli_containers = docker_client.containers.list(
            all=True, filters={"ancestor": f"public.ecr.aws/sam/build-{runtime}"}
        )
        self.assertFalse(bool(samcli_containers), "Build containers have not been removed")

    def verify_pulling_only_latest_tag(self, runtime):
        docker_client = docker.from_env()
        image_name = f"public.ecr.aws/sam/build-{runtime}"
        images = docker_client.images.list(name=image_name)
        self.assertFalse(
            len(images) == 0,
            f"Image {image_name} was not pulled",
        )
        self.assertFalse(
            len(images) > 1,
            f"Other version of the build image {image_name} was pulled",
        )
        self.assertEqual(f"public.ecr.aws/sam/build-{runtime}:latest", images[0].tags[0])

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


class NestedBuildIntegBase(BuildIntegBase):
    def _verify_build(self, function_full_paths, stack_paths, command_result):
        self._verify_process_code_and_output(command_result, function_full_paths)
        for function_full_path in function_full_paths:
            self._verify_build_artifact(self.default_build_dir, function_full_path)
        for stack_path in stack_paths:
            self._verify_move_template(self.default_build_dir, stack_path)

    def _verify_build_artifact(self, build_dir, function_full_path):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        # full_path is always posix path
        path_components = posixpath.split(function_full_path)
        artifact_path = Path(build_dir, *path_components)
        self.assertTrue(artifact_path.exists())

    def _verify_move_template(self, build_dir, stack_path):
        path_components = posixpath.split(stack_path)
        stack_build_dir_path = Path(build_dir, Path(*path_components), "template.yaml")
        self.assertTrue(stack_build_dir_path.exists())

    def _verify_process_code_and_output(self, command_result, function_full_paths):
        self.assertEqual(command_result.process.returncode, 0)
        # check HelloWorld and HelloMars functions are built in the same build
        for function_full_path in function_full_paths:
            self.assertRegex(
                command_result.stderr.decode("utf-8"),
                f"Building codeuri: .* runtime: .* metadata: .* functions: \\[.*'{function_full_path}'.*\\]",
            )

    def _verify_invoke_built_functions(self, template_path, overrides, function_and_expected):
        for function_identifier, expected in function_and_expected:
            self._verify_invoke_built_function(template_path, function_identifier, overrides, expected)


class IntrinsicIntegBase(BuildIntegBase):
    """
    Currently sam-cli does not have great support for intrinsic functions,
    in this kind of integ tests, there are functions that are buildable but not invocable.
    """

    def _verify_build(self, function_full_paths, layer_full_path, stack_paths, command_result):
        """
        Verify resources have their build artifact folders, stack has their own template.yaml, and command succeeds.
        """
        self._verify_process_code_and_output(command_result, function_full_paths, layer_full_path)
        for function_full_path in function_full_paths:
            self._verify_build_artifact(self.default_build_dir, function_full_path)
        for stack_path in stack_paths:
            self._verify_move_template(self.default_build_dir, stack_path)

    def _verify_build_artifact(self, build_dir, function_full_path):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)
        # full_path is always posix path
        path_components = posixpath.split(function_full_path)
        artifact_path = Path(build_dir, *path_components)
        self.assertTrue(artifact_path.exists())

    def _verify_move_template(self, build_dir, stack_path):
        path_components = posixpath.split(stack_path)
        stack_build_dir_path = Path(build_dir, Path(*path_components), "template.yaml")
        self.assertTrue(stack_build_dir_path.exists())

    def _verify_process_code_and_output(self, command_result, function_full_paths, layer_full_path):
        self.assertEqual(command_result.process.returncode, 0)
        # check HelloWorld and HelloMars functions are built in the same build
        for function_full_path in function_full_paths:
            self.assertRegex(
                command_result.stderr.decode("utf-8"),
                f"Building codeuri: .* runtime: .* metadata: .* functions: \\[.*'{function_full_path}'.*\\]",
            )
        self.assertIn(
            f"Building layer '{layer_full_path}'",
            command_result.stderr.decode("utf-8"),
        )

    def _verify_invoke_built_functions(self, template_path, functions, error_message):
        """
        Invoke the function, if error_message is not None, the invoke should fail.
        """
        for function_logical_id in functions:
            LOG.info("Invoking built function '{}'".format(function_logical_id))

            cmdlist = [
                self.cmd,
                "local",
                "invoke",
                function_logical_id,
                "-t",
                str(template_path),
                "--no-event",
            ]

            process_execute = run_command(cmdlist)
            process_execute.process.wait()

            process_stderr = process_execute.stderr.decode("utf-8")
            if error_message:
                self.assertNotEqual(0, process_execute.process.returncode)
                self.assertIn(error_message, process_stderr)
            else:
                self.assertEqual(0, process_execute.process.returncode)
