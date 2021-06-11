from unittest import TestCase
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    LayerPhysicalIdNotFoundError,
)


class TestMissingPhysicalResourceError(TestCase):
    def test_exception(self):
        exception = MissingPhysicalResourceError("A")
        self.assertEqual(exception.resource_identifier, "A")


class TestNoLayerVersionsFoundError(TestCase):
    def test_exception(self):
        exception = NoLayerVersionsFoundError("layer_name_arn")
        self.assertEqual(exception.layer_name_arn, "layer_name_arn")


class TestLayerPhysicalIdNotFoundError(TestCase):
    def test_exception(self):
        given_layer_name = "LayerName"
        given_resources = ["ResourceA", "ResourceB"]

        exception = LayerPhysicalIdNotFoundError(given_layer_name, given_resources)

        self.assertEqual(given_layer_name, exception.layer_name)
        self.assertEqual(given_resources, exception.stack_resource_names)
