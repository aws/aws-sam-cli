from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_layers import LambdaLayerVersionProperties
from samcli.hook_packages.terraform.hooks.prepare.types import ResourceTranslationProperties, TFResource


class TestLambdaLayerVersionProperties(TestCase):
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.resources.lambda_layers._add_lambda_resource_code_path_to_code_map"
    )
    def test_add_lambda_resources_to_code_map(self, mock_add_lambda_resource_code_path_to_code_map):
        module_mock = Mock()
        dummy_properties = ResourceTranslationProperties(
            resource=Mock(),
            translated_resource={"translated": "resource"},
            config_resource=TFResource("address", "type", module_mock, {}),
            logical_id="my_layer",
            resource_full_address=Mock(),
        )
        translated_properties = {"Content": "my_layer.zip"}
        layer_properties = LambdaLayerVersionProperties()
        layer_properties.add_lambda_resources_to_code_map(dummy_properties, translated_properties, {})
        mock_add_lambda_resource_code_path_to_code_map.assert_called_once_with(
            TFResource(address="address", type="type", module=module_mock, attributes={}),
            "layer",
            {},
            "my_layer",
            "my_layer.zip",
            "filename",
            {"translated": "resource"},
        )
