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
            "LambdaLayerWithCustomId": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": "PyLayer/",
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
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
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
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
            "CDKChildStack": {
                "Type": "AWS::CloudFormation::Stack",
                "Properties": {
                    "Location": "./child.yaml",
                },
                "Metadata": {
                    "aws:cdk:path": "RootStack/CDKChildStack-x.NestedStack/CDKChildStack-x.NestedStackResource",
                    "aws:asset:path": "RootStackCDKChildStackxF279E94E.nested.template.json",
                    "aws:asset:property": "TemplateURL"
                }
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
            }
        }
    }
    CDK_CHILD_TEMPLATE = {
        "Resources": {
            "CDKLambdaLayerInChild": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "LayerName": "Layer1",
                    "Content": {
                        "S3Bucket": "bucket",
                        "S3Key": "key",
                    },
                    "CompatibleRuntimes": ["python3.8", "python3.6"],
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

    parameter_overrides = {}
    ROOT_STACK = Stack("", "", "template.yaml", parameter_overrides, TEMPLATE)
    CHILD_STACK = Stack("", "ChildStack", "./child/template.yaml", None, CHILD_TEMPLATE, parent_stack=ROOT_STACK)
    CDK_CHILD_STACK = Stack("", "CDKChildStack", "./child/template.yaml", None, CDK_CHILD_TEMPLATE, parent_stack=ROOT_STACK, custom_id="CDKChildStack-x")

    def setUp(self):
        with patch("samcli.lib.providers.sam_stack_provider.get_template_data") as get_template_data_mock:
            get_template_data_mock.side_effect = lambda t: {
                "template.yaml": self.TEMPLATE,
                "./child/template.yaml": self.CHILD_TEMPLATE,
                "./child-x/template.yaml": self.CDK_CHILD_TEMPLATE,
            }
            self.provider = SamLayerProvider([self.ROOT_STACK, self.CHILD_STACK, self.CDK_CHILD_STACK])

    @parameterized.expand(
        [
            (
                "ServerlessLayer",
                LayerVersion(
                    "ServerlessLayer",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8", "SamResourceId": "ServerlessLayer"},
                ),
            ),
            (
                "LambdaLayer",
                LayerVersion(
                    "LambdaLayer",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayer"},
                ),
            ),
            (
                "ServerlessLayerNoBuild",
                LayerVersion(
                    "ServerlessLayerNoBuild",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"SamResourceId": "ServerlessLayerNoBuild"},
                ),
            ),
            (
                "LambdaLayerNoBuild",
                LayerVersion(
                    "LambdaLayerNoBuild",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"SamResourceId": "LambdaLayerNoBuild"},
                ),
            ),
            ("ServerlessLayerS3Content", None),  # codeuri is a s3 location, ignored
            ("LambdaLayerS3Content", None),  # codeuri is a s3 location, ignored
            (
                posixpath.join("ChildStack", "SamLayerInChild"),
                LayerVersion(
                    "SamLayerInChild",
                    CHILD_STACK,
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8", "SamResourceId": "SamLayerInChild"},
                ),
            ),
            (
                "LambdaLayerWithCustomId-x",
                LayerVersion(
                    "LambdaLayerWithCustomId",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayerWithCustomId-x"},
                ),
            ),
            (
                "LambdaLayerWithCustomId",
                LayerVersion(
                    "LambdaLayerWithCustomId",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {"BuildMethod": "python3.8", "SamResourceId": "LambdaLayerWithCustomId-x"},
                ),
            ),
            (
                "CDKLambdaLayer-x",
                LayerVersion(
                    "CDKLambdaLayer",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayer-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayer-x",
                    },
                ),
            ),
            (
                "CDKLambdaLayer",
                LayerVersion(
                    "CDKLambdaLayer",
                    ROOT_STACK,
                    "PyLayer",
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayer-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayer-x",
                    },
                ),
            ),
            (
                "CDKLambdaLayerInChild-x",
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    CDK_CHILD_STACK,
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                ),
            ),
            (
                "CDKLambdaLayerInChild",
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    CDK_CHILD_STACK,
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                ),
            ),
            (
                posixpath.join("CDKChildStack-x", "CDKLambdaLayerInChild-x"),
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    CDK_CHILD_STACK,
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                ),
            ),
            (
                posixpath.join("CDKChildStack", "CDKLambdaLayerInChild"),
                LayerVersion(
                    "CDKLambdaLayerInChild",
                    CDK_CHILD_STACK,
                    os.path.join("child", "PyLayer"),
                    ["python3.8", "python3.6"],
                    {
                        "BuildMethod": "python3.8",
                        "aws:cdk:path": "stack/CDKLambdaLayerInChild-x/Resource",
                        "aws:asset:path": "PyLayer/",
                        "aws:asset:property": "Content",
                        "SamNormalized": True,
                        "SamResourceId": "CDKLambdaLayerInChild-x",
                    },
                ),
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
            "LambdaLayerWithCustomId",
            "CDKLambdaLayer",
            "ServerlessLayerNoBuild",
            "LambdaLayerNoBuild",
            posixpath.join("ChildStack", "SamLayerInChild"),
            posixpath.join("CDKChildStack", "CDKLambdaLayerInChild"),
        ]

        self.assertEqual(expected, result)

    def test_provider_ignores_non_layer_resource(self):
        self.assertIsNone(self.provider.get("SamFunc"))

    def test_fails_with_empty_name(self):
        with self.assertRaises(ValueError):
            self.provider.get("")
