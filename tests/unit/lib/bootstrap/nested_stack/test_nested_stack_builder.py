from unittest import TestCase

from samcli.lib.bootstrap.nested_stack.nested_stack_builder import NestedStackBuilder
from samcli.lib.providers.provider import Function
from samcli.lib.utils.resources import AWS_SERVERLESS_LAYERVERSION
from tests.unit.lib.build_module.test_build_graph import generate_function


class TestNestedStackBuilder(TestCase):
    def setUp(self) -> None:
        self.nested_stack_builder = NestedStackBuilder()

    def test_no_function_added(self):
        self.assertFalse(self.nested_stack_builder.is_any_function_added())

    def test_with_function_added(self):
        function_runtime = "runtime"
        stack_name = "stack_name"
        function_logical_id = "FunctionLogicalId"
        layer_contents_folder = "layer/contents/folder"

        function = generate_function(function_id=function_logical_id, runtime=function_runtime)
        self.nested_stack_builder.add_function(stack_name, layer_contents_folder, function)

        self.assertTrue(self.nested_stack_builder.is_any_function_added())

        nested_template = self.nested_stack_builder.build_as_dict()
        resources = nested_template.get("Resources", {})
        outputs = nested_template.get("Outputs", {})

        self.assertEqual(len(resources), 1)
        self.assertEqual(len(outputs), 1)

        layer_logical_id = list(resources.keys())[0]
        self.assertTrue(layer_logical_id.startswith(function_logical_id))
        self.assertTrue(layer_logical_id.endswith("DepLayer"))

        layer_resource = list(resources.values())[0]
        self.assertEqual(layer_resource.get("Type"), AWS_SERVERLESS_LAYERVERSION)

        layer_properties = layer_resource.get("Properties", {})
        layer_name = layer_properties.get("LayerName")
        self.assertTrue(layer_name.startswith(stack_name))
        self.assertIn(function_logical_id, layer_name)
        self.assertTrue(layer_name.endswith("DepLayer"))

        self.assertEqual(layer_properties.get("ContentUri"), layer_contents_folder)
        self.assertEqual(layer_properties.get("RetentionPolicy"), "Delete")
        self.assertIn(function_runtime, layer_properties.get("CompatibleRuntimes"))

        layer_output_key = list(outputs.keys())[0]
        self.assertTrue(layer_output_key.startswith(function_logical_id))
        self.assertTrue(layer_output_key.endswith("DepLayer"))

        layer_output = list(outputs.values())[0]
        self.assertIn("Value", layer_output.keys())

        layer_output_value = layer_output.get("Value")
        self.assertIn("Ref", layer_output_value)
        self.assertEqual(layer_output_value.get("Ref"), layer_logical_id)

    def test_get_layer_logical_id(self):
        function_logical_id = "function_logical_id"
        layer_logical_id = NestedStackBuilder.get_layer_logical_id(function_logical_id)

        self.assertTrue(layer_logical_id.startswith(function_logical_id[:48]))
        self.assertTrue(layer_logical_id.endswith("DepLayer"))
        self.assertLessEqual(len(layer_logical_id), 64)

    def test_get_layer_name(self):
        function_logical_id = "function_logical_id"
        stack_name = "function_logical_id"
        layer_name = NestedStackBuilder.get_layer_name(stack_name, function_logical_id)

        self.assertTrue(layer_name.startswith(stack_name[:16]))
        self.assertTrue(layer_name.endswith("DepLayer"))
        self.assertIn(function_logical_id[:22], layer_name)
        self.assertLessEqual(len(layer_name), 64)
