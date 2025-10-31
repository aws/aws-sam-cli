import logging
import pathlib
from typing import Set
from unittest import skipIf
from uuid import uuid4

import pytest
from parameterized import parameterized, parameterized_class

from tests.integration.buildcmd.build_integ_base import (
    BuildIntegBase,
    BuildIntegPythonBase,
    show_container_in_test_name,
)
from tests.testing_utils import (
    CI_OVERRIDE,
    IS_WINDOWS,
    RUN_BY_CANARY,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
    SKIP_DOCKER_TESTS,
    run_command,
)

LOG = logging.getLogger(__name__)

# SAR tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SAR_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(
    # Hits public ECR pull limitation, move it to canary tests
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@pytest.mark.python
class TestBuildCommand_PythonFunctions_Images(BuildIntegBase):
    template = "template_image.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST: Set[str] = set()

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    def _test_default_requirements_wrapper(self, runtime, dockerfile):
        tag = uuid4().hex
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{tag}",
        )

        expected = {"pi": "3.14"}
        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

    @parameterized.expand(
        [
            *[(runtime, "Dockerfile") for runtime in ["3.8", "3.9", "3.10", "3.11"]],
            *[(runtime, "Dockerfile.production") for runtime in ["3.8", "3.9", "3.10", "3.11"]],
        ]
    )
    def test_with_default_requirements(self, runtime, dockerfile):
        self._test_default_requirements_wrapper(runtime, dockerfile)

    @parameterized.expand(
        [
            *[(runtime, "Dockerfile") for runtime in ["3.12", "3.13"]],
            *[(runtime, "Dockerfile.production") for runtime in ["3.12", "3.13"]],
        ]
    )
    @pytest.mark.al2023
    def test_with_default_requirements_al2023(self, runtime, dockerfile):
        self._test_default_requirements_wrapper(runtime, dockerfile)

    def test_intermediate_container_deleted(self):
        _tag = uuid4().hex
        overrides = {
            "Runtime": "3.9",
            "Handler": "main.handler",
            "DockerFile": "Dockerfile",
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        _num_of_containers_before_build = self.get_number_of_created_containers()
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
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
@pytest.mark.python
class TestBuildCommand_PythonFunctions_ImagesWithSharedCode(BuildIntegBase):
    template = "template_images_with_shared_code.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST: Set[str] = set()

    FUNCTION_LOGICAL_ID_IMAGE = "ImageFunction"

    def _test_default_requirements_wrapper(self, runtime, dockerfile, expected):
        tag = uuid4().hex
        overrides = {
            "Runtime": runtime,
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": tag,
        }

        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{tag}",
        )

        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )

    @parameterized.expand(
        [
            *[(runtime, "feature_phi/Dockerfile", {"phi": "1.62"}) for runtime in ["3.8", "3.9", "3.10", "3.11"]],
            *[(runtime, "feature_pi/Dockerfile", {"pi": "3.14"}) for runtime in ["3.8", "3.9", "3.10", "3.11"]],
        ]
    )
    def test_with_default_requirements(self, runtime, dockerfile, expected):
        self._test_default_requirements_wrapper(runtime, dockerfile, expected)

    @parameterized.expand(
        [
            *[(runtime, "feature_phi/Dockerfile", {"phi": "1.62"}) for runtime in ["3.12", "3.13"]],
            *[(runtime, "feature_pi/Dockerfile", {"pi": "3.14"}) for runtime in ["3.12", "3.13"]],
        ]
    )
    @pytest.mark.al2023
    def test_with_default_requirements_al2023(self, runtime, dockerfile, expected):
        self._test_default_requirements_wrapper(runtime, dockerfile, expected)

    @parameterized.expand(
        [
            ("feature_phi/Dockerfile", {"phi": "1.62"}),
            ("feature_pi/Dockerfile", {"pi": "3.14"}),
        ]
    )
    def test_intermediate_container_deleted(self, dockerfile, expected):
        _tag = uuid4().hex
        overrides = {
            "Runtime": "3.9",
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        _num_of_containers_before_build = self.get_number_of_created_containers()
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)
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

    @parameterized.expand(
        [
            ("feature_phi\\Dockerfile", {"phi": "1.62"}),
            ("feature_pi\\Dockerfile", {"pi": "3.14"}),
        ]
    )
    @skipIf(not IS_WINDOWS, "Skipping passing Windows path for dockerfile path on non Windows platform")
    def test_windows_dockerfile_present_sub_dir(self, dockerfile, expected):
        _tag = uuid4().hex
        overrides = {
            "Runtime": "3.9",
            "Handler": "main.handler",
            "DockerFile": dockerfile,
            "Tag": _tag,
        }
        cmdlist = self.get_command_list(use_container=False, parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID_IMAGE,
            "ImageUri",
            f"{self.FUNCTION_LOGICAL_ID_IMAGE.lower()}:{_tag}",
        )

        self._verify_invoke_built_function(
            self.built_template, self.FUNCTION_LOGICAL_ID_IMAGE, self._make_parameter_override_arg(overrides), expected
        )


