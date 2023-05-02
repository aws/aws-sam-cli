from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils import (
    _add_lambda_resource_code_path_to_code_map,
)


class TestCodeResourceUtils(TestCase):
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils._calculate_configuration_attribute_value_hash"
    )
    def test_add_lambda_resource_code_path_to_code_map(self, mock_calculate_configuration_attribute_value_hash):
        mock_calculate_configuration_attribute_value_hash.return_value = "some-hash"
        lambda_resources_to_code_map = {}
        _add_lambda_resource_code_path_to_code_map(
            terraform_resource=Mock(),
            lambda_resource_prefix="aws_lambda_function",
            lambda_resources_to_code_map=lambda_resources_to_code_map,
            logical_id="my_logical_id",
            lambda_resource_code_value="my_cool_code.zip",
            terraform_code_property_name="filename",
            translated_resource={"my": "resource"},
        )
        self.assertEqual(
            lambda_resources_to_code_map, {"aws_lambda_function_some-hash": [({"my": "resource"}, "my_logical_id")]}
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils._resolve_resource_attribute")
    def test_add_lambda_resource_code_path_to_code_map_resolve_code_value(self, mock_resolve_resource_attribute):
        tf_resource_mock = Mock()
        _add_lambda_resource_code_path_to_code_map(
            terraform_resource=tf_resource_mock,
            lambda_resource_prefix="aws_lambda_function",
            lambda_resources_to_code_map={},
            logical_id="my_logical_id",
            lambda_resource_code_value=None,
            terraform_code_property_name="filename",
            translated_resource={"my": "resource"},
        )
        mock_resolve_resource_attribute.assert_called_once_with(tf_resource_mock, "filename")
