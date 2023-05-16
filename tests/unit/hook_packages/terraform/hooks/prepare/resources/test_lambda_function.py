from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_function import LambdaFunctionProperties
from samcli.hook_packages.terraform.hooks.prepare.types import ResourceTranslationProperties, TFResource
from samcli.lib.utils.packagetype import ZIP


class TestLambdaLayerVersionProperties(TestCase):
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.resources.lambda_function._add_lambda_resource_code_path_to_code_map"
    )
    def test_add_lambda_resources_to_code_map(self, mock_add_lambda_resource_code_path_to_code_map):
        module_mock = Mock()
        dummy_properties = ResourceTranslationProperties(
            resource=Mock(),
            translated_resource={"translated": "resource"},
            config_resource=TFResource("address", "aws_lambda_function", module_mock, {}),
            logical_id="my_function",
            resource_full_address=Mock(),
        )
        translated_properties = {"PackageType": ZIP, "Code": "my_function_code.zip"}
        function_properties = LambdaFunctionProperties()
        function_properties.add_lambda_resources_to_code_map(dummy_properties, translated_properties, {})
        mock_add_lambda_resource_code_path_to_code_map.assert_called_once_with(
            TFResource(address="address", type="aws_lambda_function", module=module_mock, attributes={}),
            "zip",
            {},
            "my_function",
            "my_function_code.zip",
            "filename",
            {"translated": "resource"},
        )
