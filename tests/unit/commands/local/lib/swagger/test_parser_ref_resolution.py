"""
Tests for $ref resolution in SwaggerParser

These tests cover JSON Reference ($ref) resolution in OpenAPI documents,
which is different from CloudFormation intrinsics (Ref, Fn::Sub, etc.).
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized, param

from samcli.commands.local.lib.swagger.parser import SwaggerParser, _MAX_REF_RESOLUTION_DEPTH
from samcli.local.apigw.route import Route


class TestSwaggerParser_resolve_ref(TestCase):
    """Tests for the _resolve_ref method"""

    def setUp(self):
        self.stack_path = Mock()

    def test_resolve_ref_unsupported_format(self):
        """Test that unsupported $ref format returns None with debug log"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        # Just a plain string that doesn't match any known format
        result = parser._resolve_ref("JustAPlainString")
        self.assertIsNone(result)

    def test_resolve_ref_non_string(self):
        """Test that non-string $ref value returns None"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref(123)  # Not a string
        self.assertIsNone(result)

        result = parser._resolve_ref({"key": "value"})  # Dict instead of string
        self.assertIsNone(result)

    def test_resolve_simple_ref(self):
        """Test resolving a simple local $ref"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "x-amazon-apigateway-integrations": {
                    "lambda": {
                        "type": "aws_proxy",
                        "uri": "arn:aws:lambda:us-east-1:123456789:function:MyFunc",
                    }
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref("#/components/x-amazon-apigateway-integrations/lambda")

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "aws_proxy")
        self.assertIn("uri", result)

    def test_resolve_ref_not_found(self):
        """Test that None is returned when ref path doesn't exist"""
        swagger = {"openapi": "3.0", "components": {}}
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref("#/components/nonexistent/path")

        self.assertIsNone(result)

    def test_resolve_ref_empty_value(self):
        """Test that None is returned for empty $ref value"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref("")
        self.assertIsNone(result)

        result = parser._resolve_ref(None)
        self.assertIsNone(result)

    def test_resolve_external_url_ref_not_supported(self):
        """Test that external URL $ref returns None with warning"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            result = parser._resolve_ref("https://example.com/schemas/pet.yaml#/Pet")

        self.assertIsNone(result)
        self.assertTrue(any("External URL $ref" in msg for msg in log.output))

    def test_resolve_external_file_ref_not_supported(self):
        """Test that external file $ref returns None with warning"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            result = parser._resolve_ref("./schemas/pet.yaml#/Pet")

        self.assertIsNone(result)
        self.assertTrue(any("External file $ref" in msg for msg in log.output))

    def test_resolve_nested_ref(self):
        """Test resolving a $ref that points to another $ref"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "x-amazon-apigateway-integrations": {
                    "lambdaAlias": {"$ref": "#/components/x-amazon-apigateway-integrations/lambda"},
                    "lambda": {
                        "type": "aws_proxy",
                        "uri": "arn:aws:lambda:us-east-1:123456789:function:MyFunc",
                    },
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref("#/components/x-amazon-apigateway-integrations/lambdaAlias")

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "aws_proxy")

    def test_resolve_circular_ref_detected(self):
        """Test that circular $ref is detected and returns None"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/A"},
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            result = parser._resolve_ref("#/components/schemas/A")

        self.assertIsNone(result)
        self.assertTrue(any("Circular $ref detected" in msg for msg in log.output))

    def test_resolve_ref_depth_limit(self):
        """Test that deeply nested $ref triggers depth limit"""
        # Create a chain of refs deeper than _MAX_REF_RESOLUTION_DEPTH
        components = {}
        for i in range(_MAX_REF_RESOLUTION_DEPTH + 2):
            if i == 0:
                components[f"ref{i}"] = {"type": "final"}
            else:
                components[f"ref{i}"] = {"$ref": f"#/components/refs/ref{i-1}"}

        swagger = {"openapi": "3.0", "components": {"refs": components}}
        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            result = parser._resolve_ref(f"#/components/refs/ref{_MAX_REF_RESOLUTION_DEPTH + 1}")

        # Should return None due to depth limit
        self.assertIsNone(result)
        self.assertTrue(any("Maximum $ref resolution depth" in msg for msg in log.output))

    def test_resolve_ref_with_json_pointer_escaping(self):
        """Test that JSON Pointer escaping (~0 for ~, ~1 for /) is handled"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "x-amazon/apigateway": {
                    "integrations~lambda": {
                        "type": "aws_proxy",
                        "uri": "some-uri",
                    }
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        # ~1 decodes to /, ~0 decodes to ~
        result = parser._resolve_ref("#/components/x-amazon~1apigateway/integrations~0lambda")

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "aws_proxy")

    def test_resolve_ref_non_dict_result(self):
        """Test that $ref pointing to non-dict returns None"""
        swagger = {
            "openapi": "3.0",
            "info": {"title": "My API"},
        }
        parser = SwaggerParser(self.stack_path, swagger)

        result = parser._resolve_ref("#/info/title")

        self.assertIsNone(result)


