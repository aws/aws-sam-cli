from samcli.lib.providers.provider import ResourceIdentifier
from samcli.lib.utils.resource_type_based_factory import ResourceTypeBasedFactory
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch


class TestResourceTypeBasedFactory(TestCase):
    def setUp(self):
        self.abstract_method_patch = patch.multiple(ResourceTypeBasedFactory, __abstractmethods__=set())
        self.abstract_method_patch.start()
        self.stacks = [MagicMock(), MagicMock()]
        self.factory = ResourceTypeBasedFactory(self.stacks)
        self.function_generator_mock = MagicMock()
        self.layer_generator_mock = MagicMock()
        self.factory._get_generator_mapping = MagicMock()
        self.factory._get_generator_mapping.return_value = {
            "AWS::Lambda::Function": self.function_generator_mock,
            "AWS::Lambda::LayerVersion": self.layer_generator_mock,
        }

    def tearDown(self):
        self.abstract_method_patch.stop()

    @patch("samcli.lib.utils.resource_type_based_factory.get_resource_by_id")
    def test_get_generator_function_valid(self, get_resource_by_id_mock):
        resource = {"Type": "AWS::Lambda::Function"}
        get_resource_by_id_mock.return_value = resource

        generator = self.factory._get_generator_function(ResourceIdentifier("Resource1"))
        self.assertEqual(generator, self.function_generator_mock)

    @patch("samcli.lib.utils.resource_type_based_factory.get_resource_by_id")
    def test_get_generator_function_unknown_type(self, get_resource_by_id_mock):
        resource = {"Type": "AWS::Unknown::Type"}
        get_resource_by_id_mock.return_value = resource

        generator = self.factory._get_generator_function(ResourceIdentifier("Resource1"))

        self.assertEqual(None, generator)

    @patch("samcli.lib.utils.resource_type_based_factory.get_resource_by_id")
    def test_get_generator_function_no_type(self, get_resource_by_id_mock):
        resource = {"Properties": {}}
        get_resource_by_id_mock.return_value = resource

        generator = self.factory._get_generator_function(ResourceIdentifier("Resource1"))

        self.assertEqual(None, generator)
