"""
Integration test cases for `sam build` for Rust (cargo-lambda)
"""

import logging
import shutil
from pathlib import Path
from unittest import skipIf

from parameterized import parameterized, parameterized_class

from samcli.lib.utils import osutils
from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    CI_OVERRIDE,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
)
from .build_integ_base import (
    BuildIntegRustBase,
)

LOG = logging.getLogger(__name__)

# SAR tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SAR_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@parameterized_class(
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
)
class TestBuildCommand_Rust(BuildIntegRustBase):
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

    @parameterized.expand(
        [
            ("x86_64", None, False),
            ("arm64", None, False),
            ("x86_64", "debug", False),
            ("arm64", "debug", False),
        ]
    )
    def test_build(self, architecture, build_mode, use_container):
        if use_container and (SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD):
            self.skipTest(SKIP_DOCKER_MESSAGE)

        self._test_with_rust_cargo_lambda(
            runtime="provided.al2",
            code_uri=self.code_uri,
            binary=self.binary,
            architecture=architecture,
            build_mode=build_mode,
            expected_invoke_result=self.expected_invoke_result,
        )
