"""
Unit test for Lambda Integration URI parsing
"""

import logging

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri
from unittest import TestCase
from parameterized import parameterized


logging.basicConfig(level=logging.DEBUG)


class TestLambdaUri(TestCase):

    FUNCTION_NAME = "MyCoolFunction"

    SUCCESS_CASES = [
        (
            "URI is a fully resolved ARN",
            "arn:aws:lambda:us-east-1:123456789012:function:MyCoolFunction",
        ),
        (
            "URI is a fully resolved ARN with an alias",
            "arn:aws:lambda:us-east-1:123456789012:function:MyCoolFunction:ProdAlias",
        ),
        (
            "URI is a string with fully resolved ARN",
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:MyCoolFunction/invocations",  # NOQA
        ),
        (
            "URI is a full ARN with any region and any account id",
            "arn:aws:apigateway:<<someregion>>:<<someservice>>:path/2015-03-31/functions/arn:aws:lambda:region:accountid:function:MyCoolFunction/invocations",  # NOQA
        ),
        (
            "URI is a Fn::Sub with a Lambda ARN as a variable",
            {
                "Fn::Sub": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyCoolFunction.Arn}/invocations"  # NOQA
            },
        ),
        (
            "URI is a Fn::Sub with a Lambda Alias as a variable",
            {
                "Fn::Sub": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyCoolFunction.Alias}/invocations"  # NOQA
            },
        ),
        (
            "URI is a Fn::Sub with a Lambda ARN as a variable in addition to others provided as string",
            {
                "Fn::Sub": "arn:${AWS::Partition}:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${MyCoolFunction.Arn}/invocations"  # NOQA
            },
        ),
        (
            "URI is a Fn::Sub with a Lambda ARN as a variable in addition to others provided as array",
            {
                "Fn::Sub": [
                    "arn:aws:apigateway:${region}:lambda:path/2015-03-31/functions/${MyCoolFunction.Arn}/invocations",
                    {"region": {"Ref": "AWS::Region"}},
                ]
            },
        ),
        (
            "URI is a Fn::Sub resolvable intrinsic as an array",
            {
                "Fn::Sub": [
                    "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyCoolFunction.Arn}/invocations"
                ]
            },
        ),
        (
            "URI is a string with just enough information to pass regex tests",
            "foo/functions/bar:function:MyCoolFunction/invocations",  # NOQA
        ),
    ]

    @parameterized.expand(SUCCESS_CASES)
    def test_get_function_name_success(self, test_case_name, uri):

        result = LambdaUri.get_function_name(uri)
        self.assertEqual(result, self.FUNCTION_NAME)

    FAILURE_CASES = [
        (
            "URI is a string with stage variables",
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:${stageVariables.FunctionName}/invocations",  # NOQA
        ),
        (
            "URI is an ARN string of non-Lambda resource",
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:something:us-east-1:123456789012:event:MyCoolFunction/invocations",  # NOQA
        ),
        ("URI is a random string", "hello world"),
        (
            "URI is an integration ARN without proper Lambda function name",
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:${ThisIntrinsicDidntGetSubstituted}/invocations",  # NOQA
        ),
        ("URI is a list", [1, 2, 3]),
        (
            "URI is a dictionary with more than one keys",
            {
                "Fn::Sub": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyCoolFunction.Arn}/invocations",  # NOQA
                "SomeKey": "value",
            },
        ),
        ("URI is a Ref", {"Ref": "MyCoolFunction"}),
        ("URI is a GetAtt", {"Fn::GetAtt": "MyCoolFunction.Arn"}),
        (
            "URI is a Fn::Sub with array values that would resolve in CloudFormation",
            {
                "Fn::Sub": [
                    # In CloudFormation this intrinsic function will resolve to correct function name.
                    # But unfortunately we don't support this here
                    "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyArn}/invocations",
                    {"MyArn": {"Fn::GetAtt": "MyCoolFunction.Arn"}},
                ]
            },
        ),
        (
            "URI is a Fn::Sub with intrinsic that does not return an Arn or Alias",
            {
                "Fn::Sub": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${MyCoolFunction}/invocations"  # NOQA
            },
        ),
        (
            "URI is a Fn::Sub with ignored variable created with ${! syntax",
            {
                "Fn::Sub": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${!MyCoolFunction.Arn}/invocations"  # NOQA
            },
        ),
        ("URI is a Fn::Sub is invalid in structure", {"Fn::Sub": {"foo": "bar"}}),
        ("URI is empty string", ""),
        ("URI without enough information to pass regex test", "bar:function:MyCoolFunction/invocations"),
    ]

    @parameterized.expand(FAILURE_CASES)
    def test_get_function_name_failure(self, test_case_name, uri):

        result = LambdaUri.get_function_name(uri)
        self.assertIsNone(result, "Must fail to get function name when " + test_case_name)