# @skipIf(
#     # Hits public ECR pull limitation, move it to canary tests
#     ((not RUN_BY_CANARY) or (IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
#     "Skip build tests on windows when running in CI unless overridden",
# )
@parameterized_class(
    ("template", "prop"),
    [
        ("template_local_prebuilt_image.yaml", "ImageUri"),
        ("template_cfn_local_prebuilt_image.yaml", "Code.ImageUri"),
    ],
)
@parameterized_class(
    (
        "runtime",
        "codeuri",
    ),
    [
        ("python3.9", "Python"),
        ("python3.10", "Python"),
        ("python3.11", "Python"),
        ("python3.9", "PythonPEP600"),
        ("python3.10", "PythonPEP600"),
        ("python3.11", "PythonPEP600"),
    ],
)
class TestBuildCommand_PythonFunctions_WithoutDocker(BuildIntegPythonBase):
    template = "template.yaml"
    FUNCTION_LOGICAL_ID = "Function"
    overrides = True
    runtime = "python3.9"
    codeuri = "Python"
    check_function_only = False
    use_container = False
    prop = "CodeUri"

    def test_with_default_requirements(self):
        self._test_with_default_requirements(
            self.runtime,
            self.codeuri,
            self.use_container,
            self.test_data_path,
            do_override=self.overrides,
            check_function_only=self.check_function_only,
        )


@parameterized_class(
    ("template", "prop"),
    [
        ("template_local_prebuilt_image.yaml", "ImageUri"),
        ("template_cfn_local_prebuilt_image.yaml", "Code.ImageUri"),
    ],
)
@parameterized_class(
    (
        "runtime",
        "codeuri",
    ),
    [
        ("python3.12", "Python"),
        ("python3.12", "PythonPEP600"),
        ("python3.13", "Python"),
        ("python3.13", "PythonPEP600"),
    ],
)
@pytest.mark.al2023
class TestBuildCommand_PythonFunctions_WithoutDocker_al2023(BuildIntegPythonBase):
    template = "template.yaml"
    FUNCTION_LOGICAL_ID = "Function"
    overrides = True
    runtime = "python3.9"
    codeuri = "Python"
    check_function_only = False
    use_container = False
    prop = "CodeUri"

    def test_with_default_requirements(self):
        self._test_with_default_requirements(
            self.runtime,
            self.codeuri,
            self.use_container,
            self.test_data_path,
            do_override=self.overrides,
            check_function_only=self.check_function_only,
        )


@skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
class TestBuildCommand_PythonFunctions_WithDocker(BuildIntegPythonBase):
    template = "template.yaml"
    FUNCTION_LOGICAL_ID = "Function"
    overrides = True
    codeuri = "Python"
    use_container = "use_container"
    check_function_only = False
    prop = "CodeUri"

    @parameterized.expand(
        [
            ("python3.9",),
            ("python3.10",),
            ("python3.11",),
        ]
    )
    def test_with_default_requirements_in_container(self, runtime):
        self._test_with_default_requirements(
            runtime,
            self.codeuri,
            self.use_container,
            self.test_data_path,
            do_override=self.overrides,
            check_function_only=self.check_function_only,
        )

    @parameterized.expand(
        [
            ("python3.12",),
            ("python3.13",),
        ]
    )
    @pytest.mark.al2023
    def test_with_default_requirements_al2023_in_container(self, runtime):
        self._test_with_default_requirements(
            runtime,
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
class TestBuildCommand_PythonFunctions_CDK(TestBuildCommand_PythonFunctions_WithoutDocker):
    use_container = False

    def test_cdk_app_with_default_requirements(self):
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
        "use_container",
        "prop",
    ),
    [
        (
            "cdk_v2_synthesized_template_image_function_shared_code.json",
            "TestLambdaFunctionC089708A",
            False,
            False,
            "Code.ImageUri",
        ),
    ],
)
class TestBuildCommandCDKPythonImageFunctionSharedCode(BuildIntegPythonBase):
    def test_cdk_app_with_default_requirements(self):
        expected = "Hello World"
        cmdlist = self.get_command_list(use_container=self.use_container)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(command_result.process.returncode, 0)

        self._verify_image_build_artifact(
            self.built_template,
            self.FUNCTION_LOGICAL_ID,
            self.prop,
            f"{self.FUNCTION_LOGICAL_ID.lower()}:latest",
        )

        self._verify_invoke_built_function(self.built_template, self.FUNCTION_LOGICAL_ID, {}, expected)


