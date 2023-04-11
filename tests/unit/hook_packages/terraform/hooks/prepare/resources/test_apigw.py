from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.exceptions import OpenAPIBodyNotSupportedException
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import (
    _unsupported_reference_field,
    RESTAPITranslationValidator,
)
from samcli.hook_packages.terraform.hooks.prepare.types import References, TFResource, ConstantValue


class TestRESTAPITranslationValidator(TestCase):
    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._unsupported_reference_field")
    def test_validate_valid(self, mock_unsupported_reference_field):
        mock_unsupported_reference_field.return_value = False
        validator = RESTAPITranslationValidator({}, TFResource("address", "", Mock(), {}))
        validator.validate()

    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.apigw._unsupported_reference_field")
    def test_validate_invalid(self, mock_unsupported_reference_field):
        mock_unsupported_reference_field.return_value = True
        validator = RESTAPITranslationValidator({}, TFResource("address", "", Mock(), {}))
        with self.assertRaises(OpenAPIBodyNotSupportedException) as ex:
            validator.validate()
        self.assertIn(
            "AWS SAM CLI is unable to process a Terraform project that "
            "uses an OpenAPI specification to define the API Gateway resource.",
            ex.exception.message,
        )

    @parameterized.expand(
        [
            ({"field": "a"}, TFResource("address", "", Mock(), {}), False),
            ({}, TFResource("address", "", Mock(), {"field": ConstantValue("a")}), False),
            ({}, TFResource("address", "", Mock(), {"field": References(["a"])}), True),
        ]
    )
    def test_unsupported_reference_field(self, resource, config_resource, expected):
        result = _unsupported_reference_field("field", resource, config_resource)
        self.assertEqual(result, expected)
