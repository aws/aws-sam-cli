from unittest import TestCase
from unittest.mock import patch
from parameterized import parameterized

from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.local.lib.validators.lambda_auth_props import (
    LambdaAuthorizerV1Validator,
    LambdaAuthorizerV2Validator,
)


class TestLambdaAuthorizerV1Validator(TestCase):
    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_valid_v1_properties(self, function_mock):
        logical_id = "id"
        properties = {
            "Properties": {
                "Type": "REQUEST",
                "RestApiId": "my-rest-api",
                "Name": "my-auth-name",
                "AuthorizerUri": "arn",
                "IdentitySource": "method.request.header.auth, method.request.querystring.abc",
            }
        }

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        function_mock.return_value = auth_lambda_func_name

        self.assertTrue(LambdaAuthorizerV1Validator.validate(logical_id, properties))

    @parameterized.expand(
        [
            (  # test no type
                {"Properties": {}},
                "Authorizer 'my-auth-id' is missing the 'Type' property, an Authorizer type must be defined.",
            ),
            (  # test no rest api id
                {"Properties": {"Type": "TOKEN"}},
                "Authorizer 'my-auth-id' is missing the 'RestApiId' property, this must be defined.",
            ),
            (  # test no name
                {"Properties": {"Type": "TOKEN", "RestApiId": "restapiid"}},
                "Authorizer 'my-auth-id' is missing the 'Name' property, the Name must be defined.",
            ),
            (  # test no authorizer uri
                {"Properties": {"Type": "TOKEN", "RestApiId": "restapiid", "Name": "myauth"}},
                "Authorizer 'my-auth-id' is missing the 'AuthorizerUri' property, a valid Lambda ARN must be provided.",
            ),
            (  # test invalid identity source (missing)
                {"Properties": {"Type": "TOKEN", "RestApiId": "restapiid", "Name": "myauth", "AuthorizerUri": "arn"}},
                "Lambda Authorizer 'my-auth-id' of type TOKEN, must have 'IdentitySource' of type string defined.",
            ),
            (  # test invalid identity source (must be str)
                {
                    "Properties": {
                        "Type": "TOKEN",
                        "RestApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                        "IdentitySource": {},
                    }
                },
                "Lambda Authorizer 'my-auth-id' contains an invalid 'IdentitySource', it must be a comma-separated string.",
            ),
            (  # test request type using validation
                {
                    "Properties": {
                        "Type": "REQUEST",
                        "RestApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                        "IdentityValidationExpression": "123",
                    }
                },
                "Lambda Authorizer 'my-auth-id' has 'IdentityValidationExpression' property defined, but validation is only supported on TOKEN type authorizers.",
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v1_lamabda_authorizers(self, resource, expected_exception_message, get_func_name_mock):
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        get_func_name_mock.return_value = auth_lambda_func_name

        with self.assertRaisesRegex(InvalidSamTemplateException, expected_exception_message):
            LambdaAuthorizerV1Validator.validate(lambda_auth_logical_id, resource)

    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v1_skip_invalid_type(self, get_func_name_mock):
        properties = {"Properties": {"Type": "_-_-_", "RestApiId": "restapiid", "Name": "myauth"}}
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        get_func_name_mock.return_value = auth_lambda_func_name

        self.assertFalse(LambdaAuthorizerV1Validator.validate(lambda_auth_logical_id, properties))

    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v1_skip_invalid_arn(self, get_func_name_mock):
        properties = {
            "Properties": {"Type": "TOKEN", "RestApiId": "restapiid", "Name": "myauth", "AuthorizerUri": "arn"}
        }
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function to return None
        get_func_name_mock.return_value = None

        self.assertFalse(LambdaAuthorizerV1Validator.validate(lambda_auth_logical_id, properties))


class TestLambdaAuthorizerV2Validator(TestCase):
    @parameterized.expand(
        [
            (  # authorizer with 2.0 payload and simple responses
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "my-rest-api",
                        "Name": "my-auth-name",
                        "AuthorizerUri": "arn",
                        "IdentitySource": ["$request.header.auth", "$context.something"],
                        "AuthorizerPayloadFormatVersion": "2.0",
                        "EnableSimpleResponses": True,
                    }
                },
            ),
            (  # authorizer with 2.0 payload and NO simple responses
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "my-rest-api",
                        "Name": "my-auth-name",
                        "AuthorizerUri": "arn",
                        "IdentitySource": ["$request.header.auth", "$context.something"],
                        "AuthorizerPayloadFormatVersion": "2.0",
                        "EnableSimpleResponses": False,
                    }
                },
            ),
            (  # authorizer with 1.0 payload and NO simple responses
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "my-rest-api",
                        "Name": "my-auth-name",
                        "AuthorizerUri": "arn",
                        "IdentitySource": ["$request.header.auth", "$context.something"],
                        "AuthorizerPayloadFormatVersion": "1.0",
                    }
                },
            ),
            (  # authorizer with missing payload version
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "my-rest-api",
                        "Name": "my-auth-name",
                        "AuthorizerUri": "arn",
                        "IdentitySource": ["$request.header.auth", "$context.something"],
                    }
                },
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_valid_v2_properties(self, properties, function_mock):
        logical_id = "id"

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        function_mock.return_value = auth_lambda_func_name

        self.assertTrue(LambdaAuthorizerV2Validator.validate(logical_id, properties))

    @parameterized.expand(
        [
            (  # test no type
                {"Properties": {}},
                "Authorizer 'my-auth-id' is missing the 'AuthorizerType' property, an Authorizer type must be defined.",
            ),
            (  # test no rest api id
                {"Properties": {"AuthorizerType": "REQUEST"}},
                "Authorizer 'my-auth-id' is missing the 'ApiId' property, this must be defined.",
            ),
            (  # test no name
                {"Properties": {"AuthorizerType": "REQUEST", "ApiId": "restapiid"}},
                "Authorizer 'my-auth-id' is missing the 'Name' property, the Name must be defined.",
            ),
            (  # test no authorizer uri
                {"Properties": {"AuthorizerType": "REQUEST", "ApiId": "restapiid", "Name": "myauth"}},
                "Authorizer 'my-auth-id' is missing the 'AuthorizerUri' property, a valid Lambda ARN must be provided.",
            ),
            (  # test invalid identity source (missing)
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                    }
                },
                "Lambda Authorizer 'my-auth-id' must have 'IdentitySource' of type list defined.",
            ),
            (  # test invalid identity source (must be list)
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                        "IdentitySource": "hello world, im not a list",
                    }
                },
                "Lambda Authorizer 'my-auth-id' must have 'IdentitySource' of type list defined.",
            ),
            (  # test invalid payload version
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                        "IdentitySource": [],
                        "AuthorizerPayloadFormatVersion": "1.2.3",
                    }
                },
                "Lambda Authorizer 'my-auth-id' contains an invalid 'AuthorizerPayloadFormatVersion', it must be set to '1.0' or '2.0'",
            ),
            (  # test using simple response but wrong payload version
                {
                    "Properties": {
                        "AuthorizerType": "REQUEST",
                        "ApiId": "restapiid",
                        "Name": "myauth",
                        "AuthorizerUri": "arn",
                        "IdentitySource": [],
                        "AuthorizerPayloadFormatVersion": "1.0",
                        "EnableSimpleResponses": True,
                    }
                },
                "'EnableSimpleResponses' is only supported for '2.0' payload format versions for Lambda Authorizer 'my-auth-id'.",
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v2_lamabda_authorizers(self, resource, expected_exception_message, get_func_name_mock):
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        get_func_name_mock.return_value = auth_lambda_func_name

        with self.assertRaisesRegex(InvalidSamTemplateException, expected_exception_message):
            LambdaAuthorizerV2Validator.validate(lambda_auth_logical_id, resource)

    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v2_skip_invalid_type(self, get_func_name_mock):
        properties = {"Properties": {"AuthorizerType": "TOKEN", "ApiId": "restapiid", "Name": "myauth"}}
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function
        auth_lambda_func_name = "my-lambda"
        get_func_name_mock.return_value = auth_lambda_func_name

        self.assertFalse(LambdaAuthorizerV2Validator.validate(lambda_auth_logical_id, properties))

    @patch("samcli.commands.local.lib.swagger.integration_uri.LambdaUri.get_function_name")
    def test_invalid_v2_skip_invalid_arn(self, get_func_name_mock):
        properties = {
            "Properties": {"AuthorizerType": "REQUEST", "ApiId": "restapiid", "Name": "myauth", "AuthorizerUri": "arn"}
        }
        lambda_auth_logical_id = "my-auth-id"

        # mock ARN resolving function to return None
        get_func_name_mock.return_value = None

        self.assertFalse(LambdaAuthorizerV2Validator.validate(lambda_auth_logical_id, properties))
