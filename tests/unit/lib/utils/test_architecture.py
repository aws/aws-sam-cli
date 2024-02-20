from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.commands.local.lib.exceptions import UnsupportedRuntimeArchitectureError
from samcli.lib.utils.architecture import (
    InvalidArchitecture,
    validate_architecture,
    validate_architecture_runtime,
    has_runtime_multi_arch_image,
)
from samcli.lib.runtimes.base import Architecture
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestArchitecture(TestCase):
    """
    Tests for samcli.lib.utils.architecture
    """

    def test_validate_architecture(self):
        """
        Passing values
        """
        validate_architecture(Architecture.ARM64.value)
        validate_architecture(Architecture.X86_64.value)

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
            ("nodejs20.x", Architecture.X86_64.value, ZIP),
            ("java8.al2", Architecture.ARM64.value, ZIP),
            ("dotnet6", Architecture.ARM64.value, ZIP),
            (None, Architecture.X86_64.value, IMAGE),
            (None, Architecture.ARM64.value, IMAGE),
            (None, Architecture.X86_64.value, IMAGE),
        ]
    )
    def test_must_pass_for_support_runtime_architecture(self, runtime, arch, packagetype):
        function = Mock(
            functionname="name", handler="app.handler", runtime=runtime, packagetype=packagetype, architectures=[arch]
        )
        validate_architecture_runtime(function)

    @parameterized.expand(
        [
            ("python3.7", Architecture.ARM64.value),
            ("java8", Architecture.ARM64.value),
            ("go1.x", Architecture.ARM64.value),
            ("provided", Architecture.ARM64.value),
        ]
    )
    def test_must_raise_for_unsupported_runtime_architecture(self, runtime, arch):
        function = Mock(
            functionname="name", handler="app.handler", runtime=runtime, architectures=[arch], packagetype=ZIP
        )

        with self.assertRaises(UnsupportedRuntimeArchitectureError) as ex:
            validate_architecture_runtime(function)

        self.assertEqual(str(ex.exception), f"Runtime {runtime} is not supported on '{arch}' architecture")

    @parameterized.expand([("python3.8", True), ("python3.9", True)])
    def test_multi_arch_image(self, runtime, result):
        self.assertEqual(has_runtime_multi_arch_image(runtime), result)
