import os
import posixpath
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.providers.provider import LayerVersion, Stack
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
            "ChildStack": {
                "Type": "AWS::Serverless::Application",
                "Properties": {
                    "Location": "./child.yaml",
                },
            },
        }
    }

    CHILD_TEMPLATE = {
        "Resources": {
            "SamLayerInChild": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "PyLayer",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
        }
    }

    def setUp(self):
        self.parameter_overrides = {}
        root_stack = Stack("", "", "template.yaml", self.parameter_overrides, self.TEMPLATE)
        child_stack = Stack("", "ChildStack", "./child/template.yaml", None, self.CHILD_TEMPLATE)
        with patch("samcli.lib.providers.sam_stack_provider.get_template_data") as get_template_data_mock:
            get_template_data_mock.side_effect = lambda t: {
                "template.yaml": self.TEMPLATE,
                "./child/template.yaml": self.CHILD_TEMPLATE,
            }
            self.provider = SamLayerProvider([root_stack, child_stack])

    @parameterized.expand(
        [
            (
                "ServerlessLayer",
                LayerVersion(
                    "ServerlessLayer",
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8"},
                    stack_path="",
                ),
            ),
            (
                "LambdaLayer",
                LayerVersion(
                    "LambdaLayer",
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8"},
                    stack_path="",
                ),
            ),
            (
                "ServerlessLayerNoBuild",
                LayerVersion("ServerlessLayerNoBuild", "PyLayer", ["python3.8", "python3.6"], None, stack_path=""),
            ),
            (
                "LambdaLayerNoBuild",
                LayerVersion("LambdaLayerNoBuild", "PyLayer", ["python3.8", "python3.6"], None, stack_path=""),
            ),
            ("ServerlessLayerS3Content", None),  # codeuri is a s3 location, ignored
            ("LambdaLayerS3Content", None),  # codeuri is a s3 location, ignored
            (
                posixpath.join("ChildStack", "SamLayerInChild"),
                LayerVersion(
                    "SamLayerInChild",
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8"},
                    stack_path="ChildStack",
                ),
            ),
        ]
    )
    def test_get_must_return_each_layer(self, name, expected_output):
        actual = self.provider.get(name)
        self.assertEqual(expected_output, actual)

    def test_get_all_must_return_all_layers(self):
        result = [posixpath.join(f.stack_path, f.arn) for f in self.provider.get_all()]
        expected = [
            "ServerlessLayer",
            "LambdaLayer",
            "ServerlessLayerNoBuild",
            "LambdaLayerNoBuild",
            posixpath.join("ChildStack", "SamLayerInChild"),
        ]

        self.assertEqual(expected, result)

    def test_provider_ignores_non_layer_resource(self):
        self.assertIsNone(self.provider.get("SamFunc"))

    def test_fails_with_empty_name(self):
        with self.assertRaises(ValueError):
            self.provider.get("")
