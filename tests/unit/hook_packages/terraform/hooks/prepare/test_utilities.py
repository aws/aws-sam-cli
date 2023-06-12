from unittest import TestCase

from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.utilities import get_configuration_address


class TestGetConfigurationAddress(TestCase):
    @parameterized.expand(
        [
            (
                "module.get_language_function.aws_lambda_function.this[0]",
                "module.get_language_function.aws_lambda_function.this",
            ),
            (
                "module.get_language_function.aws_lambda_function.this[1]",
                "module.get_language_function.aws_lambda_function.this",
            ),
            ("module.functions[0].aws_lambda_function.this[0]", "module.functions.aws_lambda_function.this"),
            ("module.functions[1].aws_lambda_function.this[1]", "module.functions.aws_lambda_function.this"),
            (
                'module.functions["get_function"].aws_lambda_function.this[0]',
                "module.functions.aws_lambda_function.this",
            ),
            (
                "module.functions.aws_lambda_function.this",
                "module.functions.aws_lambda_function.this",
            ),
        ]
    )
    def test_get_configuration_address(self, input_addr, expected_addr):
        cleaned_addr = get_configuration_address(input_addr)

        self.assertEqual(cleaned_addr, expected_addr)
