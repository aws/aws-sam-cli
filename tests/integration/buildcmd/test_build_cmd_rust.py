"""
Integration test cases for `sam build` for Rust (cargo-lambda)
"""

import logging
from unittest import skipIf

from parameterized import parameterized

from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    CI_OVERRIDE,
)
from .build_integ_base import (
    BuildIntegRustBase,
    rust_parameterized_class,
)

LOG = logging.getLogger(__name__)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
@rust_parameterized_class
class TestBuildCommand_Rust(BuildIntegRustBase):
    @parameterized.expand(
        [
            ("provided", "x86_64", None, False),
            ("provided", "x86_64", "debug", False),
            ("provided.al2", "x86_64", None, False),
            ("provided.al2", "x86_64", "debug", False),
            ("provided.al2023", "x86_64", None, False),
            ("provided.al2023", "x86_64", "debug", False),
        ]
    )
    def test_build(self, runtime, architecture, build_mode, use_container):
        self._test_with_rust_cargo_lambda(
            runtime=runtime,
            code_uri=self.code_uri,
            binary=self.binary,
            architecture=architecture,
            build_mode=build_mode,
            expected_invoke_result=self.expected_invoke_result,
            use_container=use_container,
        )
