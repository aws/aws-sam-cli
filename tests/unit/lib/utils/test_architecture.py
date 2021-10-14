from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.commands.local.lib.exceptions import UnsupportedRuntimeArchitectureError
from samcli.lib.utils.architecture import (
    ARM64,
    InvalidArchitecture,
    validate_architecture,
    X86_64,
    validate_architecture_runtime,
    has_runtime_multi_arch_image,
)
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestArchitecture(TestCase):
    """
    Tests for samcli.lib.utils.architecture
    """

    def test_validate_architecture(self):
        """
        Passing values
        """
        validate_architecture(ARM64)
        validate_architecture(X86_64)

    @parameterized.expand([(None,), (""), ("unknown")])
    def test_validate_architecture_errors(self, value):
        """
        Invalid values

        Parameters
        ----------
        value : str
            Value
        """
        with self.assertRaises(InvalidArchitecture):
            validate_architecture(value)

    @parameterized.expand(
        [
            ("nodejs10.x", X86_64, ZIP),
            ("java8.al2", ARM64, ZIP),
            ("dotnetcore3.1", ARM64, ZIP),
            (None, X86_64, IMAGE),
            (None, ARM64, IMAGE),
            (None, X86_64, IMAGE),
        ]
    )
    def test_must_pass_for_support_runtime_architecture(self, runtime, arch, packagetype):
        function = Mock(
            functionname="name", handler="app.handler", runtime=runtime, packagetype=packagetype, architectures=[arch]
        )
        validate_architecture_runtime(function)

    @parameterized.expand(
        [
            ("nodejs10.x", ARM64),
            ("python2.7", ARM64),
            ("python3.6", ARM64),
            ("python3.7", ARM64),
            ("ruby2.5", ARM64),
            ("java8", ARM64),
            ("go1.x", ARM64),
            ("provided", ARM64),
        ]
    )
    def test_must_raise_for_unsupported_runtime_architecture(self, runtime, arch):
        function = Mock(
            functionname="name", handler="app.handler", runtime=runtime, architectures=[arch], packagetype=ZIP
        )

        with self.assertRaises(UnsupportedRuntimeArchitectureError) as ex:
            validate_architecture_runtime(function)

        self.assertEqual(str(ex.exception), f"Runtime {runtime} is not supported on '{arch}' architecture")

    @parameterized.expand([("python3.6", False), ("python3.8", True)])
    def test_multi_arch_image(self, runtime, result):
        self.assertEqual(has_runtime_multi_arch_image(runtime), result)
