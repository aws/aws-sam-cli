"""
Guards `sam validate --lint` against a cfn-lint that does not cover every SAM resource type.

cfn-lint 1.54.0 dropped the SAM transform and started validating AWS::Serverless resources against
schemas it bundles itself, so a resource type it has no schema for fails a valid template with
E3006. See aws-cloudformation/cfn-lint#4678 and the cfn-lint bound in pyproject.toml.
"""

import inspect
import json
from typing import Any, Dict, Set
from unittest import TestCase

from cfnlint.api import ManualArgs, lint
from samtranslator.model import sam_resources

REGION = "us-east-1"


def get_sam_resource_types() -> Set[str]:
    """Every AWS::Serverless resource type the installed SAM translator can expand."""
    resource_types = set()
    for member in vars(sam_resources).values():
        resource_type = getattr(member, "resource_type", None) if inspect.isclass(member) else None
        if isinstance(resource_type, str) and resource_type.startswith("AWS::Serverless::"):
            resource_types.add(resource_type)
    return resource_types


def get_all_sam_resource_types_template() -> Dict[str, Any]:
    """A valid template holding one of every SAM resource type, so linting it must report nothing."""
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Transform": "AWS::Serverless-2016-10-31",
        "Resources": {
            "Api": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"StageName": "prod", "DefinitionUri": "s3://bucket/api.yaml"},
            },
            "Application": {
                "Type": "AWS::Serverless::Application",
                "Properties": {"Location": "s3://bucket/app.yaml"},
            },
            "CapacityProvider": {
                "Type": "AWS::Serverless::CapacityProvider",
                "Properties": {
                    "VpcConfig": {
                        "SubnetIds": ["subnet-0123456789abcdef0"],
                        "SecurityGroupIds": ["sg-0123456789abcdef0"],
                    }
                },
            },
            "Connector": {
                "Type": "AWS::Serverless::Connector",
                "Properties": {
                    "Source": {"Id": "Function"},
                    "Destination": {"Id": "SimpleTable"},
                    "Permissions": ["Read"],
                },
            },
            "Function": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "InlineCode": "def handler(event, context): pass",
                    "Handler": "index.handler",
                    "Runtime": "python3.13",
                },
            },
            "GraphQLApi": {
                "Type": "AWS::Serverless::GraphQLApi",
                "Properties": {"Auth": {"Type": "AWS_IAM"}, "SchemaInline": "type Query { hello: String }"},
            },
            "HttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {}},
            "LayerVersion": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {"ContentUri": "s3://bucket/layer.zip"},
            },
            "MicrovmImage": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "image",
                    "CodeUri": "s3://bucket/code.zip",
                    "BaseImageArn": "arn:aws:lambda:us-east-1:123456789012:microvm-base-image/base",
                    "BaseImageVersion": "1",
                },
            },
            "NetworkConnector": {
                "Type": "AWS::Serverless::NetworkConnector",
                "Properties": {
                    "VpcConfig": {
                        "SubnetIds": ["subnet-0123456789abcdef0"],
                        "SecurityGroupIds": ["sg-0123456789abcdef0"],
                        "NetworkProtocol": "IPv4",
                    }
                },
            },
            "SimpleTable": {"Type": "AWS::Serverless::SimpleTable", "Properties": {}},
            "StateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"Definition": {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}},
            },
            "WebSocketApi": {
                "Type": "AWS::Serverless::WebSocketApi",
                "Properties": {
                    "RouteSelectionExpression": "$request.body.action",
                    "Routes": {"$connect": {"FunctionArn": {"Fn::GetAtt": ["Function", "Arn"]}}},
                },
            },
        },
    }


class TestLintEverySamResourceType(TestCase):
    def test_lint_every_sam_resource_type(self):
        # A resource type cfn-lint does not cover fails a valid template, so lint one of each.
        template = get_all_sam_resource_types_template()

        # Fails when SAM gains a resource type the template does not cover.
        self.assertEqual(
            {resource["Type"] for resource in template["Resources"].values()},
            get_sam_resource_types(),
            "Add the new SAM resource type to get_all_sam_resource_types_template",
        )

        # Reaches cfn-lint the same way samcli.commands.validate.validate._lint does.
        matches = lint(json.dumps(template), config=ManualArgs(regions=[REGION]))

        self.assertEqual(matches, [], f"cfn-lint rejected a valid SAM template: {matches}")