class TestSwaggerParser_resolve_object_refs(TestCase):
    """Tests for the _resolve_object_refs method"""

    def setUp(self):
        self.stack_path = Mock()

    def test_resolve_object_refs_simple(self):
        """Test resolving $ref within nested object"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "schemas": {
                    "Pet": {"type": "object", "properties": {"name": {"type": "string"}}},
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        obj = {"pet": {"$ref": "#/components/schemas/Pet"}}
        result = parser._resolve_object_refs(obj)

        self.assertEqual(result["pet"]["type"], "object")

    def test_resolve_object_refs_with_list(self):
        """Test resolving $ref within a list"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "schemas": {
                    "Item": {"type": "object", "properties": {"name": {"type": "string"}}},
                }
            },
        }
        parser = SwaggerParser(self.stack_path, swagger)

        obj = {"items": [{"$ref": "#/components/schemas/Item"}]}
        result = parser._resolve_object_refs(obj)

        # Item is a dict, so it should be resolved
        self.assertEqual(result["items"][0]["type"], "object")

    def test_resolve_object_refs_depth_limit(self):
        """Test that depth limit is respected in _resolve_object_refs"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        obj = {"key": "value"}
        # Call with depth at max
        result = parser._resolve_object_refs(obj, depth=_MAX_REF_RESOLUTION_DEPTH)

        # Should return obj as-is due to depth limit
        self.assertEqual(result, obj)

    def test_resolve_object_refs_unresolvable_ref(self):
        """Test that unresolvable $ref is kept as-is"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        obj = {"pet": {"$ref": "#/components/nonexistent"}}
        result = parser._resolve_object_refs(obj)

        # Should return original object since ref cannot be resolved
        self.assertEqual(result["pet"]["$ref"], "#/components/nonexistent")

    def test_resolve_object_refs_no_ref(self):
        """Test that objects without $ref are returned as-is"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        obj = {"key": "value", "nested": {"foo": "bar"}}
        result = parser._resolve_object_refs(obj)

        self.assertEqual(result, obj)

    def test_resolve_object_refs_primitive(self):
        """Test that primitive values are returned as-is"""
        swagger = {"openapi": "3.0"}
        parser = SwaggerParser(self.stack_path, swagger)

        self.assertEqual(parser._resolve_object_refs("string"), "string")
        self.assertEqual(parser._resolve_object_refs(123), 123)
        self.assertEqual(parser._resolve_object_refs(True), True)
        self.assertIsNone(parser._resolve_object_refs(None))


class TestSwaggerParser_get_routes_with_ref(TestCase):
    """Tests for get_routes with $ref in integration"""

    def setUp(self):
        self.stack_path = Mock()

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_with_ref_in_integration(self, LambdaUriMock):
        """Test get_routes when x-amazon-apigateway-integration uses $ref"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-amazon-apigateway-integrations": {
                    "lambda": {
                        "type": "aws_proxy",
                        "uri": "arn:aws:lambda:us-east-1:123456789:function:MyFunction/invocations",
                    }
                }
            },
            "paths": {
                "/hello": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/lambda"
                        }
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].path, "/hello")
        self.assertEqual(routes[0].methods, ["GET"])
        self.assertEqual(routes[0].function_name, "MyFunction")

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_with_ref_in_method_config(self, LambdaUriMock):
        """Test get_routes when entire method config uses $ref"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-methods": {
                    "getLambda": {
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "some-uri",
                        }
                    }
                }
            },
            "paths": {"/hello": {"get": {"$ref": "#/components/x-methods/getLambda"}}},
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].path, "/hello")

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_with_ref_in_path_config(self, LambdaUriMock):
        """Test get_routes when entire path config uses $ref"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-paths": {
                    "helloPath": {
                        "get": {
                            "x-amazon-apigateway-integration": {
                                "type": "aws_proxy",
                                "uri": "some-uri",
                            }
                        }
                    }
                }
            },
            "paths": {"/hello": {"$ref": "#/components/x-paths/helloPath"}},
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].path, "/hello")

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_with_invalid_ref(self, LambdaUriMock):
        """Test that invalid $ref is handled gracefully"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "paths": {
                "/hello": {"get": {"x-amazon-apigateway-integration": {"$ref": "#/components/nonexistent/integration"}}}
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        # Route should be skipped since ref can't be resolved
        self.assertEqual(len(routes), 0)

    def test_get_routes_path_config_not_dict(self):
        """Test that non-dict path config is skipped"""
        swagger = {
            "openapi": "3.0",
            "paths": {
                "/hello": "not a dict",  # Invalid path config
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 0)

    def test_get_routes_path_ref_resolves_to_non_dict(self):
        """Test that path $ref resolving to non-dict is skipped"""
        swagger = {
            "openapi": "3.0",
            "components": {"x-paths": {"invalidPath": "not a dict"}},  # Invalid - not a dict
            "paths": {
                "/hello": {"$ref": "#/components/x-paths/invalidPath"},
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 0)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_method_ref_unresolvable(self, LambdaUriMock):
        """Test that unresolvable method $ref is skipped"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "paths": {
                "/hello": {
                    "get": {"$ref": "#/components/nonexistent/method"},
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 0)

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_routes_with_multiple_methods_using_refs(self, LambdaUriMock):
        """Test multiple methods using different $refs"""
        LambdaUriMock.get_function_name.return_value = "MyFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-amazon-apigateway-integrations": {
                    "getIntegration": {
                        "type": "aws_proxy",
                        "uri": "get-uri",
                    },
                    "postIntegration": {
                        "type": "aws_proxy",
                        "uri": "post-uri",
                    },
                }
            },
            "paths": {
                "/items": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/getIntegration"
                        }
                    },
                    "post": {
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/postIntegration"
                        }
                    },
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 2)
        methods = {routes[0].methods[0], routes[1].methods[0]}
        self.assertEqual(methods, {"GET", "POST"})


