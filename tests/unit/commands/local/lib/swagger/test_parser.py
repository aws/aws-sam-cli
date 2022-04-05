"""
Test the swagger parser
"""
from unittest import TestCase

from unittest.mock import patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.local.apigw.local_apigw_service import Route


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

        expected = [Route(path="/path1", methods=["get"], function_name=function_name, stack_path=self.stack_path)]
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
            Route(path="/path1", methods=["get"], function_name=function_name, stack_path=self.stack_path),
            Route(path="/path1", methods=["delete"], function_name=function_name, stack_path=self.stack_path),
            Route(path="/path2", methods=["post"], function_name=function_name, stack_path=self.stack_path),
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

        expected = [Route(methods=["ANY"], path="/path1", function_name=function_name, stack_path=self.stack_path)]
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
