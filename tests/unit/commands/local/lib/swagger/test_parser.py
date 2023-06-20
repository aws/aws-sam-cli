"""
Test the swagger parser
"""
from unittest import TestCase

from unittest.mock import ANY, patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.local.apigw.exceptions import (
    IncorrectOasWithDefaultAuthorizerException,
    InvalidOasVersion,
    InvalidSecurityDefinition,
    MultipleAuthorizerException,
)
from samcli.local.apigw.route import Route
from samcli.local.apigw.authorizers.lambda_authorizer import LambdaAuthorizer


class TestSwaggerParser_get_apis(TestCase):
    def setUp(self) -> None:
        self.stack_path = Mock()

    def test_with_one_path_method(self):
        function_name = "myfunction"
        swagger = {
            "paths": {"/path1": {"get": {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}}}}
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock()
        parser._get_integration_function_name.return_value = function_name

        expected = [
            Route(
                path="/path1",
                methods=["get"],
                function_name=function_name,
                stack_path=self.stack_path,
            )
        ]
        result = parser.get_routes()

        self.assertEqual(expected, result)
        parser._get_integration_function_name.assert_called_with(
            {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}}
        )

    def test_with_combination_of_paths_methods(self):
        function_name = "myfunction"
        swagger = {
            "paths": {
                "/path1": {
                    "get": {"x-amazon-apigateway-integration": {"type": "AWS_PROXY", "uri": "someuri"}},
                    "delete": {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}},
                },
                "/path2": {"post": {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}}},
            }
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock()
        parser._get_integration_function_name.return_value = function_name

        expected = {
            Route(
                path="/path1",
                methods=["get"],
                function_name=function_name,
                stack_path=self.stack_path,
            ),
            Route(
                path="/path1",
                methods=["delete"],
                function_name=function_name,
                stack_path=self.stack_path,
            ),
            Route(
                path="/path2",
                methods=["post"],
                function_name=function_name,
                stack_path=self.stack_path,
            ),
        }
        result = parser.get_routes()

        self.assertEqual(expected, set(result))

    def test_with_any_method(self):
        function_name = "myfunction"
        swagger = {
            "paths": {
                "/path1": {
                    "x-amazon-apigateway-any-method": {
                        "x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}
                    }
                }
            }
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock()
        parser._get_integration_function_name.return_value = function_name

        expected = [
            Route(
                methods=["ANY"],
                path="/path1",
                function_name=function_name,
                stack_path=self.stack_path,
            )
        ]
        result = parser.get_routes()

        self.assertEqual(expected, result)

    def test_does_not_have_function_name(self):
        swagger = {
            "paths": {"/path1": {"post": {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}}}}
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock()
        parser._get_integration_function_name.return_value = None  # Function Name could not be resolved

        expected = []
        result = parser.get_routes()

        self.assertEqual(expected, result)

    def test_payload_format_version(self):
        function_name = "myfunction"
        swagger = {
            "paths": {
                "/path1": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "someuri",
                            "payloadFormatVersion": "1.0",
                        }
                    }
                },
                "/path2": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "someuri",
                            "payloadFormatVersion": "2.0",
                        }
                    }
                },
            }
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock()
        parser._get_integration_function_name.return_value = function_name

        expected = [
            Route(
                path="/path1",
                methods=["get"],
                function_name=function_name,
                payload_format_version="1.0",
                stack_path=self.stack_path,
            ),
            Route(
                path="/path2",
                methods=["get"],
                function_name=function_name,
                payload_format_version="2.0",
                stack_path=self.stack_path,
            ),
        ]
        result = parser.get_routes()

        self.assertEqual(expected, result)

    @parameterized.expand(
        [
            param("empty swagger", {}),
            param("'paths' property is absent", {"foo": "bar"}),
            param("no paths", {"paths": {}}),
            param("no methods", {"paths": {"/path1": {}}}),
            param("no integration", {"paths": {"/path1": {"get": {}}}}),
        ]
    )
    def test_invalid_swagger(self, test_case_name, swagger):
        parser = SwaggerParser(self.stack_path, swagger)
        result = parser.get_routes()

        expected = []
        self.assertEqual(expected, result)

    def test_set_no_authorizer(self):
        function_name = "function"
        payload_version = "1.0"

        swagger = {
            "paths": {
                "/path1": {
                    "get": {
                        "security": [],
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "someuri",
                            "payloadFormatVersion": payload_version,
                        },
                    }
                }
            }
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock(return_value=function_name)
        parser._get_payload_format_version = Mock(return_value=payload_version)

        results = parser.get_routes()
        expected_result = [
            Route(
                path="/path1",
                methods=["get"],
                function_name=function_name,
                payload_format_version=payload_version,
                stack_path=self.stack_path,
                authorizer_name=None,
                authorizer_object=None,
                use_default_authorizer=False,
            ),
        ]

        self.assertEqual(results, expected_result)

    def test_set_defined_authorizer(self):
        function_name = "function"
        payload_version = "1.0"
        authorizer_name = "auth"

        swagger = {
            "paths": {
                "/path1": {
                    "get": {
                        "security": [{authorizer_name: []}],
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "someuri",
                            "payloadFormatVersion": payload_version,
                        },
                    }
                }
            }
        }

        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock(return_value=function_name)
        parser._get_payload_format_version = Mock(return_value=payload_version)

        results = parser.get_routes()
        expected_result = [
            Route(
                path="/path1",
                methods=["get"],
                function_name=function_name,
                payload_format_version=payload_version,
                stack_path=self.stack_path,
                authorizer_name=authorizer_name,
            ),
        ]

        self.assertEqual(results, expected_result)

    @parameterized.expand(
        [
            (
                {
                    "paths": {
                        "/path1": {
                            "get": {
                                "security": {},
                                "x-amazon-apigateway-integration": {
                                    "type": "aws_proxy",
                                    "uri": "someuri",
                                    "payloadFormatVersion": "1.0",
                                },
                            }
                        }
                    }
                },
                InvalidSecurityDefinition,
            ),
            (
                {
                    "paths": {
                        "/path1": {
                            "get": {
                                "security": [{"auth1": []}, {"auth2": []}],
                                "x-amazon-apigateway-integration": {
                                    "type": "aws_proxy",
                                    "uri": "someuri",
                                    "payloadFormatVersion": "1.0",
                                },
                            }
                        }
                    }
                },
                MultipleAuthorizerException,
            ),
        ]
    )
    def test_invalid_authorizer_definition(self, swagger, expected_exception):
        parser = SwaggerParser(self.stack_path, swagger)
        parser._get_integration_function_name = Mock(return_value="function")
        parser._get_payload_format_version = Mock(return_value="1.0")

        with self.assertRaises(expected_exception):
            parser.get_routes()


