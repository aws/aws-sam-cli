import os
import posixpath
import sys
import uuid
import shutil
import tempfile
import time
import logging
import json
from typing import Optional
from unittest import TestCase

import docker
import jmespath
from pathlib import Path

import pytest
from parameterized import parameterized_class

from samcli.commands.build.utils import MountMode
from samcli.lib.utils import osutils
from samcli.lib.utils.architecture import X86_64, has_runtime_multi_arch_image
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from samcli.yamlhelper import yaml_parse
from tests.testing_utils import (
    IS_WINDOWS,
    run_command,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_MESSAGE,
    SKIP_DOCKER_BUILD,
    get_sam_command,
)

LOG = logging.getLogger(__name__)


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
        self.scratch_dir = str(Path(__file__).resolve().parent.joinpath("tmp", str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.makedirs(self.scratch_dir)

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
        config_file=None,
        save_params=False,
        project_root_dir=None,
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

        if config_file is not None:
            command_list += ["--config-file", config_file]

        if save_params:
            command_list += ["--save-params"]

        if project_root_dir is not None:
            command_list += ["--terraform-project-root-path", project_root_dir]

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
        containers = docker_client.containers.list(all=True, filters={"status": "exited"})
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

        for i in range(5):
            process_execute = run_command(cmdlist)
            process_stdout = process_execute.stdout.decode("utf-8")
            process_stderr = process_execute.stderr.decode("utf-8")
            LOG.info("Local invoke stdout: %s", process_stdout)
            LOG.info("Local invoke stderr: %s", process_stderr)

            if "timed out after" in process_stderr:
                LOG.info("Function timed out, retrying")
                continue

            if json.loads(process_stdout) == expected_result:
                LOG.info("Expected result found, succeeded!")
                # success
                return

        self.fail("Failed to invoke function & get expected result")

    def get_override(self, runtime, code_uri, architecture, handler):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": handler}
        if architecture:
            overrides["Architectures"] = architecture
        return overrides


@pytest.mark.ruby
class BuildIntegRubyBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"app.rb"}
    EXPECTED_RUBY_GEM = "aws-eventstream"

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_default_gemfile(self, runtime, use_container, code_uri, relative_path, architecture=None):
        overrides = self.get_override(runtime, code_uri, architecture, "ignored")
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

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


@pytest.mark.nodejs
class BuildIntegEsbuildBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    # Everything should be minifed to one line and a second line for the sourcemap mapping
    MAX_MINIFIED_LINE_COUNT = 2
    MANIFEST_PATH: Optional[str] = None

    def _test_with_default_package_json(
        self, runtime, use_container, code_uri, expected_files, handler, architecture=None, build_in_source=None
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        overrides = self.get_override(runtime, code_uri, architecture, handler)
        manifest_path = str(Path(self.test_data_path, self.MANIFEST_PATH)) if self.MANIFEST_PATH else None
        cmdlist = self.get_command_list(
            use_container=use_container,
            parameter_overrides=overrides,
            build_in_source=build_in_source,
            manifest_path=manifest_path,
        )
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            expected_files,
        )

        expected = {"body": '{"message":"hello world!"}', "statusCode": 200}
        if not SKIP_DOCKER_TESTS and architecture == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        self._verify_esbuild_properties(self.default_build_dir, self.FUNCTION_LOGICAL_ID, handler)

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime, architecture)

    def _test_with_various_properties(self, overrides):
        overrides = self.get_override(**overrides)
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        run_command(cmdlist, cwd=self.working_dir)

        expected = {"body": '{"message":"hello world!"}', "statusCode": 200}
        if not SKIP_DOCKER_TESTS and overrides["Architectures"] == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        self._verify_esbuild_properties(self.default_build_dir, self.FUNCTION_LOGICAL_ID, overrides["Handler"])

    def _verify_esbuild_properties(self, build_dir, function_logical_id, handler):
        filename = self._extract_filename_from_handler(handler)
        resource_artifact_dir = build_dir.joinpath(function_logical_id)
        self._verify_sourcemap_created(filename, resource_artifact_dir)
        self._verify_function_minified(filename, resource_artifact_dir)

    @staticmethod
    def _extract_filename_from_handler(handler):
        # Takes a handler in the form /a/b/c/file.function and returns file
        return str(Path(handler).stem)

    def _verify_function_minified(self, filename, resource_artifact_dir):
        with open(Path(resource_artifact_dir, f"{filename}.js"), "r") as handler_file:
            x = len(handler_file.readlines())
        self.assertLessEqual(x, self.MAX_MINIFIED_LINE_COUNT)

    def _verify_sourcemap_created(self, filename, resource_artifact_dir):
        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        self.assertIn(f"{filename}.js.map", all_artifacts)

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


