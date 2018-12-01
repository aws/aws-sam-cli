from unittest import TestCase

from parameterized import parameterized

from samcli.commands.local.lib.provider import LayerVersion
from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn, UnsupportedIntrinsic


class TestLayerVersion(TestCase):

    @parameterized.expand([
        ("arn:aws:lambda:region:account-id:layer:layer-name:a"),
        ("arn:aws:lambda:region:account-id:layer"),
        ("a string without delimiter")
    ])
    def test_invalid_arn(self, arn):
        with self.assertRaises(InvalidLayerVersionArn):
            LayerVersion(arn, None)

    def test_layer_version_returned(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEquals(layer_version.version, 1)

    def test_layer_arn_returned(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEquals(layer_version.layer_arn, "arn:aws:lambda:region:account-id:layer:layer-name")

    def test_codeuri_is_setable(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)
        layer_version.codeuri = "./some_value"

        self.assertEquals(layer_version.codeuri, "./some_value")

    def test_name_is_computed(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEquals(layer_version.name, "layer-name-1-8cebcd0539")

    def test_layer_version_is_defined_in_template(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", ".")

        self.assertTrue(layer_version.is_defined_within_template)

    def test_layer_version_raises_unsupported_intrinsic(self):
        intrinsic_arn = {
            "Fn::Sub":
                [
                    "arn:aws:lambda:region:account-id:layer:{layer_name}:1",
                    {
                        "layer_name": "layer-name"
                    }
                ]
        }

        with self.assertRaises(UnsupportedIntrinsic):
            LayerVersion(intrinsic_arn, ".")
