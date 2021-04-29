import os
from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized


from samcli.lib.providers.provider import LayerVersion, Stack, _get_build_dir
from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn, UnsupportedIntrinsic


def make_resource(stack_path, name):
    resource = Mock()
    resource.stack_path = stack_path
    resource.name = name
    return resource


class TestProvider(TestCase):
    @parameterized.expand(
        [
            (make_resource("", "A"), os.path.join("builddir", "A")),
            (make_resource("A", "B"), os.path.join("builddir", "A", "B")),
            (make_resource("A/B", "C"), os.path.join("builddir", "A", "B", "C")),
        ]
    )
    def test_stack_build_dir(self, resource, output_build_dir):
        self.assertEqual(_get_build_dir(resource, "builddir"), output_build_dir)

    @parameterized.expand(
        [
            ("", "", os.path.join("builddir", "template.yaml")),  # root stack
            ("", "A", os.path.join("builddir", "A", "template.yaml")),
            ("A", "B", os.path.join("builddir", "A", "B", "template.yaml")),
            ("A/B", "C", os.path.join("builddir", "A", "B", "C", "template.yaml")),
        ]
    )
    def test_stack_get_output_template_path(self, parent_stack_path, name, output_template_path):
        root_stack = Stack(parent_stack_path, name, None, None, None)
        self.assertEqual(root_stack.get_output_template_path("builddir"), output_template_path)


class TestLayerVersion(TestCase):
    @parameterized.expand(
        [
            ("arn:aws:lambda:region:account-id:layer:layer-name:a"),
            ("arn:aws:lambda:region:account-id:layer"),
            ("a string without delimiter"),
        ]
    )
    def test_invalid_arn(self, arn):
        layer = LayerVersion("layer-id", arn, None)  # creation of layer does not raise exception
        with self.assertRaises(InvalidLayerVersionArn):
            layer.version, layer.name

    def test_layer_version_returned(self):
        layer_version = LayerVersion("layer-id", "arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.version, 1)

    def test_layer_arn_returned(self):
        layer_version = LayerVersion("layer-id", "arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.layer_arn, "arn:aws:lambda:region:account-id:layer:layer-name")

    def test_layer_build_method_returned(self):
        layer_version = LayerVersion(
            "layer-id",
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            None,
            [],
            {"BuildMethod": "dummy_build_method"},
        )

        self.assertEqual(layer_version.build_method, "dummy_build_method")

    def test_codeuri_is_setable(self):
        layer_version = LayerVersion("layer-id", "arn:aws:lambda:region:account-id:layer:layer-name:1", None)
        layer_version.codeuri = "./some_value"

        self.assertEqual(layer_version.codeuri, "./some_value")

    def test_name_is_computed(self):
        layer_version = LayerVersion(None, "arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.name, "layer-name-1-8cebcd0539")

    def test_layer_version_is_defined_in_template(self):
        layer_version = LayerVersion("layer-id", "arn:aws:lambda:region:account-id:layer:layer-name:1", ".")

        self.assertTrue(layer_version.is_defined_within_template)

    def test_layer_version_raises_unsupported_intrinsic(self):
        intrinsic_arn = {
            "Fn::Sub": ["arn:aws:lambda:region:account-id:layer:{layer_name}:1", {"layer_name": "layer-name"}]
        }

        with self.assertRaises(UnsupportedIntrinsic):
            LayerVersion("layer-id", intrinsic_arn, ".")
