"""
Test the swagger parser
"""
from unittest import TestCase

from unittest.mock import patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.local.apigw.exceptions import (
    IncorrectOasWithDefaultAuthorizerException,
    InvalidOasVersion,
    InvalidSecurityDefinition,
    MultipleAuthorizerException,
)
from samcli.local.apigw.local_apigw_service import Route, LambdaAuthorizer


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
                authorizer_name="",
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
                authorizer_name="",
            ),
            Route(
                path="/path1",
                methods=["delete"],
                function_name=function_name,
                stack_path=self.stack_path,
                authorizer_name="",
            ),
            Route(
                path="/path2",
                methods=["post"],
                function_name=function_name,
                stack_path=self.stack_path,
                authorizer_name="",
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
                authorizer_name="",
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
                authorizer_name="",
            ),
            Route(
                path="/path2",
                methods=["get"],
                function_name=function_name,
                payload_format_version="2.0",
                stack_path=self.stack_path,
                authorizer_name="",
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
                                "identitySource": "method.request.header.Auth",
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
                                "identitySource": "method.request.query.Auth",
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
                        identity_sources=["method.request.query.Auth"],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                },
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
                                    "type": "token",
                                    "identitySource": "method.request.header.Auth",
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
                        type="token",
                        lambda_name="arn",
                        identity_sources=["method.request.header.Auth"],
                        validation_string=None,
                        use_simple_response=False,
                    ),
                },
            ),
        ]
    )
    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_with_valid_definition(self, swagger_doc, expected_authorizers, mock_lambda_uri):
        mock_lambda_uri.get_function_name.return_value = "arn"

        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(), expected_authorizers)

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
                                    "type": "token",
                                    "identitySource": "method.request.header.Auth",
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
    def test_unsupported_authorizers(self, swagger_doc, mock_lambda_uri):
        parser = SwaggerParser(Mock(), swagger_doc)

        self.assertEqual(parser.get_authorizers(), {})

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_invalid_arn(self, mock_lambda_uri):
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
                        "identitySource": "method.request.header.Auth",
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
                                "identitySource": "method.request.header.Auth",
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
                                "identitySource": "method.request.header.Auth",
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
                                "identitySource": "method.request.header.Auth",
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
            ({"swagger": "2.0", "security": [{"auth": []}]}, IncorrectOasWithDefaultAuthorizerException),
            ({"openapi": "3.0", "security": [{"auth": []}, {"auth2": []}]}, MultipleAuthorizerException),
        ]
    )
    def test_invalid_default_authorizer_definition(self, swagger, expected_exception):
        parser = SwaggerParser(Mock(), swagger)

        with self.assertRaises(expected_exception):
            parser.get_default_authorizer(Route.HTTP)
