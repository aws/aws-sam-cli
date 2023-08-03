from unittest import TestCase

from samcli.hook_packages.terraform.hooks.prepare.constants import TF_AWS_LAMBDA_FUNCTION, TF_AWS_LAMBDA_LAYER_VERSION
from samcli.hook_packages.terraform.hooks.prepare.resources.resource_properties import get_resource_property_mapping
from samcli.hook_packages.terraform.hooks.prepare.types import CodeResourceProperties


class TestResourceProperties(TestCase):
    def test_get_resource_property_mapping(self):
        resource_property_mapping = get_resource_property_mapping()
        self.assertIn(TF_AWS_LAMBDA_FUNCTION, resource_property_mapping)
        self.assertTrue(isinstance(resource_property_mapping[TF_AWS_LAMBDA_FUNCTION], CodeResourceProperties))

        self.assertIn(TF_AWS_LAMBDA_LAYER_VERSION, resource_property_mapping)
        self.assertTrue(isinstance(resource_property_mapping[TF_AWS_LAMBDA_LAYER_VERSION], CodeResourceProperties))
