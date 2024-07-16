import logging
import os
import pytest
from parameterized import parameterized, parameterized_class

from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
)
from tests.integration.buildcmd.build_integ_base import (
    BuildIntegProvidedBase,
)


LOG = logging.getLogger(__name__)

# SAR tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SAR_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@parameterized_class(
    ("template", "is_nested_parent"),
    [
        (os.path.join("nested-parent", "template-parent.yaml"), "is_nested_parent"),
        ("template.yaml", False),
    ],
)
@pytest.mark.provided
class TestBuildCommand_ProvidedFunctions(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None),
            ("provided", "use_container", "Makefile-container"),
            ("provided.al2", False, None),
            ("provided.al2", "use_container", "Makefile-container"),
        ]
    )
    def test_building_Makefile(self, runtime, use_container, manifest):
        if use_container:
            if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
                self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_Makefile(runtime, use_container, manifest)

    @parameterized.expand(
        [
            ("provided.al2023", False, None),
            ("provided.al2023", "use_container", "Makefile-container"),
        ]
    )
    @pytest.mark.al2023
    def test_building_Makefile_al2023(self, runtime, use_container, manifest):
        if use_container:
            if SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD:
                self.skipTest(SKIP_DOCKER_MESSAGE)
        self._test_with_Makefile(runtime, use_container, manifest)


@parameterized_class(
    ("template", "is_nested_parent"),
    [
        (os.path.join("nested-parent", "template-parent.yaml"), "is_nested_parent"),
        ("template.yaml", False),
    ],
)
class TestBuildCommand_ProvidedFunctions_With_Specified_Architecture(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None, "x86_64"),
            ("provided", "use_container", "Makefile-container", "x86_64"),
            ("provided.al2", False, None, "x86_64"),
            ("provided.al2", "use_container", "Makefile-container", "x86_64"),
        ]
    )
    def test_building_Makefile(self, runtime, use_container, manifest, architecture):
        self._test_with_Makefile(runtime, use_container, manifest, architecture)

    @parameterized.expand(
        [
            ("provided.al2023", False, None, "x86_64"),
            ("provided.al2023", "use_container", "Makefile-container", "x86_64"),
        ]
    )
    @pytest.mark.al2023
    def test_building_Makefile_al2023(self, runtime, use_container, manifest, architecture):
        self._test_with_Makefile(runtime, use_container, manifest, architecture)


@parameterized_class(
    ("template", "code_uri", "is_nested_parent"),
    [
        ("custom_build_with_custom_root_project_path.yaml", "empty_src_code", False),
        ("custom_build_with_custom_make_file_path.yaml", "provided_src_code_without_makefile", False),
        ("custom_build_with_custom_working_dir.yaml", "custom_working_dir_src_code", False),
        ("custom_build_with_custom_root_project_path_and_custom_makefile_path.yaml", "empty_src_code", False),
        (
            "custom_build_with_custom_root_project_path_custom_makefile_path_and_custom_working_dir.yaml",
            "empty_src_code",
            False,
        ),
    ],
)
class TestBuildCommand_ProvidedFunctionsWithCustomMetadata(BuildIntegProvidedBase):
    # Test Suite for runtime: provided and where selection of the build workflow is implicitly makefile builder
    # if the makefile is present.
    @parameterized.expand(
        [
            ("provided", False, None),
            ("provided.al2", False, None),
        ]
    )
    def test_building_Makefile(self, runtime, use_container, manifest):
        self._test_with_Makefile(runtime, use_container, manifest)

    @parameterized.expand(
        [
            ("provided.al2023", False, None),
        ]
    )
    @pytest.mark.al2023
    def test_building_Makefile_al2023(self, runtime, use_container, manifest):
        self._test_with_Makefile(runtime, use_container, manifest)
