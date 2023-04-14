import logging
import os
import random
import sys
from typing import Set
from unittest import skipIf

import pytest
from parameterized import parameterized_class, parameterized

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import (
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    run_command,
    RUN_BY_CANARY,
    CI_OVERRIDE,
)

LOG = logging.getLogger(__name__)


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

        LOG.info("Running Command: {}".format(cmdlist))
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
        return "python{}.{}".format(sys.version_info.major, sys.version_info.minor)


@parameterized_class(
    (
        "template",
        "FUNCTION_LOGICAL_ID",
        "overrides",
        "runtime",
        "codeuri",
        "use_container",
        "check_function_only",
        "prop",
    ),
    [
        ("template.yaml", "Function", True, "python3.7", "Python", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.8", "Python", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.9", "Python", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.10", "Python", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.7", "PythonPEP600", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.8", "PythonPEP600", False, False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.7", "Python", "use_container", False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.8", "Python", "use_container", False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.9", "Python", "use_container", False, "CodeUri"),
        ("template.yaml", "Function", True, "python3.10", "Python", "use_container", False, "CodeUri"),
    ],
)
class TestBuildCommand_PythonFunctions(BuildIntegPythonBase):
    overrides = True
    runtime = "python3.9"
    codeuri = "Python"
    use_container = False
    check_function_only = False

    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self):
        if self.use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_requirements(
            self.runtime,
            self.codeuri,
            self.use_container,
            self.test_data_path,
            do_override=self.overrides,
            check_function_only=self.check_function_only,
        )


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    SKIP_DOCKER_TESTS,
    "Skip build tests that requires Docker in CI environment",
)
@parameterized_class(
    (
        "template",
        "FUNCTION_LOGICAL_ID",
        "overrides",
        "runtime",
        "codeuri",
        "use_container",
        "check_function_only",
        "prop",
    ),
    [
        (
            "cdk_v1_synthesized_template_zip_image_functions.json",
            "RandomCitiesFunction5C47A2B8",
            False,
            None,
            None,
            False,
            True,
            "Code",
        ),
    ],
)
class TestBuildCommand_PythonFunctions_CDK(TestBuildCommand_PythonFunctions):
    @pytest.mark.flaky(reruns=3)
    def test_cdk_app_with_default_requirements(self):
        self._test_with_default_requirements(
            self.runtime,
            self.codeuri,
            self.use_container,
            self.test_data_path,
            do_override=self.overrides,
            check_function_only=self.check_function_only,
        )


class TestBuildCommand_PythonFunctions_With_Specified_Architecture(BuildIntegPythonBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("python3.7", "Python", False, "x86_64"),
            ("python3.8", "Python", False, "x86_64"),
            # numpy 1.20.3 (in PythonPEP600/requirements.txt) only support python 3.7+
            ("python3.7", "PythonPEP600", False, "x86_64"),
            ("python3.8", "PythonPEP600", False, "x86_64"),
            ("python3.7", "Python", "use_container", "x86_64"),
            ("python3.8", "Python", "use_container", "x86_64"),
            ("python3.8", "Python", False, "arm64"),
            ("python3.8", "PythonPEP600", False, "arm64"),
            ("python3.8", "Python", "use_container", "arm64"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self, runtime, codeuri, use_container, architecture):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_default_requirements(
            runtime, codeuri, use_container, self.test_data_path, architecture=architecture
        )


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_PythonFunctions_Images(BuildIntegBase):
    template = "template_image.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST: Set[str] = set()

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    @parameterized.expand([("3.7", False), ("3.8", False), ("3.9", False)])
    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self, runtime, use_container):
        _tag = f"{random.randint(1,100)}"
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": "Dockerfile",
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

    @parameterized.expand([("3.7", False), ("3.8", False), ("3.9", False)])
    @pytest.mark.flaky(reruns=3)
    def test_with_dockerfile_extension(self, runtime, use_container):
        _tag = f"{random.randint(1,100)}"
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": "Dockerfile.production",
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=use_container, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

    @pytest.mark.flaky(reruns=3)
    def test_intermediate_container_deleted(self):
        _tag = f"{random.randint(1, 100)}"
        overrides = {
            "Runtime": "3.9",
            "Handler": "main.handler",
            "DockerFile": "Dockerfile",
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)

        _num_of_containers_before_build = self.get_number_of_created_containers()
        run_command(cmdlist, cwd=self.working_dir)
        _num_of_containers_after_build = self.get_number_of_created_containers()

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

        self.assertEqual(
            _num_of_containers_before_build, _num_of_containers_after_build, "Intermediate containers are not removed"
        )


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestBuildCommand_PythonFunctions_ImagesWithSharedCode(BuildIntegBase):
    template = "template_images_with_shared_code.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST: Set[str] = set()

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    @parameterized.expand(
        [
            *[(runtime, "feature_phi/Dockerfile", {"phi": "1.62"}) for runtime in ["3.7", "3.8", "3.9"]],
            *[(runtime, "feature_pi/Dockerfile", {"pi": "3.14"}) for runtime in ["3.7", "3.8", "3.9"]],
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_with_default_requirements(self, runtime, dockerfile, expected):
        _tag = f"{random.randint(1, 100)}"
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)
        run_command(cmdlist, cwd=self.working_dir)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

    @parameterized.expand(
        [
            ("feature_phi/Dockerfile", {"phi": "1.62"}),
            ("feature_pi/Dockerfile", {"pi": "3.14"}),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_intermediate_container_deleted(self, dockerfile, expected):
        _tag = f"{random.randint(1, 100)}"
        overrides = {
            "Runtime": "3.9",
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        LOG.info("Running Command: ")
        LOG.info(cmdlist)

        _num_of_containers_before_build = self.get_number_of_created_containers()
        run_command(cmdlist, cwd=self.working_dir)
        _num_of_containers_after_build = self.get_number_of_created_containers()

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

        self.assertEqual(
            _num_of_containers_before_build, _num_of_containers_after_build, "Intermediate containers are not removed"
        )
