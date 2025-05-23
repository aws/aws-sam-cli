import logging
import os
import random
import shutil
import sys
from pathlib import Path
from typing import Set
from unittest import skipIf
from uuid import uuid4

import jmespath
import docker
import pytest
from parameterized import parameterized, parameterized_class

from samcli.lib.utils import osutils
from samcli.yamlhelper import yaml_parse
from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    CI_OVERRIDE,
    run_command,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    UpdatableSARTemplate,
)
from tests.integration.buildcmd.build_integ_base import (
    BuildIntegBase,
    DedupBuildIntegBase,
    CachedBuildIntegBase,
    BuildIntegRubyBase,
    NestedBuildIntegBase,
    IntrinsicIntegBase,
    BuildIntegGoBase,
    BuildIntegPythonBase,
)


LOG = logging.getLogger(__name__)

# SAR tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SAR_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class TestBuildingImageTypeLambdaDockerFileFailures(BuildIntegBase):
    template = "template_image.yaml"

    def test_with_invalid_dockerfile_location(self):
        overrides = {
            "Runtime": "3.10",
            "Handler": "handler",
            "DockerFile": "ThisDockerfileDoesNotExist",
            "Tag": uuid4().hex,
        }
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        # confirm build failed
        self.assertEqual(command_result.process.returncode, 1)
        self.assertIn("Cannot locate specified Dockerfile", command_result.stderr.decode())

    def test_with_invalid_dockerfile_definition(self):
        overrides = {
            "Runtime": "3.10",
            "Handler": "handler",
            "DockerFile": "InvalidDockerfile",
            "Tag": uuid4().hex,
        }
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        # confirm build failed
        self.assertEqual(command_result.process.returncode, 1)
        self.assertIn("COPY requires at least two arguments", command_result.stderr.decode())


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class TestLoadingImagesFromArchive(BuildIntegBase):
    template = "template_loadable_image.yaml"

    FUNCTION_LOGICAL_ID = "ImageFunction"

    def test_load_not_an_archive_passthrough(self):
        overrides = {"ImageUri": "./load_image_archive/this_file_does_not_exist.tar.gz"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)

    def test_bad_image_archive_fails(self):
        overrides = {"ImageUri": "./load_image_archive/error.tar.gz"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 1)
        self.assertIn("unexpected EOF", command_result.stderr.decode())

    def test_load_success(self):
        overrides = {"ImageUri": "./load_image_archive/archive.tar.gz"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID,
            "ImageUri",
            "sha256:81d2ff8422e3a78dc0c1eff53d8e46f5666a801b17b5607a920860c2d234f9d0",
        )


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    ((not RUN_BY_CANARY) or (IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@parameterized_class(
    ("template", "prop"),
    [
        ("template_local_prebuilt_image.yaml", "ImageUri"),
        ("template_cfn_local_prebuilt_image.yaml", "Code.ImageUri"),
    ],
)
class TestSkipBuildingFunctionsWithLocalImageUri(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST: Set[str] = set()

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    @parameterized.expand(["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"])
    def test_with_default_requirements(self, runtime):
        _tag = uuid4().hex
        image_uri = f"func:{_tag}"
        docker_client = docker.from_env()
        docker_client.images.build(
            path=str(Path(self.test_data_path, "PythonImage")),
            dockerfile="Dockerfile",
            buildargs={"BASE_RUNTIME": runtime},
            tag=image_uri,
        )
        overrides = {
            "ImageUri": image_uri,
            "Handler": "main.handler",
        }
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            self.prop,
            {"Ref": "ImageUri"},
        )

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    ((not RUN_BY_CANARY) or (IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@parameterized_class(
    ("template", "SKIPPED_FUNCTION_LOGICAL_ID", "src_code_path", "src_code_prop", "metadata_key"),
    [
        ("template_function_flagged_to_skip_build.yaml", "SkippedFunction", "PreBuiltPython", "CodeUri", None),
        ("template_cfn_function_flagged_to_skip_build.yaml", "SkippedFunction", "PreBuiltPython", "Code", None),
        (
            "cdk_v1_synthesized_template_python_function_construct.json",
            "SkippedFunctionDA0220D7",
            "asset.7023fd47c81480184154c6e0e870d6920c50e35d8fae977873016832e127ded9",
            None,
            "aws:asset:path",
        ),
        (
            "cdk_v1_synthesized_template_function_construct_with_skip_build_metadata.json",
            "SkippedFunctionDA0220D7",
            "asset.7023fd47c81480184154c6e0e870d6920c50e35d8fae977873016832e127ded9",
            None,
            "aws:asset:path",
        ),
        (
            "cdk_v2_synthesized_template_python_function_construct.json",
            "SkippedFunctionDA0220D7",
            "asset.7023fd47c81480184154c6e0e870d6920c50e35d8fae977873016832e127ded9",
            None,
            "aws:asset:path",
        ),
        (
            "cdk_v2_synthesized_template_function_construct_with_skip_build_metadata.json",
            "RandomSpaceFunction4F8564D0",
            "asset.7023fd47c81480184154c6e0e870d6920c50e35d8fae977873016832e127ded9",
            None,
            "aws:asset:path",
        ),
    ],
)
class TestSkipBuildingFlaggedFunctions(BuildIntegPythonBase):
    template = "template_cfn_function_flagged_to_skip_build.yaml"
    SKIPPED_FUNCTION_LOGICAL_ID = "SkippedFunction"
    src_code_path = "PreBuiltPython"
    src_code_prop = "Code"
    metadata_key = None

    def test_with_default_requirements(self):
        self._validate_skipped_built_function(
            self.default_build_dir,
            self.SKIPPED_FUNCTION_LOGICAL_ID,
            self.test_data_path,
            self.src_code_path,
            self.src_code_prop,
            self.metadata_key,
        )

    def _validate_skipped_built_function(
        self, build_dir, skipped_function_logical_id, relative_path, src_code_path, src_code_prop, metadata_key
    ):
        cmdlist = self.get_command_list()

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))
        self.assertNotIn(skipped_function_logical_id, build_dir_files)

        expected_value = os.path.relpath(
            os.path.normpath(os.path.join(str(relative_path), src_code_path)),
            str(self.default_build_dir),
        )

        with open(self.built_template, "r") as fp:
            template_dict = yaml_parse(fp.read())
            if src_code_prop:
                self.assertEqual(
                    expected_value,
                    jmespath.search(
                        f"Resources.{skipped_function_logical_id}.Properties.{src_code_prop}", template_dict
                    ),
                )
            if metadata_key:
                metadata = jmespath.search(f"Resources.{skipped_function_logical_id}.Metadata", template_dict)
                metadata = metadata if metadata else {}
                self.assertEqual(expected_value, metadata.get(metadata_key, ""))
        expected = "Hello World"
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, skipped_function_logical_id, self._make_parameter_override_arg({}), expected
            )


@pytest.mark.ruby
class TestBuildCommand_RubyFunctions(BuildIntegRubyBase):
    @parameterized.expand([(False,), ("use_container",)])
    def test_building_ruby_3_2(self, use_container):
        if use_container and SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        self._test_with_default_gemfile("ruby3.2", use_container, "Ruby", self.test_data_path)

    @parameterized.expand([("ruby3.3",), ("ruby3.4",)])
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_building_ruby_al2023(self, runtime):
        self._test_with_default_gemfile(runtime, "use_container", "Ruby", self.test_data_path)


class TestBuildCommand_RubyFunctions_With_Architecture(BuildIntegRubyBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand([(False,), ("use_container",)])
    def test_building_ruby_3_2(self, use_container):
        if use_container and SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_gemfile("ruby3.2", use_container, "Ruby32", self.test_data_path, "x86_64")

    @parameterized.expand(
        [
            ("ruby3.3", "Ruby33", False),
            ("ruby3.3", "Ruby33", True),
            # ("ruby3.4", "Ruby34", False), # TODO: Try to make this work in AppVeyor (windows-al2023)
            ("ruby3.4", "Ruby34", True),
        ]
    )
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    @pytest.mark.al2023
    def test_building_ruby_al2023(self, runtime, codeuri, use_container):
        self._test_with_default_gemfile(runtime, use_container, codeuri, self.test_data_path, "x86_64")


class TestBuildCommand_RubyFunctionsWithGemfileInTheRoot(BuildIntegRubyBase):
    """
    Tests use case where Gemfile will present in the root of the project folder.
    This doesn't apply to containerized build, since it copies only the function folder to the container
    """

    @parameterized.expand([("ruby3.2",), ("ruby3.3",), ("ruby3.4",)])
    def test_building_ruby_in_process_with_root_gemfile(self, runtime):
        self._prepare_application_environment(runtime)
        self._test_with_default_gemfile(runtime, False, "RubyWithRootGemfile", self.working_dir)

    def _prepare_application_environment(self, runtime):
        """
        Create an application environment where Gemfile will be in the root folder of the app;
        ├── .ruby-version
        ├── RubyWithRootGemfile
        │   └── app.rb
        ├── Gemfile
        └── template.yaml
        """
        # copy .ruby-version to the root of the project
        ruby_runtime_path = runtime.replace(".", "").title()  # ruby3.X to Ruby3X
        shutil.copyfile(
            Path(self.template_path).parent.joinpath(ruby_runtime_path, ".ruby-version"),
            Path(self.working_dir).joinpath(".ruby-version"),
        )
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


class TestBuildCommand_Go_Modules(BuildIntegGoBase):
    @parameterized.expand([("go1.x", "Go", None, False), ("go1.x", "Go", "debug", True)])
    def test_building_go(self, runtime, code_uri, mode, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        self._test_with_go(runtime, code_uri, mode, self.test_data_path, use_container=use_container)


class TestBuildCommand_Go_Modules_With_Specified_Architecture(BuildIntegGoBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("go1.x", "Go", None, "x86_64"),
        ]
    )
    def test_building_go(self, runtime, code_uri, mode, architecture):
        self._test_with_go(runtime, code_uri, mode, self.test_data_path, architecture)

    @parameterized.expand([("go1.x", "Go", "unknown_architecture")])
    def test_go_must_fail_with_unknown_architecture(self, runtime, code_uri, architecture):
        overrides = {"Runtime": runtime, "CodeUri": code_uri, "Handler": "hello-world", "Architectures": architecture}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        process_execute = run_command(cmdlist, cwd=self.working_dir)

        # Must error out, because container builds are not supported
        self.assertEqual(process_execute.process.returncode, 1)


class TestBuildCommand_SingleFunctionBuilds(BuildIntegBase):
    template = "many-functions-template.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
        "numpy",
        # 'cryptography',
        "requirements.txt",
    }

    def test_function_not_found(self):
        overrides = {"Runtime": "python3.11", "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(parameter_overrides=overrides, function_identifier="FunctionNotInTemplate")

        process_execute = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 1)
        self.assertIn("FunctionNotInTemplate not found", str(process_execute.stderr))

    @parameterized.expand(
        [
            ("python3.11", False, "FunctionOne"),
            ("python3.11", "use_container", "FunctionOne"),
            ("python3.11", False, "FunctionTwo"),
            ("python3.11", "use_container", "FunctionTwo"),
        ]
    )
    def test_build_single_function(self, runtime, use_container, function_identifier):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": runtime, "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=function_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_artifact(self.default_build_dir, function_identifier, self.EXPECTED_FILES_PROJECT_MANIFEST)

        expected = {"pi": "3.14"}
        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template, function_identifier, self._make_parameter_override_arg(overrides), expected
            )

        if use_container:
            self.verify_docker_container_cleanedup(runtime)
            self.verify_pulled_image(runtime)

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
class TestBuildCommand_ExcludeResources(BuildIntegBase):
    template = "many-more-functions-template.yaml"

    @parameterized.expand(
        [
            ((), None),
            (("FunctionOne",), None),
            (("FunctionThree",), None),
            (("FunctionOne",), "FunctionOne"),
            (("FunctionOne",), "FunctionTwo"),
            (("FunctionTwo", "FunctionThree")),
        ]
    )
    def test_build_without_resources(self, excluded_resources, function_identifier):
        overrides = {"Runtime": "python3.12", "CodeUri": "Python", "Handler": "main.handler"}
        cmdlist = self.get_command_list(
            parameter_overrides=overrides, function_identifier=function_identifier, exclude=excluded_resources
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_resources_excluded(self.default_build_dir, excluded_resources, function_identifier)

    def _verify_resources_excluded(self, build_dir, excluded_resources, function_identifier):
        self.assertTrue(build_dir.exists(), "Build directory should be created")

        build_dir_files = os.listdir(str(build_dir))

        if function_identifier is not None and function_identifier in excluded_resources:
            self.assertIn(function_identifier, build_dir_files)  # If building 1 and excluding it, build anyway
        else:
            for resource in excluded_resources:
                self.assertNotIn(resource, build_dir_files)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_LayerBuilds(BuildIntegBase):
    template = "layers-functions-template.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {"__init__.py", "main.py", "requirements.txt"}
    EXPECTED_LAYERS_FILES_PROJECT_MANIFEST = {"__init__.py", "layer.py", "numpy", "requirements.txt"}

    EXPECTED_LAYERS_FILES_NO_COMPATIBLE_RUNTIMES = {"__init__.py", "layer.py", "requirements.txt"}

    @parameterized.expand(
        [
            ("python3.12", False, "LayerOne", "ContentUri"),
            ("python3.12", "use_container", "LayerOne", "ContentUri"),
            ("python3.12", False, "LambdaLayerOne", "Content"),
            ("python3.12", "use_container", "LambdaLayerOne", "Content"),
        ]
    )
    def test_build_single_layer(self, runtime, use_container, layer_identifier, content_property):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": runtime, "LayerContentUri": "PyLayer"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir,
            layer_identifier,
            self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST,
            content_property,
            "python",
        )

    @parameterized.expand(
        [("makefile", False, "LayerWithMakefile"), ("makefile", "use_container", "LayerWithMakefile")]
    )
    def test_build_layer_with_makefile(self, build_method, use_container, layer_identifier):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": build_method, "LayerMakeContentUri": "PyLayerMake"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir,
            layer_identifier,
            self.EXPECTED_LAYERS_FILES_PROJECT_MANIFEST,
            "ContentUri",
            "python",
        )

    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_build_layer_with_makefile_no_compatible_runtimes(self):
        build_method = "makefile"
        use_container = True
        layer_identifier = "LayerWithMakefileNoCompatibleRuntimes"

        overrides = {"LayerBuildMethod": build_method, "LayerMakeContentUri": "PyLayerMake"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        LOG.info("Default build dir: %s", self.default_build_dir)
        self._verify_built_artifact(
            self.default_build_dir,
            layer_identifier,
            self.EXPECTED_LAYERS_FILES_NO_COMPATIBLE_RUNTIMES,
            "ContentUri",
            "random",
        )

    @parameterized.expand(
        [("makefile", False), ("makefile", "use_container"), ("python3.9", False), ("python3.9", "use_container")]
    )
    def test_build_layer_with_architecture_not_compatible(self, build_method, use_container):
        # The BuildArchitecture is not one of the listed CompatibleArchitectures
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        layer_identifier = "LayerWithNoCompatibleArchitectures"

        overrides = {
            "LayerBuildMethod": build_method,
            "LayerMakeContentUri": "PyLayerMake",
            "LayerBuildArchitecture": "x86_64",
            "LayerCompatibleArchitecture": "arm64",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        # Capture warning
        self.assertIn(
            f"Layer '{layer_identifier}' has BuildArchitecture x86_64, which is not listed in CompatibleArchitectures",
            str(command_result.stderr.decode("utf-8")),
        )
        # Build should still succeed
        self.assertEqual(command_result.process.returncode, 0)

    @parameterized.expand([("python3.11", False), ("python3.11", "use_container")])
    def test_build_arch_no_compatible_arch(self, runtime, use_container):
        # BuildArchitecture is present, but CompatibleArchitectures section is missing
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        layer_identifier = "LayerWithBuildArchButNoCompatibleArchs"

        overrides = {
            "LayerBuildMethod": runtime,
            "LayerMakeContentUri": "PyLayer",
            "LayerBuildArchitecture": "arm64",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        # Capture warning
        self.assertIn(
            f"Layer '{layer_identifier}' has BuildArchitecture arm64, which is not listed in CompatibleArchitectures",
            str(command_result.stderr),
        )
        # Build should still succeed
        self.assertEqual(command_result.process.returncode, 0)

    @parameterized.expand([("python3.11", False), ("python3.11", "use_container")])
    def test_compatible_arch_no_build_arch(self, runtime, use_container):
        # CompatibleArchitectures is present, but BuildArchitecture section is missing
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        layer_identifier = "LayerWithCompatibleArchsButNoBuildArch"

        overrides = {
            "LayerBuildMethod": runtime,
            "LayerMakeContentUri": "PyLayer",
            "LayerCompatibleArchitecture": "arm64",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        # Capture warning
        self.assertIn(
            f"Layer '{layer_identifier}' has BuildArchitecture x86_64, which is not listed in CompatibleArchitectures",
            str(command_result.stderr),
        )
        # Build should still succeed
        self.assertEqual(command_result.process.returncode, 0)

    def test_build_layer_with_makefile_with_fake_build_architecture(self):
        build_method = "makefile"
        use_container = False

        # Re-use the same test Layer, this time with just a bad BuildArchitecture
        layer_identifier = "LayerWithNoCompatibleArchitectures"

        overrides = {
            "LayerBuildMethod": build_method,
            "LayerMakeContentUri": "PyLayerMake",
            "LayerBuildArchitecture": "fake",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        # Capture warning
        self.assertIn(
            "`fake` in Layer `LayerWithNoCompatibleArchitectures` is not a valid architecture",
            str(command_result.stderr),
        )
        # Build should still succeed
        self.assertEqual(command_result.process.returncode, 0)

    @parameterized.expand([("python3.12", False, "LayerTwo"), ("python3.12", "use_container", "LayerTwo")])
    def test_build_fails_with_missing_metadata(self, runtime, use_container, layer_identifier):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"LayerBuildMethod": runtime, "LayerContentUri": "PyLayer"}
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier=layer_identifier
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 1)
        self.assertFalse(self.default_build_dir.joinpath(layer_identifier).exists())

    @parameterized.expand([False, "use_container"])
    def test_function_build_succeeds_with_referenced_layer(self, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {"Runtime": "python3.11", "CodeUri": "Python"}

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, function_identifier="FunctionTwo"
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

    @parameterized.expand([("python3.12", False), ("python3.12", "use_container")])
    def test_build_function_and_layer(self, runtime, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

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
            self.verify_pulled_image(runtime)

    @parameterized.expand([("python3.12", False), ("python3.12", "use_container")])
    def test_build_function_with_dependent_layer(self, runtime, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

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
            self.verify_pulled_image(runtime)

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
    def test_with_makefile_builder_specified_python_runtime(self, use_container, manifest, build_method):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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

        # Built using Makefile for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

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
            self.verify_pulled_image(runtime)

    @parameterized.expand([(False,), ("use_container")])
    def test_with_native_builder_specified_python_runtime(self, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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

        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

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
            self.verify_pulled_image(runtime)

    @parameterized.expand([(False,), ("use_container")])
    def test_with_wrong_builder_specified_python_runtime(self, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        # runtime is chosen based off current python version.
        runtime = self._get_python_version()
        # BuildMethod is set to the java17, this should cause failure.
        overrides = {"Runtime": runtime, "CodeUri": "Provided", "Handler": "main.handler", "BuildMethod": "java17"}
        manifest_path = os.path.join(self.test_data_path, "Provided", "requirements.txt")

        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, manifest_path=manifest_path
        )

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
# remove following parameterized_class when BuildImprovements22 experimental flag is removed
@parameterized_class(("beta_features",), [(True,), (False,)])
class TestBuildWithDedupBuilds(DedupBuildIntegBase):
    template = "dedup-functions-template.yaml"
    beta_features = False  # parameterized

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnet6",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnet6",
            ),
            (
                False,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
            # container
            (
                True,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
        ]
    )
    def test_dedup_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, beta_features=self.beta_features
        )

        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]

        self._verify_build_and_invoke_functions(
            expected_messages, command_result, self._make_parameter_override_arg(overrides)
        )


@skipIf(
    (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithDedupImageBuilds(DedupBuildIntegBase):
    template = "dedup-functions-image-template.yaml"

    def test_dedup_build(self):
        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Function1Handler": "main.first_function_handler",
            "Function2Handler": "main.second_function_handler",
            "FunctionRuntime": "3.11",
            "DockerFile": "Dockerfile",
            "Tag": f"{random.randint(1,100)}",
        }
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

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
# remove following parameterized_class when BuildImprovements22 experimental flag is removed
@parameterized_class(("beta_features",), [(True,), (False,)])
class TestBuildWithDedupBuildsMakefile(DedupBuildIntegBase):
    template = "dedup-functions-makefile-template.yaml"
    beta_features = False  # parameterized

    def test_dedup_build_makefile(self):
        """
        Build template above in the container and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(beta_features=self.beta_features)

        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]
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
# remove following parameterized_class when BuildImprovements22 experimental flag is removed
@parameterized_class(("beta_features",), [(True,), (False,)])
class TestBuildWithCacheBuilds(CachedBuildIntegBase):
    template = "dedup-functions-template.yaml"
    beta_features = False  # parameterized

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnet6",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnet6",
            ),
            (
                False,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
            # container
            (
                True,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
        ]
    )
    def test_cache_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
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
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, cached=True, beta_features=self.beta_features
        )

        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]
        self._verify_build_and_invoke_functions(
            expected_messages, command_result, self._make_parameter_override_arg(overrides)
        )

    def test_no_cached_override_build(self):
        overrides = {
            "FunctionCodeUri": "Python",
            "Function1Handler": "main.first_function_handler",
            "Function2Handler": "main.second_function_handler",
            "FunctionRuntime": "python3.11",
        }
        config_file = str(Path(self.test_data_path).joinpath("samconfig_no_cached.toml"))
        cmdlist = self.get_command_list(parameter_overrides=overrides, cached=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(
            "Running PythonPipBuilder:ResolveDependencies" in str(command_result.stderr)
            and "Running PythonPipBuilder:CopySource" in str(command_result.stderr),
            "Non-cached build should have been run",
        )
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        cmdlist.extend(["--config-file", config_file])
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertRegex(
            str(command_result.stderr),
            "Manifest is not changed for .* running incremental build",
            "Should have built using cache",
        )
        cmdlist.extend(["--no-cached"])
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(
            "Running PythonPipBuilder:ResolveDependencies" in str(command_result.stderr)
            and "Running PythonPipBuilder:CopySource" in str(command_result.stderr),
            "Non-cached build should have been run",
        )

    @skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
    def test_cached_build_with_env_vars(self):
        """
        Build 2 times to verify that second time hits the cached build
        """
        overrides = {
            "FunctionCodeUri": "Python",
            "Function1Handler": "main.first_function_handler",
            "Function2Handler": "main.second_function_handler",
            "FunctionRuntime": "python3.11",
        }
        cmdlist = self.get_command_list(
            use_container=True, parameter_overrides=overrides, cached=True, container_env_var="FOO=BAR"
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(
            "Cache is invalid, running build and copying resources for following functions"
            in command_result.stderr.decode("utf-8")
        )

        LOG.info("Re-Running Command (valid cache should exist)")
        command_result_with_cache = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result_with_cache.process.returncode, 0)

        self.assertTrue(
            "Valid cache found, copying previously built resources for following functions"
            in command_result_with_cache.stderr.decode("utf-8")
        )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestRepeatedBuildHitsCache(BuildIntegBase):
    # Use template containing both functions and layers
    template = "layers-functions-template.yaml"

    @parameterized.expand([(True,), (False,)])
    def test_repeated_cached_build_hits_cache(self, use_container):
        """
        Build 2 times to verify that second time hits the cached build
        """
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        parameter_overrides = {
            "LayerContentUri": "PyLayer",
            "LayerBuildMethod": "python3.12",
            "CodeUri": "Python",
            "Handler": "main.handler",
            "Runtime": "python3.12",
            "LayerMakeContentUri": "PyLayerMake",
        }

        cmdlist = self.get_command_list(
            use_container=use_container,
            parameter_overrides=parameter_overrides,
            cached=True,
            container_env_var="FOO=BAR" if use_container else None,
        )

        cache_invalid_output_use_container = "Cache is invalid, running build and copying resources "
        cache_valid_output_use_container = "Valid cache found, copying previously built resources "

        cache_invalid_output_no_container = "Manifest file is changed"
        cache_valid_output_no_container = "Manifest is not changed"

        cache_invalid_output, cache_valid_output = (
            (cache_invalid_output_use_container, cache_valid_output_use_container)
            if use_container
            else (cache_invalid_output_no_container, cache_valid_output_no_container)
        )

        LOG.info("Running Command (cache should be invalid)")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(cache_invalid_output in command_result.stderr.decode("utf-8"))
        self.assertFalse(cache_valid_output in command_result.stderr.decode("utf-8"))

        LOG.info("Re-Running Command (valid cache should exist)")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        self.assertFalse(cache_invalid_output in command_result.stderr.decode("utf-8"))
        self.assertTrue(cache_valid_output in command_result.stderr.decode("utf-8"))


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
# remove following parameterized_class when BuildImprovements22 experimental flag is removed
@parameterized_class(("beta_features",), [(True,), (False,)])
class TestParallelBuilds(DedupBuildIntegBase):
    template = "dedup-functions-template.yaml"
    beta_features = False  # parameterized

    @parameterized.expand(
        [
            # in process
            (
                False,
                "Dotnet6",
                "HelloWorld::HelloWorld.FirstFunction::FunctionHandler",
                "HelloWorld::HelloWorld.SecondFunction::FunctionHandler",
                "dotnet6",
            ),
            (
                False,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (False, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (False, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (False, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
            # container
            (
                True,
                "Java/gradlew/8",
                "aws.example.Hello::myHandler",
                "aws.example.SecondFunction::myHandler",
                "java8.al2",
            ),
            (True, "Node", "main.lambdaHandler", "main.secondLambdaHandler", "nodejs20.x"),
            (True, "Python", "main.first_function_handler", "main.second_function_handler", "python3.9"),
            (True, "Ruby", "app.lambda_handler", "app.second_lambda_handler", "ruby3.4"),
        ]
    )
    def test_dedup_build(self, use_container, code_uri, function1_handler, function2_handler, runtime):
        """
        Build template above and verify that each function call returns as expected
        """
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        overrides = {
            "FunctionCodeUri": code_uri,
            "Function1Handler": function1_handler,
            "Function2Handler": function2_handler,
            "FunctionRuntime": runtime,
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, parallel=True, beta_features=self.beta_features
        )

        # Built using `native` python-pip builder for a python project.
        command_result = run_command(cmdlist, cwd=self.working_dir)

        expected_messages = ["World", "Mars"]
        self._verify_build_and_invoke_functions(
            expected_messages, command_result, self._make_parameter_override_arg(overrides)
        )


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
# remove following parameterized_class when BuildImprovements22 experimental flag is removed
@parameterized_class(("beta_features",), [(True,), (False,)])
class TestParallelBuildsJavaWithLayers(DedupBuildIntegBase):
    template = "template-java-maven-with-layers.yaml"
    beta_features = False  # parameterized

    def test_dedup_build(self):
        """
        Build template above and verify that each function call returns as expected
        """

        cmdlist = self.get_command_list(parallel=True, beta_features=self.beta_features)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        self._verify_build_artifact(self.default_build_dir, "HelloWorldFunction")
        self._verify_build_artifact(self.default_build_dir, "HelloWorldLayer")

        if not SKIP_DOCKER_TESTS:
            self._verify_invoke_built_function(
                self.built_template,
                "HelloWorldFunction",
                None,
                "hello world. sum is 12.",
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
    def test_inline_not_built(self, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_artifact(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.12")
            self.verify_pulled_image("python3.12")

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
    def test_json_env_vars_passed(self, use_container, env_vars_file):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(
            use_container=use_container, container_env_var_file=self.get_env_file(env_vars_file)
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_env_var(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.12")
            self.verify_pulled_image("python3.12")

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
    def test_inline_env_vars_passed(self, use_container, inline_env_var):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container, container_env_var=inline_env_var)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_built_env_var(self.default_build_dir)

        if use_container:
            self.verify_docker_container_cleanedup("python3.12")
            self.verify_pulled_image("python3.12")

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
    def test_nested_build(self, use_container, cached, parallel):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Runtime": "python3.11",
            "CodeUri": "../Python",  # root stack is one level deeper than the code
            "ChildStackCodeUri": "./Python",  # chidl stack is in the same folder as the code
            "LocalNestedFuncHandler": "main.handler",
        }
        cmdlist = self.get_command_list(
            use_container=use_container, parameter_overrides=overrides, cached=cached, parallel=parallel
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)

        # make sure functions are deduplicated properly, in stderr they will show up in the same line.
        self.assertRegex(command_result.stderr.decode("utf-8"), r"Building .+Function2,.+LocalNestedStack/Function2")

        function_full_paths = ["Function", "Function2", "LocalNestedStack/Function1", "LocalNestedStack/Function2"]
        stack_paths = ["", "LocalNestedStack"]

        self._verify_build(
            function_full_paths,
            stack_paths,
            command_result,
        )

        if not SKIP_DOCKER_TESTS:
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

    def test_nested_build(self):
        if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(
            use_container=True,
            cached=True,
            parallel=True,
            base_dir=(os.path.join(self.test_data_path, "base-dir") if self.use_base_dir else None),
        )

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

        self._verify_build(
            function_full_paths,
            stack_paths,
            command_result,
        )

        if not SKIP_DOCKER_TESTS:
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

    def test_nested_build(self):
        if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(
            use_container=True, cached=True, parallel=True, build_dir=str(self.default_build_dir)
        )

        command_result = run_command(cmdlist, cwd=self.scratch_dir)

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

        self._verify_build(
            function_full_paths,
            stack_paths,
            command_result,
        )

        if not SKIP_DOCKER_TESTS:
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


@skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
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
    def test_nested_build(self, use_container, cached, parallel):
        """
        Build template above and verify that each function call returns as expected
        """
        overrides = {
            "Runtime": "3.11",
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

        command_result = run_command(cmdlist, cwd=self.working_dir)

        stack_paths = ["", "LocalNestedStack"]
        self._verify_build(
            [],  # there is no function artifact dirs to check
            stack_paths,
            command_result,
        )

        if not SKIP_DOCKER_TESTS:
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
            ("use_container", "public.ecr.aws/sam/build-python3.11:latest-x86_64"),
        ]
    )
    def test_custom_build_image_succeeds(self, use_container, build_image):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container, build_image=build_image)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
        stderr = command_result.stderr
        process_stderr = stderr.strip()

        self._verify_right_image_pulled(build_image, process_stderr)
        self._verify_build_succeeds(self.default_build_dir)

        self.verify_docker_container_cleanedup("python3.12")

    def _verify_right_image_pulled(self, build_image, process_stderr):
        image_name = build_image if build_image is not None else "public.ecr.aws/sam/build-python3.11:latest-x86_64"
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
    def test_nested_build(self):
        if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
            cached=True,
            parallel=True,
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)

        self._verify_build(
            self.function_full_paths,
            self.layer_full_path,
            self.stack_paths,
            command_result,
        )

        if not SKIP_DOCKER_TESTS:
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

    def test_functions_layers_with_s3_codeuri(self):
        if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)

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

    def test_functions_layers_with_s3_codeuri(self):
        if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
            self.skipTest(SKIP_DOCKER_MESSAGE)

        """
        Build template above and verify that each function call returns as expected
        """
        cmdlist = self.get_command_list(
            use_container=True,
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        # no functions/layers should be built since they all have zip code/content
        # which are
        self._verify_build(
            [],
            [""],  # there is only one stack
            command_result,
        )


@skipIf(SKIP_SAR_TESTS, "Skip SAR tests")
class TestBuildSAR(BuildIntegBase):
    template = "aws-serverless-application-with-application-id-map.yaml"

    @classmethod
    def setUpClass(cls):
        super(TestBuildSAR, cls).setUpClass()
        cls.update_sar_template = None
        if cls.template_path:
            cls.update_sar_template = UpdatableSARTemplate(cls.template_path)
            cls.update_sar_template.setup()
            cls.template_path = cls.update_sar_template.updated_template_path

    @classmethod
    def tearDownClass(cls):
        if cls.update_sar_template:
            cls.update_sar_template.clean()

    @parameterized.expand(
        [
            ("use_container", "us-east-2"),
            ("use_container", "eu-west-1"),
            ("use_container", None),
            (False, "us-east-2"),
            (False, "eu-west-1"),
            (False, None),
        ]
    )
    def test_sar_application_with_location_resolved_from_map(self, use_container, region):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        cmdlist = self.get_command_list(use_container=use_container, region=region)
        process_execute = run_command(cmdlist, cwd=self.working_dir)

        if region == "us-east-2":  # Success [the !FindInMap contains an entry for use-east-2 region only]
            self.assertEqual(process_execute.process.returncode, 0)
        else:
            # Using other regions or the default SAM CLI region (us-east-1, in case if None region given)
            # will fail the build as there is no mapping
            self.assertEqual(process_execute.process.returncode, 1)
            self.assertIn("Property \\'ApplicationId\\' cannot be resolved.", str(process_execute.stderr))


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildWithLanguageExtensions(BuildIntegBase):
    template = "language-extensions.yaml"

    def test_validation_does_not_error_out(self):
        cmdlist = self.get_command_list()
        process_execute = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(process_execute.process.returncode, 0)
        self.assertIn("template.yaml", os.listdir(self.default_build_dir))