class TestSwaggerParser_get_integration_function_name(TestCase):
    def setUp(self) -> None:
        self.stack_path = Mock()

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_valid_integration(self, LambdaUriMock):
        function_name = "name"
        LambdaUriMock.get_function_name.return_value = function_name

        method_config = {"x-amazon-apigateway-integration": {"type": "aws_proxy", "uri": "someuri"}}

        parser = SwaggerParser(self.stack_path, {})
        result = parser._get_integration_function_name(method_config)

        self.assertEqual(function_name, result)
        LambdaUriMock.get_function_name.assert_called_with("someuri")

    @parameterized.expand(
        [
            param("config is not dict", "myconfig"),
            param("integration key is not in config", {"key": "value"}),
            param("integration value is empty", {"x-amazon-apigateway-integration": {}}),
            param("integration value is not dict", {"x-amazon-apigateway-integration": "someval"}),
            param("integration type is not aws_proxy", {"x-amazon-apigateway-integration": {"type": "mock"}}),
            param("integration uri is not present", {"x-amazon-apigateway-integration": {"type": "aws_proxy"}}),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_invalid_integration(self, test_case_name, method_config, LambdaUriMock):
        LambdaUriMock.get_function_name.return_value = None

        parser = SwaggerParser(self.stack_path, {})
        result = parser._get_integration_function_name(method_config)

        self.assertIsNone(result, "must not parse invalid integration")


class TestSwaggerParser_get_binary_media_types(TestCase):
    def setUp(self) -> None:
        self.stack_path = Mock()

    @parameterized.expand(
        [
            param("Swagger was none", None, []),
            param("Swagger is has no binary media types defined", {}, []),
            param(
                "Swagger define binary media types",
                {"x-amazon-apigateway-binary-media-types": ["image/gif", "application/json"]},
                ["image/gif", "application/json"],
            ),
        ]
    )
    def test_binary_media_type_returned(self, test_case_name, swagger, expected_result):
        parser = SwaggerParser(self.stack_path, swagger)

        self.assertEqual(parser.get_binary_media_types(), expected_result)


class TestSwaggerParser_get_authorizers(TestCase):
    @parameterized.expand(
        [
            (  # swagger 2.0 with token + request authorizers
                {
                    "swagger": "2.0",
                    "securityDefinitions": {
                        "TokenAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "token",
                                "authorizerUri": "arn",
                            },
                        },
                        "QueryAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "request",
                                "identitySource": "method.request.querystring.Auth",
                                "authorizerUri": "arn",
                            },
                        },
                    },
                },
                {
                    "TokenAuth": LambdaAuthorizer(
                        payload_version="1.0",
                        authorizer_name="TokenAuth",
                        type="token",
                        lambda_name="arn",
                        identity_sources=["method.request.header.Auth"],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                    "QueryAuth": LambdaAuthorizer(
                        payload_version="1.0",
                        authorizer_name="QueryAuth",
                        type="request",
                        lambda_name="arn",
                        identity_sources=["method.request.querystring.Auth"],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                },
                Route.API,
            ),
            (  # swagger 2.0 request authorizer using empty id source
                {
                    "swagger": "2.0",
                    "securityDefinitions": {
                        "QueryAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "request",
                                "authorizerUri": "arn",
                            },
                        },
                    },
                },
                {
                    "QueryAuth": LambdaAuthorizer(
                        payload_version="1.0",
                        authorizer_name="QueryAuth",
                        type="request",
                        lambda_name="arn",
                        identity_sources=[],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                },
                Route.API,
            ),
            (  # openapi 3.0 with token authorizer
                {
                    "openapi": "3.0",
                    "components": {
                        "securitySchemes": {
                            "TokenAuth": {
                                "type": "apiKey",
                                "in": "header",
                                "name": "Auth",
                                "x-amazon-apigateway-authtype": "custom",
                                "x-amazon-apigateway-authorizer": {
                                    "authorizerPayloadFormatVersion": "2.0",
                                    "type": "request",
                                    "identitySource": "$request.header.Auth",
                                    "authorizerUri": "arn",
                                },
                            },
                        },
                    },
                },
                {
                    "TokenAuth": LambdaAuthorizer(
                        payload_version="2.0",
                        authorizer_name="TokenAuth",
                        type="request",
                        lambda_name="arn",
                        identity_sources=["$request.header.Auth"],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                },
                Route.HTTP,
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_with_valid_lambda_auth_definition(self, swagger_doc, expected_authorizers, api_type, mock_lambda_uri):
        mock_lambda_uri.get_function_name.return_value = "arn"

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(event_type=api_type), expected_authorizers)

    @parameterized.expand(
        [
            (  # test unsupported type (jwt)
                {
                    "openapi": "3.0",
                    "components": {
                        "securitySchemes": {
                            "TokenAuth": {
                                "type": "apiKey",
                                "in": "header",
                                "name": "Auth",
                                "x-amazon-apigateway-authtype": "custom",
                                "x-amazon-apigateway-authorizer": {
                                    "type": "jwt",
                                    "identitySource": "method.request.header.Auth",
                                    "authorizerUri": "arn",
                                },
                            },
                        },
                    },
                },
            ),
            (  # test invalid integration key
                {
                    "openapi": "3.0",
                    "components": {
                        "securitySchemes": {
                            "TokenAuth": {
                                "type": "apiKey",
                                "in": "header",
                                "name": "Auth",
                                "x-amazon-apigateway-authtype": "custom",
                                "invalid-key-goes-here": {
                                    "type": "request",
                                    "identitySource": "$request.header.Auth",
                                    "authorizerUri": "arn",
                                },
                            },
                        },
                    },
                },
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_unsupported_lambda_authorizers(self, swagger_doc, get_id_sources_mock, mock_lambda_uri):
        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(), {})

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_invalid_lambda_auth_arn(self, get_id_sources_mock, mock_lambda_uri):
        mock_lambda_uri.get_function_name.return_value = None

        swagger_doc = {
            "swagger": "2.0",
            "securityDefinitions": {
                "TokenAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Auth",
                    "x-amazon-apigateway-authtype": "custom",
                    "x-amazon-apigateway-authorizer": {
                        "type": "token",
                        "authorizerUri": "arn",
                    },
                }
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(), {})

    @parameterized.expand(
        [
            (
                {
                    "swagger": "4.0",
                    "securityDefinitions": {
                        "TokenAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "token",
                                "authorizerUri": "arn",
                            },
                        }
                    },
                },
            ),
            (
                {
                    "openapi": "1.0",
                    "securityDefinitions": {
                        "TokenAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "token",
                                "authorizerUri": "arn",
                            },
                        }
                    },
                },
            ),
            (
                {
                    "securityDefinitions": {
                        "TokenAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "token",
                                "authorizerUri": "arn",
                            },
                        }
                    }
                },
            ),
        ]
    )
    def test_invalid_oas_version(self, swagger_doc):
        parser = SwaggerParser(Mock(), swagger_doc)

        with self.assertRaises(InvalidOasVersion):
            parser.get_authorizers()

    @parameterized.expand(
        [
            (  # API event with a defined validation string (123), expect lambda auth obj property populated
                {
                    "swagger": "2.0",
                    "securityDefinitions": {
                        "TokenAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Auth",
                            "x-amazon-apigateway-authtype": "custom",
                            "x-amazon-apigateway-authorizer": {
                                "type": "token",
                                "identityValidationExpression": "123",
                                "authorizerUri": "arn",
                            },
                        },
                    },
                },
                "123",
                Route.API,
            ),
            (  # HTTP event with a defined validation string (123), expect lambda auth obj property NOT populated
                {
                    "openapi": "3.0",
                    "components": {
                        "securitySchemes": {
                            "TokenAuth": {
                                "type": "apiKey",
                                "in": "header",
                                "name": "unused",
                                "x-amazon-apigateway-authtype": "custom",
                                "x-amazon-apigateway-authorizer": {
                                    "authorizerPayloadFormatVersion": "2.0",
                                    "type": "request",
                                    "identityValidationExpression": "123",
                                    "authorizerUri": "arn",
                                    "identitySource": "$request.header.header",
                                },
                            },
                        }
                    },
                },
                None,
                Route.HTTP,
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_defining_validation_expression(
        self, swagger_doc, expected_validation_string, event_type, get_id_sources_mock, mock_lambda_uri
    ):
        mock_lambda_uri.get_function_name.return_value = "arn"

        parser = SwaggerParser(Mock(), swagger_doc)

        lambda_authorizers = parser.get_authorizers(event_type)

        self.assertEqual(lambda_authorizers["TokenAuth"].validation_string, expected_validation_string)

    @parameterized.expand(
        [
            ##
            # testing API events
            #
            (  # using 2.0 payload and no simple response, expect it to be set as False
                "2.0",
                False,
                Route.API,
                False,
            ),
            (  # using 1.0 payload and no simple response, expect it to be set as False
                "1.0",
                False,
                Route.API,
                False,
            ),
            (  # using 1.0 payload and simple response IS set, expect it to be set as False
                "1.0",
                True,
                Route.API,
                False,
            ),
            (  # using 2.0 payload and simple response IS set, expect it to be set as False
                "2.0",
                True,
                Route.API,
                False,
            ),
            ##
            # testing HTTP events
            #
            (  # using 2.0 payload and no simple response, expect it to be set as False
                "2.0",
                False,
                Route.HTTP,
                False,
            ),
            (  # using 1.0 payload and no simple response, expect it to be set as False
                "1.0",
                False,
                Route.HTTP,
                False,
            ),
            (  # using 1.0 payload and simple response IS set, expect it to be set as False
                "1.0",
                True,
                Route.HTTP,
                False,
            ),
            (  # using 2.0 payload and simple response IS set, expect it to be set as True
                "2.0",
                True,
                Route.HTTP,
                True,
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_defining_simple_responses(
        self,
        payload_version,
        enabled_simple_response,
        event_type,
        expected_response,
        get_id_sources_mock,
        mock_lambda_uri,
    ):
        mock_lambda_uri.get_function_name.return_value = "arn"

        swagger_doc = {
            "openapi": "3.0",
            "components": {
                "securitySchemes": {
                    "Authorizer": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "notused",
                        "x-amazon-apigateway-authorizer": {
                            "authorizerPayloadFormatVersion": payload_version,
                            "enableSimpleResponses": enabled_simple_response,
                            "type": "request",
                            "authorizerUri": "arn",
                            "identitySource": "$request.header.header",
                        },
                    },
                },
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        lambda_authorizers = parser.get_authorizers(event_type)

        self.assertEqual(lambda_authorizers["Authorizer"].use_simple_response, expected_response)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_defining_invalid_payload_versions(self, get_id_sources_mock, mock_lambda_uri):
        mock_lambda_uri.get_function_name.return_value = "arn"

        swagger_doc = {
            "openapi": "3.0",
            "components": {
                "securitySchemes": {
                    "TokenAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Auth",
                        "x-amazon-apigateway-authtype": "custom",
                        "x-amazon-apigateway-authorizer": {
                            "authorizerPayloadFormatVersion": "1.2.3",
                            "type": "request",
                            "authorizerUri": "arn",
                            "identitySource": "$request.header.header",
                        },
                    },
                },
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        with self.assertRaisesRegex(
            InvalidSecurityDefinition, "^Authorizer 'TokenAuth' contains an invalid payload version$"
        ):
            parser.get_authorizers(Route.HTTP)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_undefined_payload_api_event(self, get_id_sources_mock, mock_lambda_uri):
        """
        Tests if the payload version is set to 1.0 if it is not defined for API events
        """
        mock_lambda_uri.get_function_name.return_value = "arn"

        swagger_doc = {
            "swagger": "2.0",
            "securityDefinitions": {
                "TokenAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Auth",
                    "x-amazon-apigateway-authtype": "custom",
                    "x-amazon-apigateway-authorizer": {
                        "type": "token",
                        "authorizerUri": "arn",
                    },
                },
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(Route.API)["TokenAuth"].payload_version, LambdaAuthorizer.PAYLOAD_V1)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_simple_response_override_using_rest_api(self, get_id_sources_mock, mock_lambda_uri):
        """
        Tests the the Lambda authorizer's simple response property is set to False
        if it is provided in a Swagger 2.0 document.
        """
        mock_lambda_uri.get_function_name.return_value = "arn"

        swagger_doc = {
            "swagger": "2.0",
            "securityDefinitions": {
                "TokenAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Auth",
                    "x-amazon-apigateway-authtype": "custom",
                    "x-amazon-apigateway-authorizer": {
                        "type": "token",
                        "authorizerUri": "arn",
                        "enableSimpleResponses": True,
                    },
                },
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(Route.API)["TokenAuth"].use_simple_response, False)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    @patch("samcli.commands.local.lib.swagger.parser.SwaggerParser._get_lambda_identity_sources")
    def test_ignore_token_auth_with_empty_id_sources(self, get_id_sources_mock, mock_lambda_uri):
        """
        Test if we skip a token authorizer if identity source gathering method returns empty
        """
        mock_lambda_uri.get_function_name.return_value = "arn"
        get_id_sources_mock.return_value = []

        # sample token auth
        swagger_doc = {
            "swagger": "2.0",
            "securityDefinitions": {
                "TokenAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Auth",
                    "x-amazon-apigateway-authtype": "custom",
                    "x-amazon-apigateway-authorizer": {"type": "token", "authorizerUri": "arn"},
                },
            },
        }

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(len(parser.get_authorizers(Route.API)), 0)


class TestSwaggerParser_get_default_authorizer(TestCase):
    def test_valid_default_authorizers(self):
        authorizer_name = "authorizer"

        swagger_doc = {"openapi": "3.0", "security": [{authorizer_name: []}]}

        parser = SwaggerParser(Mock(), swagger_doc)
        result = parser.get_default_authorizer(Route.HTTP)

        self.assertEqual(result, authorizer_name)

    @parameterized.expand(
        [
            ({"openapi": "3.0", "security": []},),
            ({"swagger": "2.0", "security": []},),
            ({"openapi": "3.0"},),
            ({"swagger": "2.0"},),
        ]
    )
    def test_no_default_authorizer_defined(self, swagger):
        parser = SwaggerParser(Mock(), swagger)

        result = parser.get_default_authorizer(Route.HTTP)
        self.assertIsNone(result)

        result = parser.get_default_authorizer(Route.API)
        self.assertIsNone(result)

    @parameterized.expand(
        [
            ({"swagger": "2.0", "security": [{"auth": []}]}, IncorrectOasWithDefaultAuthorizerException, Route.API),
            ({"swagger": "2.0", "security": [{"auth": []}]}, IncorrectOasWithDefaultAuthorizerException, Route.HTTP),
            ({"openapi": "3.0", "security": [{"auth": []}, {"auth2": []}]}, MultipleAuthorizerException, Route.API),
            ({"openapi": "3.0", "security": [{"auth": []}, {"auth2": []}]}, MultipleAuthorizerException, Route.HTTP),
        ]
    )
    def test_invalid_default_authorizer_definition(self, swagger, expected_exception, type):
        parser = SwaggerParser(Mock(), swagger)

        with self.assertRaises(expected_exception):
            parser.get_default_authorizer(type)

    def test_default_authorizer_definition_using_3_x_version(self):
        parser = SwaggerParser(Mock(), {"swagger": "3.0", "security": [{"auth": []}]})

        parser.get_default_authorizer(Route.API)
        parser.get_default_authorizer(Route.HTTP)


class TestSwaggerParser_get_lambda_identity_sources(TestCase):
    @parameterized.expand(
        [
            (
                "token",
                Route.API,
                {"name": "Authentication", "in": "header"},
                {},
                ["method.request.header.Authentication"],
            ),
            (
                "request",
                Route.API,
                {"name": "unused", "in": "header"},
                {"identitySource": "method.request.header.Authentication, method.request.header.otherheader"},
                ["method.request.header.Authentication", "method.request.header.otherheader"],
            ),
            ("request", Route.HTTP, {"name": "unused", "in": "header"}, {}, []),  # missing 'identitySource' for request
        ]
    )
    def test_valid_identity_sources(self, type, event_type, properties, authorizer_object, expected_result):
        parser = SwaggerParser(Mock(), Mock())

        result = parser._get_lambda_identity_sources("myauth", type, event_type, properties, authorizer_object)
        self.assertEqual(result, expected_result)

    @parameterized.expand(
        [
            (  # missing 'in' property
                "token",
                Route.API,
                {"name": "Authentication"},
                {},
            ),
            (  # missing 'name' property
                "token",
                Route.API,
                {"in": "header"},
                {},
            ),
            (  # token type for HTTP API
                "token",
                Route.HTTP,
                {"name": "auth", "in": "header"},
                {"identitySource": "method.request.header.Authentication, method.request.header.otherheader"},
            ),
        ]
    )
    def test_invalid_authorizer_definitions(self, type, event_type, properties, authorizer_object):
        parser = SwaggerParser(Mock(), Mock())

        result = parser._get_lambda_identity_sources("myauth", type, event_type, properties, authorizer_object)
        self.assertEqual(result, [])

    def test_invalid_identity_source_throws_exception(self):
        parser = SwaggerParser(Mock(), Mock())

        properties = {"name": "Authentication", "in": "header"}
        auth_properties = {"identitySource": "invalid string goes here"}

        with self.assertRaises(InvalidSecurityDefinition):
            parser._get_lambda_identity_sources(Mock(), "request", Route.API, properties, auth_properties)
