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
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
            "LambdaLayer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
            "LambdaLayerWithCustomId": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayerWithCustomId-x"},
            },
            "CDKLambdaLayer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": {
                        "S3Bucket": "bucket",
                        "S3Key": "key",
                    },
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {
                    "BuildMethod": "python3.8",
                    "aws:cdk:path": "stack/CDKLambdaLayer-x/Resource",
                    "aws:asset:path": "PyLayer/",
                    "aws:asset:property": "Content",
                },
            },
            "ServerlessLayerNoBuild": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
            },
            "LambdaLayerNoBuild": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
            },
            "ServerlessLayerS3Content": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "ContentUri": "s3://dummy-bucket/my-layer.zip",
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
            },
            "LambdaLayerS3Content": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": {"S3Bucket": "dummy-bucket", "S3Key": "layer.zip"},
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
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
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {"BuildMethod": "python3.8"},
            },
            "CDKLambdaLayerInChild": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": {
                        "S3Bucket": "bucket",
                        "S3Key": "key",
                    },
                    "CompatibleRuntimes": ["python3.8", "python3.9"],
                },
                "Metadata": {
                    "BuildMethod": "python3.8",
                    "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                    "aws:asset:path": "PyLayer/",
                    "aws:asset:property": "Content",
                },
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
                    ["python3.8", "python3.9"],
                    {"BuildMethod": "python3.8", "SamResourceId": "ServerlessLayer"},
                    stack_path="",
                ),
            ),
            (
                "LambdaLayer",
                LayerVersion(
                    "LambdaLayer",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayer"},
                    stack_path="",
                ),
            ),
            (
                "ServerlessLayerNoBuild",
                LayerVersion(
                    "ServerlessLayerNoBuild",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {"SamResourceId": "ServerlessLayerNoBuild"},
                    stack_path="",
                ),
            ),
            (
                "LambdaLayerNoBuild",
                LayerVersion(
                    "LambdaLayerNoBuild",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {"SamResourceId": "LambdaLayerNoBuild"},
                    stack_path="",
                ),
            ),
            ("ServerlessLayerS3Content", None),  # codeuri is a s3 location, ignored
            ("LambdaLayerS3Content", None),  # codeuri is a s3 location, ignored
            (
                posixpath.join("ChildStack", "SamLayerInChild"),
                LayerVersion(
                    "SamLayerInChild",
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.9"],
                    {"BuildMethod": "python3.8", "SamResourceId": "SamLayerInChild"},
                    stack_path="ChildStack",
                ),
            ),
            (
                "LambdaLayerWithCustomId-x",
                LayerVersion(
                    "LambdaLayerWithCustomId",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayerWithCustomId-x"},
                    stack_path="",
                ),
            ),
            (
                "LambdaLayerWithCustomId",
                LayerVersion(
                    "LambdaLayerWithCustomId",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayerWithCustomId-x"},
                    stack_path="",
                ),
            ),
            (
                "CDKLambdaLayer-x",
                LayerVersion(
                    "CDKLambdaLayer",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayer-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayer-x",
                    },
                    stack_path="",
                ),
            ),
            (
                "CDKLambdaLayer",
                LayerVersion(
                    "CDKLambdaLayer",
                    "PyLayer",
                    ["python3.8", "python3.9"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayer-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayer-x",
                    },
                    stack_path="",
                ),
            ),
            (
                "CDKLambdaLayerInChild-x",
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.9"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                    stack_path="ChildStack",
                ),
            ),
            (
                "CDKLambdaLayerInChild",
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.9"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                    stack_path="ChildStack",
                ),
            ),
            (
                posixpath.join("ChildStack", "CDKLambdaLayerInChild-x"),
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.9"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                    stack_path="ChildStack",
                ),
            ),
            (
                # resource_Iac_id is used to build full_path, so logical id could not be used in full_path if
                # resource_iac_id exists
                posixpath.join("ChildStack", "CDKLambdaLayerInChild"),
                None,
            ),
        ]
    )
    def test_get_must_return_each_layer(self, name, expected_output):
        actual = self.provider.get(name)
        self.assertEqual(expected_output, actual)

    def test_get_all_must_return_all_layers(self):
        result = [f.full_path for f in self.provider.get_all()]
        expected = [
            "ServerlessLayer",
            "LambdaLayer",
            "LambdaLayerWithCustomId-x",
            "CDKLambdaLayer-x",
            "ServerlessLayerNoBuild",
            "LambdaLayerNoBuild",
            posixpath.join("ChildStack", "SamLayerInChild"),
            posixpath.join("ChildStack", "CDKLambdaLayerInChild-x"),
        ]

        self.assertEqual(expected, result)

    def test_provider_ignores_non_layer_resource(self):
        self.assertIsNone(self.provider.get("SamFunc"))

    def test_fails_with_empty_name(self):
        with self.assertRaises(ValueError):
            self.provider.get("")
