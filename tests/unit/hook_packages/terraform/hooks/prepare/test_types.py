"""Test types"""
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.hook_packages.terraform.hooks.prepare.types import (
    ResourceProperties,
    TFResource,
    ResourceTranslationProperties,
)


class TestLambdaLayerVersionProperties(TestCase):
    @patch("samcli.hook_packages.terraform.hooks.prepare.types.get_configuration_address")
    def test_collect(self, mock_get_configuration_address):
        class TestingProperties(ResourceProperties):
            def __init__(self):
                super(TestingProperties, self).__init__()

        module_mock = Mock()
        mock_get_configuration_address.side_effect = ["address_a", "address_a", "address_b"]

        testing_resource_a_tf_config = {
            "address": "address_b",
            "mode": "managed",
            "type": "testing_type",
            "values": {
                "prop": "value",
            },
        }

        testing_resource_b_tf_config = {
            "address": "address_b",
            "mode": "managed",
            "type": "testing_type",
            "values": {
                "prop": "value",
            },
        }

        config_a = TFResource(address="address_a", type="testing_type", module=module_mock, attributes={})
        dummy_properties = ResourceTranslationProperties(
            resource=testing_resource_a_tf_config,
            translated_resource={"cfn_resource": "a"},
            config_resource=config_a,
            logical_id="my_testing_resource_a",
            resource_full_address=Mock(),
        )
        testing_properties = TestingProperties()
        testing_properties.collect(dummy_properties)

        self.assertEqual(testing_properties.terraform_config["address_a"], config_a)

        dummy_properties = ResourceTranslationProperties(
            resource=testing_resource_b_tf_config,
            translated_resource={"cfn_resource": "b"},
            config_resource=config_a,
            logical_id="my_testing_resource_b",
            resource_full_address=Mock(),
        )
        testing_properties.collect(dummy_properties)

        config_b = TFResource(address="address_b", type="testing_type", module=module_mock, attributes={})
        dummy_properties = ResourceTranslationProperties(
            resource=testing_resource_b_tf_config,
            translated_resource={"cfn_resource": "c"},
            config_resource=config_b,
            logical_id="my_testing_resource_c",
            resource_full_address=Mock(),
        )
        testing_properties.collect(dummy_properties)

        self.assertEqual(testing_properties.terraform_config["address_a"], config_a)
        self.assertEqual(testing_properties.terraform_config["address_b"], config_b)

        self.assertEqual(testing_properties.cfn_resources["address_a"], [{"cfn_resource": "a"}, {"cfn_resource": "b"}])
        self.assertEqual(testing_properties.cfn_resources["address_b"], [{"cfn_resource": "c"}])

        self.assertEqual(
            testing_properties.terraform_resources,
            {
                "my_testing_resource_a": testing_resource_a_tf_config,
                "my_testing_resource_b": testing_resource_b_tf_config,
                "my_testing_resource_c": testing_resource_b_tf_config,
            },
        )
