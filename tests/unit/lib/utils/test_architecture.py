from unittest import TestCase

from parameterized import parameterized

from samcli.lib.utils.architecture import ARM64, InvalidArchitecture, validate_architecture, X86_64


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
