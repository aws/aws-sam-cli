import logging
import os
import shutil
from pathlib import Path
from unittest import skipIf

import pytest
from parameterized import parameterized

from samcli.lib.utils import osutils
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command, SKIP_DOCKER_TESTS, SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE

LOG = logging.getLogger(__name__)


class BuildIntegRubyBase(BuildIntegBase):
    EXPECTED_FILES_PROJECT_MANIFEST = {"app.rb"}
    EXPECTED_RUBY_GEM = "aws-record"

    FUNCTION_LOGICAL_ID = "Function"

    def _test_with_default_gemfile(self, runtime, use_container, code_uri, relative_path, architecture=None):
        overrides = self.get_override(runtime, code_uri, architecture, "ignored")
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


class TestBuildCommand_RubyFunctions(BuildIntegRubyBase):
    @parameterized.expand(["ruby2.7"])
    @pytest.mark.flaky(reruns=3)
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_ruby_in_container(self, runtime):
        self._test_with_default_gemfile(runtime, "use_container", "Ruby", self.test_data_path)

    @parameterized.expand(["ruby2.7"])
    @pytest.mark.flaky(reruns=3)
    def test_building_ruby_in_process(self, runtime):
        self._test_with_default_gemfile(runtime, False, "Ruby", self.test_data_path)


class TestBuildCommand_RubyFunctions_With_Architecture(BuildIntegRubyBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(["ruby2.7", ("ruby2.7", "arm64")])
    @pytest.mark.flaky(reruns=3)
    @skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
    def test_building_ruby_in_container_with_specified_architecture(self, runtime, architecture="x86_64"):
        self._test_with_default_gemfile(runtime, "use_container", "Ruby", self.test_data_path, architecture)

    @parameterized.expand(["ruby2.7", ("ruby2.7", "arm64")])
    @pytest.mark.flaky(reruns=3)
    def test_building_ruby_in_process_with_specified_architecture(self, runtime, architecture="x86_64"):
        self._test_with_default_gemfile(runtime, False, "Ruby", self.test_data_path, architecture)


class TestBuildCommand_RubyFunctionsWithGemfileInTheRoot(BuildIntegRubyBase):
    """
    Tests use case where Gemfile will present in the root of the project folder.
    This doesn't apply to containerized build, since it copies only the function folder to the container
    """

    @parameterized.expand([("ruby2.7")])
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