class TestBuildCommand_PythonFunctions_With_Specified_Architecture(BuildIntegPythonBase):
    template = "template_with_architecture.yaml"

    @parameterized.expand(
        [
            ("python3.9", "Python", False, "x86_64"),
            ("python3.10", "Python", False, "x86_64"),
            ("python3.11", "Python", False, "x86_64"),
            ("python3.9", "PythonPEP600", False, "x86_64"),
            ("python3.10", "PythonPEP600", False, "x86_64"),
            ("python3.11", "PythonPEP600", False, "x86_64"),
            ("python3.9", "Python", "use_container", "x86_64"),
            ("python3.10", "Python", "use_container", "x86_64"),
            ("python3.11", "Python", "use_container", "x86_64"),
        ],
        name_func=show_container_in_test_name,
    )
    def test_with_default_requirements(self, runtime, codeuri, use_container, architecture):
        self._test_with_default_requirements(
            runtime, codeuri, use_container, self.test_data_path, architecture=architecture
        )

    @parameterized.expand(
        [
            ("python3.12", "Python", False, "x86_64"),
            ("python3.12", "PythonPEP600", False, "x86_64"),
            ("python3.12", "Python", "use_container", "x86_64"),
            ("python3.13", "Python", False, "x86_64"),
            ("python3.13", "PythonPEP600", False, "x86_64"),
            ("python3.13", "Python", "use_container", "x86_64"),
        ],
        name_func=show_container_in_test_name,
    )
    @pytest.mark.al2023
    def test_with_default_requirements_al2023(self, runtime, codeuri, use_container, architecture):
        self._test_with_default_requirements(
            runtime, codeuri, use_container, self.test_data_path, architecture=architecture
        )

    def test_invalid_architecture(self):
        overrides = {"Runtime": "python3.11", "Architectures": "fake"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        process_execute = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(1, process_execute.process.returncode)

        self.assertIn("Build Failed", str(process_execute.stdout))
        self.assertIn("Architecture fake is not supported", str(process_execute.stderr))


class TestBuildCommand_ParentPackages(BuildIntegPythonBase):
    template = "template_with_metadata_python.yaml"
    runtime = "python3.12"
    use_container = False
    prop = "CodeUri"

    logical_id_one = "FunctionOne"
    logical_id_two = "FunctionTwo"
    parent_packages_one = "src.fnone"
    parent_packages_two = "src.fntwo"
    codeuri_one = "PythonParentPackages/src/fnone"
    codeuri_two = "PythonParentPackages/src/fntwo"
    handler_one = f"{parent_packages_one}.main.handler"
    handler_two = f"{parent_packages_two}.main.handler"

    overrides = {
        "Runtime": runtime,
        "CodeUriOne": codeuri_one,
        "CodeUriTwo": codeuri_two,
        "HandlerOne": handler_one,
        "HandlerTwo": handler_two,
    }

    expected_files_project_manifest = {"numpy", "src"}
    expected_source_files = {
        "__init__.py",
        "main.py",
        "requirements.txt",
    }

    def test_parent_package_mode_explicit(self):
        # Arrange
        cmdlist = self.get_command_list(
            use_container=self.use_container,
            parameter_overrides={
                **self.overrides,
                "ParentPackageMode": "explicit",
                "ParentPackagesOne": self.parent_packages_one,
                "ParentPackagesTwo": self.parent_packages_two,
            },
        )

        # Act
        run_command(cmdlist, cwd=self.working_dir)

        # Assert
        self._verify_built_artifacts()

    def test_parent_package_mode_auto(self):
        # Arrange
        cmdlist = self.get_command_list(
            use_container=self.use_container,
            parameter_overrides={**self.overrides, "ParentPackageMode": "auto"},
        )

        # Act
        run_command(cmdlist, cwd=self.working_dir)

        # Assert
        self._verify_built_artifacts()

    def _verify_built_artifacts(self):
        [
            self._verify_built_artifact(self.default_build_dir, logical_id, self.expected_files_project_manifest)
            for logical_id in [self.logical_id_one, self.logical_id_two]
        ]
        [
            self._verify_source_files(
                self.default_build_dir,
                self.expected_source_files,
                logical_id,
                parent_packages,
            )
            for (logical_id, parent_packages) in [
                (self.logical_id_one, self.parent_packages_one),
                (self.logical_id_two, self.parent_packages_two),
            ]
        ]

    def _verify_source_files(
        self, build_dir: pathlib.Path, expected_files: set[str], function_logical_id: str, parent_packages: str
    ) -> None:
        relative_code_uri = parent_packages.replace(".", "/")
        function_artifact_dir = build_dir / function_logical_id / relative_code_uri
        all_artifacts = set(
            map(
                lambda artifact: str(object=artifact.relative_to(function_artifact_dir)),
                function_artifact_dir.glob("*"),
            )
        )
        actual_files = all_artifacts.intersection(expected_files)
        self.assertEqual(actual_files, expected_files)


class TestBuildCommand_ErrorCases(BuildIntegBase):
    def test_unsupported_runtime(self):
        overrides = {"Runtime": "unsupportedpython", "CodeUri": "Python"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        process_execute = run_command(cmdlist, cwd=self.working_dir)
        self.assertEqual(1, process_execute.process.returncode)

        self.assertIn("Build Failed", str(process_execute.stdout))
