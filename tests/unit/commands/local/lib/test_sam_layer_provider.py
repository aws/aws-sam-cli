from unittest import TestCase
from unittest.mock import patch, MagicMock

from parameterized import parameterized

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionContentUri
from samcli.lib.providers.provider import LayerVersion
from samcli.lib.providers.sam_layer_provider import SamLayerProvider


class TestSamLayerProvider(TestCase):
    TEMPLATE = {
        "Resources": {
            "ServerlessLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
            "LambdaLayer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
            "ServerlessLayerNoBuild": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
            },
            "LambdaLayerNoBuild": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
            },
            "ServerlessLayerS3Content": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "s3://dummy-bucket/my-layer.zip",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
            },
            "LambdaLayerS3Content": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": {"S3Bucket": "dummy-bucket", "S3Key": "layer.zip"},
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
            },
            "SamFunc": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
        }
    }

    def setUp(self):
        self.parameter_overrides = {}
        with patch("os.path.exists", MagicMock(return_value=True)):
            self.provider = SamLayerProvider(self.TEMPLATE, parameter_overrides=self.parameter_overrides)

    @parameterized.expand(
        [
            (
                "ServerlessLayer",
                ("ServerlessLayer", "PyLayer/", ["python3.8", "python3.6"], {"BuildMethod": "python3.8"}),
            ),
            ("LambdaLayer", ("LambdaLayer", "PyLayer/", ["python3.8", "python3.6"], {"BuildMethod": "python3.8"}),),
            ("ServerlessLayerNoBuild", ("ServerlessLayerNoBuild", "PyLayer/", ["python3.8", "python3.6"], None),),
            ("LambdaLayerNoBuild", ("LambdaLayerNoBuild", "PyLayer/", ["python3.8", "python3.6"], None)),
            ("ServerlessLayerS3Content", ("ServerlessLayerS3Content", ".", ["python3.8", "python3.6"], None),),
            ("LambdaLayerS3Content", ("LambdaLayerS3Content", ".", ["python3.8", "python3.6"], None)),
        ]
    )
    @patch("os.path.exists", MagicMock(return_value=True))
    def test_get_must_return_each_layer(self, name, expected_output_layer_args):
        actual = self.provider.get(name)
        self.assertEqual(actual, LayerVersion(*expected_output_layer_args))

    def test_get_all_must_return_all_layers(self):
        result = [f.arn for f in self.provider.get_all()]
        expected = [
            "ServerlessLayer",
            "LambdaLayer",
            "ServerlessLayerNoBuild",
            "LambdaLayerNoBuild",
            "ServerlessLayerS3Content",
            "LambdaLayerS3Content",
        ]

        self.assertEqual(result, expected)

    def test_provider_ignores_non_layer_resource(self):
        self.assertIsNone(self.provider.get("SamFunc"))

    def test_fails_with_empty_name(self):
        with self.assertRaises(ValueError):
            self.provider.get("")

    @patch("os.path.exists", MagicMock(return_value=False))
    def test_fails_with_non_exist_local_layer_directory(self):
        with self.assertRaises(InvalidLayerVersionContentUri):
            self.provider = SamLayerProvider(self.TEMPLATE, parameter_overrides=self.parameter_overrides)