class TestSwaggerParser_get_authorizers_with_ref(TestCase):
    """Tests for get_authorizers with $ref"""

    def setUp(self):
        self.stack_path = Mock()

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_authorizers_with_ref_in_security_scheme(self, LambdaUriMock):
        """Test get_authorizers when security scheme uses $ref"""
        LambdaUriMock.get_function_name.return_value = "AuthorizerFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-authorizers": {
                    "lambdaAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                        "x-amazon-apigateway-authorizer": {
                            "type": "request",
                            "authorizerPayloadFormatVersion": "2.0",
                            "authorizerUri": "arn:aws:lambda:...",
                            "identitySource": "$request.header.Authorization",
                        },
                    }
                },
                "securitySchemes": {"LambdaAuthorizer": {"$ref": "#/components/x-authorizers/lambdaAuth"}},
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        authorizers = parser.get_authorizers(Route.HTTP)

        self.assertEqual(len(authorizers), 1)
        self.assertIn("LambdaAuthorizer", authorizers)

    def test_get_authorizers_with_unresolvable_security_scheme_ref(self):
        """Test get_authorizers when security scheme $ref cannot be resolved"""
        swagger = {
            "openapi": "3.0",
            "components": {
                "securitySchemes": {
                    "BrokenAuthorizer": {"$ref": "#/components/nonexistent/auth"},
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            authorizers = parser.get_authorizers(Route.HTTP)

        self.assertEqual(len(authorizers), 0)
        self.assertTrue(any("Unable to resolve $ref" in msg for msg in log.output))

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_authorizers_with_unresolvable_authorizer_ref(self, LambdaUriMock):
        """Test get_authorizers when x-amazon-apigateway-authorizer $ref cannot be resolved"""
        LambdaUriMock.get_function_name.return_value = "AuthorizerFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "securitySchemes": {
                    "BrokenAuthorizer": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Auth",
                        "x-amazon-apigateway-authorizer": {"$ref": "#/components/nonexistent/config"},
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)

        with self.assertLogs("samcli.commands.local.lib.swagger.parser", level="WARNING") as log:
            authorizers = parser.get_authorizers(Route.HTTP)

        self.assertEqual(len(authorizers), 0)
        self.assertTrue(any("Unable to resolve $ref" in msg for msg in log.output))

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_get_authorizers_with_ref_in_authorizer_object(self, LambdaUriMock):
        """Test get_authorizers when x-amazon-apigateway-authorizer uses $ref"""
        LambdaUriMock.get_function_name.return_value = "AuthorizerFunction"

        swagger = {
            "openapi": "3.0",
            "components": {
                "x-authorizer-configs": {
                    "lambdaConfig": {
                        "type": "request",
                        "authorizerPayloadFormatVersion": "2.0",
                        "authorizerUri": "arn:aws:lambda:...",
                        "identitySource": "$request.header.Authorization",
                    }
                },
                "securitySchemes": {
                    "LambdaAuthorizer": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                        "x-amazon-apigateway-authorizer": {"$ref": "#/components/x-authorizer-configs/lambdaConfig"},
                    }
                },
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        authorizers = parser.get_authorizers(Route.HTTP)

        self.assertEqual(len(authorizers), 1)
        self.assertIn("LambdaAuthorizer", authorizers)


class TestSwaggerParser_integration_issue_6045(TestCase):
    """
    Tests specifically for GitHub Issue #6045:
    sam local start-api crashes when OpenAPI uses $ref in x-amazon-apigateway-integration

    This test class reproduces the exact scenario from the issue.
    """

    def setUp(self):
        self.stack_path = Mock()

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_issue_6045_ref_in_integration(self, LambdaUriMock):
        """
        Reproduction of Issue #6045 - the original bug

        When x-amazon-apigateway-integration contains {"$ref": "..."},
        the code tried to call .get("type").lower() which failed with
        AttributeError: 'NoneType' object has no attribute 'lower'
        """
        LambdaUriMock.get_function_name.return_value = "HelloWorldFunction"

        # This is the exact structure that caused the crash
        swagger = {
            "openapi": "3.0.1",
            "info": {"title": "Test API", "version": "1.0"},
            "components": {
                "x-amazon-apigateway-integrations": {
                    "lambda": {
                        "type": "aws_proxy",
                        "httpMethod": "POST",
                        "uri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:HelloWorldFunction/invocations",
                        "payloadFormatVersion": "2.0",
                    }
                }
            },
            "paths": {
                "/hello": {
                    "get": {
                        "operationId": "getHello",
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/lambda"
                        },
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)

        # This should not raise AttributeError anymore
        routes = parser.get_routes()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].function_name, "HelloWorldFunction")
        self.assertEqual(routes[0].path, "/hello")
        self.assertEqual(routes[0].methods, ["GET"])

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_issue_6045_integration_without_ref(self, LambdaUriMock):
        """Verify that normal (non-$ref) integrations still work"""
        LambdaUriMock.get_function_name.return_value = "HelloWorldFunction"

        swagger = {
            "openapi": "3.0.1",
            "paths": {
                "/hello": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "type": "aws_proxy",
                            "uri": "arn:aws:lambda:...",
                        }
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].function_name, "HelloWorldFunction")

    @patch("samcli.commands.local.lib.swagger.parser.LambdaUri")
    def test_issue_6045_integration_with_mock_type(self, LambdaUriMock):
        """Verify that mock integrations (non-aws_proxy) are still ignored"""
        swagger = {
            "openapi": "3.0.1",
            "components": {
                "x-amazon-apigateway-integrations": {
                    "mockIntegration": {
                        "type": "mock",
                        "responses": {"default": {"statusCode": "200"}},
                    }
                }
            },
            "paths": {
                "/mock": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/mockIntegration"
                        }
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        # Mock integration should be ignored (not aws_proxy)
        self.assertEqual(len(routes), 0)

    def test_issue_6045_integration_ref_not_found(self):
        """Test that unresolvable $ref doesn't crash but is skipped"""
        swagger = {
            "openapi": "3.0.1",
            "paths": {
                "/hello": {
                    "get": {
                        "x-amazon-apigateway-integration": {
                            "$ref": "#/components/x-amazon-apigateway-integrations/nonexistent"
                        }
                    }
                }
            },
        }

        parser = SwaggerParser(self.stack_path, swagger)
        routes = parser.get_routes()

        # Route should be skipped, not crash
        self.assertEqual(len(routes), 0)