@pytest.mark.nodejs
class BuildIntegNodeBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"node_modules", "main.js"}
    EXPECTED_NODE_MODULES = {"minimal-request-promise"}
    CODE_URI = "Node"
    FUNCTION_LOGICAL_ID = "Function"
    TEST_INVOKE = False
    MANIFEST_PATH: Optional[str] = None

    def _test_with_default_package_json(self, runtime, use_container, relative_path, architecture=None):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        overrides = self.get_override(runtime, self.CODE_URI, architecture, "main.lambdaHandler")
        manifest_path = str(Path(self.test_data_path, self.MANIFEST_PATH)) if self.MANIFEST_PATH else None
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
        )

        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir,
            self.FUNCTION_LOGICAL_ID,
            self.EXPECTED_FILES_PROJECT_MANIFEST,
            self.EXPECTED_NODE_MODULES,
        )

        expected = {"body": '{"message":"hello world!"}', "statusCode": 200}
        if not SKIP_DOCKER_TESTS and self.TEST_INVOKE:
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
            )

        self._verify_resource_property(
            str(self.built_template),
            "OtherRelativePathResource",
            "BodyS3Location",
            os.path.relpath(
                os.path.normpath(os.path.join(str(str(relative_path)), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        self._verify_resource_property(
            str(self.built_template),
            "GlueResource",
            "Command.ScriptLocation",
            os.path.relpath(
                os.path.normpath(os.path.join(str(str(relative_path)), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        if use_container:
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

        all_modules = set(os.listdir(str(resource_artifact_dir.joinpath("node_modules"))))
        actual_files = all_modules.intersection(expected_modules)
        self.assertEqual(actual_files, expected_modules)


@pytest.mark.golang
class BuildIntegGoBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {"hello-world"}

    def _test_with_go(self, runtime, code_uri, mode, relative_path, architecture=None, use_container=False):
        overrides = self.get_override(runtime, code_uri, architecture, "hello-world")
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        # Need to pass GOPATH ENV variable to match the test directory when running build
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
                os.path.normpath(os.path.join(str(relative_path), "SomeRelativePath")),
                str(self.default_build_dir),
            ),
        )

        expected = "{'message': 'Hello World'}"
        if not SKIP_DOCKER_TESTS and architecture == X86_64:
            # ARM64 is not supported yet for invoking
            self._verify_invoke_built_function(
                self.built_template, self.FUNCTION_LOGICAL_ID, self._make_parameter_override_arg(overrides), expected
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


@pytest.mark.java
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


@pytest.mark.python
class BuildIntegPythonBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    FUNCTION_LOGICAL_ID = "Function"
    prop = "CodeUri"

    def _test_with_default_requirements(
        self,
        runtime,
        codeuri,
        use_container,
        relative_path,
        do_override=True,
        check_function_only=False,
        architecture=None,
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        overrides = self.get_override(runtime, codeuri, architecture, "main.handler") if do_override else None
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        run_command(cmdlist, cwd=self.working_dir)

        self._verify_built_artifact(
            self.default_build_dir, self.FUNCTION_LOGICAL_ID, self.EXPECTED_FILES_PROJECT_MANIFEST
        )

        if not check_function_only:
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

            self._verify_resource_property(
                str(self.built_template),
                "ExampleNestedStack",
                "TemplateURL",
                "https://s3.amazonaws.com/examplebucket/exampletemplate.yml",
            )

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template,
                self.FUNCTION_LOGICAL_ID,
                self._make_parameter_override_arg(overrides) if do_override else None,
                expected,
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
        self._verify_resource_property(str(template_path), function_logical_id, self.prop, function_logical_id)

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEqual(actual_files, expected_files)

    def _get_python_version(self):
        """
        This method is used to override python version of some of the tests which is run with Makefile
        """
        return "python3.10"


@pytest.mark.provided
class BuildIntegProvidedBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requests", "requirements.txt"}

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_Makefile(
        self, runtime, use_container, manifest, architecture=None, code_uri="Provided", build_in_source=None
    ):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = self.get_override(runtime, code_uri, architecture, "main.handler")
        manifest_path = None
        if manifest:
            manifest_path = os.path.join(self.test_data_path, "Provided", manifest)

        cmdlist = self.get_command_list(
            use_container=use_container,
            parameter_overrides=overrides,
            manifest_path=manifest_path,
            build_in_source=build_in_source,
        )

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


def rust_parameterized_class(cls):
    """
    common class parameterize for rust integration tests
    """
    cls = parameterized_class(
        ("template", "code_uri", "binary", "expected_invoke_result"),
        [
            (
                "template_build_method_rust_single_function.yaml",
                "Rust/single-function",
                None,
                {"req_id": "34", "msg": "Hello World"},
            ),
            (
                "template_build_method_rust_binary.yaml",
                "Rust/multi-binaries",
                "function_a",
                {"req_id": "63", "msg": "Hello FunctionA"},
            ),
            (
                "template_build_method_rust_binary.yaml",
                "Rust/multi-binaries",
                "function_b",
                {"req_id": "99", "msg": "Hello FunctionB"},
            ),
        ],
    )(cls)
    return cls


@pytest.mark.provided
class BuildIntegRustBase(BuildIntegBase):
    FUNCTION_LOGICAL_ID = "Function"
    EXPECTED_FILES_PROJECT_MANIFEST = {"bootstrap"}

    def setUp(self):
        super().setUp()
        # Copy source code to working_dir to allow tests run in parallel, as Cargo Lambda generates artifacts in source code dir
        osutils.copytree(
            Path(self.template_path).parent.joinpath(self.code_uri),
            Path(self.working_dir).joinpath(self.code_uri),
        )
        # copy template path
        tmp_template_path = Path(self.working_dir).joinpath(self.template)
        shutil.copyfile(Path(self.template_path), tmp_template_path)
        self.template_path = str(tmp_template_path)

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
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
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
