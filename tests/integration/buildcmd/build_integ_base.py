import json
import os
import posixpath
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional
from unittest import TestCase

import docker
import jmespath

from samcli.lib.utils.architecture import X86_64
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from samcli.yamlhelper import yaml_parse
from tests.testing_utils import (
    IS_WINDOWS,
    run_command,
    SKIP_DOCKER_TESTS,
    get_sam_command,
)


class BuildIntegBase(TestCase):
    template: Optional[str] = "template.yaml"

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        integration_dir = Path(__file__).resolve().parents[1]
        cls.test_data_path = str(Path(integration_dir, "testdata", "buildcmd"))
        cls.template_path = str(Path(cls.test_data_path, cls.template)) if cls.template else None

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
        exclude=None,
        region=None,
        hook_name=None,
        beta_features=None,
        build_in_source=None,
        mount_with=None,
    ):
        command_list = [self.cmd, "build"]

        if function_identifier:
            command_list += [function_identifier]

        command_list += ["-t", self.template_path] if self.template_path else []

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

        if mount_with:
            command_list += ["--mount-with", mount_with.value]

        if exclude:
            for f in exclude:
                command_list += ["--exclude", f]

        if region:
            command_list += ["--region", region]

        if beta_features is not None:
            command_list += ["--beta-features"] if beta_features else ["--no-beta-features"]

        if hook_name:
            command_list += ["--hook-name", hook_name]

        if build_in_source is not None:
            command_list += ["--build-in-source"] if build_in_source else ["--no-build-in-source"]

        return command_list

    def verify_docker_container_cleanedup(self, runtime):
        if IS_WINDOWS:
            time.sleep(1)
        docker_client = docker.from_env()
        samcli_containers = docker_client.containers.list(
            all=True, filters={"ancestor": f"{LambdaBuildContainer._IMAGE_URI_PREFIX}-{runtime}"}
        )
        self.assertFalse(bool(samcli_containers), "Build containers have not been removed")

    def get_number_of_created_containers(self):
        if IS_WINDOWS:
            time.sleep(1)
        docker_client = docker.from_env()
        containers = docker_client.containers.list(all=True)
        return len(containers)

    def verify_pulled_image(self, runtime, architecture=X86_64):
        docker_client = docker.from_env()
        image_name = f"{LambdaBuildContainer._IMAGE_URI_PREFIX}-{runtime}"
        images = docker_client.images.list(name=image_name)
        architecture = architecture if architecture and "provided" not in runtime else X86_64
        tag_name = LambdaBuildContainer.get_image_tag(architecture)
        self.assertGreater(
            len(images),
            0,
            f"Image {image_name} was not pulled",
        )
        self.assertIn(
            len(images),
            [1, 2],
            f"Other version of the build image {image_name} was pulled. Currently pulled images: {images}, architecture: {architecture}, tag: {tag_name}",
        )
        image_tag = f"{image_name}:{tag_name}"
        for t in [tag for image in images for tag in image.tags]:
            if t == image_tag:
                # Found, pass
                return
        self.fail(f"{image_tag} was not pulled")

    def _make_parameter_override_arg(self, overrides):
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    def _verify_image_build_artifact(self, template_path, image_function_logical_id, property, image_uri):
        self.assertTrue(template_path.exists(), "Build directory should be created")

        build_dir = template_path.parent
        build_dir_files = os.listdir(str(build_dir))
        self.assertNotIn(image_function_logical_id, build_dir_files)

        # Make sure the template has correct CodeUri for resource
        self._verify_resource_property(str(template_path), image_function_logical_id, property, image_uri)

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
        ]

        if overrides:
            cmdlist += [
                "--parameter-overrides",
                overrides,
            ]

        LOG.info("Running invoke Command: {}".format(cmdlist))

        process_execute = run_command(cmdlist)
        process_execute.process.wait()

        process_stdout = process_execute.stdout.decode("utf-8")
        self.assertEqual(json.loads(process_stdout), expected_result)

    def get_override(self, runtime, code_uri, architecture, handler):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": handler}
        if architecture:
            overrides["Architectures"] = architecture
        return overrides


class DedupBuildIntegBase(BuildIntegBase):
    def _verify_build_and_invoke_functions(self, expected_messages, command_result, overrides):
        self._verify_process_code_and_output(command_result)
        for expected_message in expected_messages:
            expected = f"Hello {expected_message}"
            function_id = f"Hello{expected_message}Function"
            self._verify_build_artifact(self.default_build_dir, function_id)
            if not SKIP_DOCKER_TESTS:
                self._verify_invoke_built_function(self.built_template, function_id, overrides, expected)

    def _verify_build_artifact(self, build_dir, function_logical_id):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertIn("template.yaml", build_dir_files)

        # confirm function logical id is in the built template
        template_dict = {}
        with open(Path(build_dir).joinpath("template.yaml"), "r") as template_file:
            template_dict = yaml_parse(template_file.read())
        self.assertIn(function_logical_id, template_dict.get("Resources", {}).keys())

        # confirm build folder for the function exist in the build directory
        built_folder = (
            template_dict.get("Resources", {}).get(function_logical_id, {}).get("Properties", {}).get("CodeUri")
        )
        if not built_folder:
            built_folder = (
                template_dict.get("Resources", {}).get(function_logical_id, {}).get("Properties", {}).get("ContentUri")
            )
        self.assertIn(built_folder, build_dir_files)

    def _verify_process_code_and_output(self, command_result):
        self.assertEqual(command_result.process.returncode, 0)
        # check HelloWorld and HelloMars functions are built in the same build
        self.assertRegex(
            command_result.stderr.decode("utf-8"),
            "Building codeuri: .* runtime: .* metadata: .* functions: " "HelloWorldFunction, HelloMarsFunction",
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
                f"Building codeuri: .* runtime: .* metadata: .* functions: .*{function_full_path}.*",
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
                f"Building codeuri: .* runtime: .* metadata: .* functions:.*{function_full_path}.*",
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


class BuildIntegRustBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {"bootstrap"}

    def _test_with_rust_cargo_lambda(
        self,
        runtime,
        code_uri,
        handler="bootstap",
        binary=None,
        build_mode=None,
        architecture=None,
        use_container=False,
        expected_invoke_result=None,
    ):
        overrides = self.get_override(runtime, code_uri, architecture, handler)
        if binary:
            overrides["Binary"] = binary
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides, beta_features=True)

        newenv = os.environ.copy()
        if build_mode:
            newenv["SAM_BUILD_MODE"] = build_mode

        run_command(cmdlist, cwd=self.working_dir, env=newenv)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
        )

        if expected_invoke_result and not SKIP_DOCKER_TESTS and architecture == X86_64:
            # ARM64 is not supported yet for local invoke
            self._verify_invoke_built_function(
                self.built_template,
                self.FUNCTION_LOGICAL_ID,
                self._make_parameter_override_arg(overrides),
                expected_invoke_result,
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime, architecture)

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
