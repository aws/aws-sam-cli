"""Unit tests for OpenAPI converter"""

from unittest import TestCase
from samcli.lib.generate.openapi_converter import OpenApiConverter


class TestOpenApiConverter(TestCase):
    """Test OpenApiConverter class"""

    def test_swagger_to_openapi3_conversion(self):
        """Test converting Swagger 2.0 to OpenAPI 3.0"""
        swagger_doc = {
            "swagger": "2.0",
            "info": {"title": "Test API", "version": "1.0"},
            "paths": {"/test": {"get": {}}},
            "securityDefinitions": {
                "ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
        }
        
        result = OpenApiConverter.swagger_to_openapi3(swagger_doc)
        
        # Version changed
        self.assertEqual(result["openapi"], "3.0.0")
        self.assertNotIn("swagger", result)
        
        # SecurityDefinitions moved
        self.assertIn("components", result)
        self.assertIn("securitySchemes", result["components"])
        self.assertEqual(result["components"]["securitySchemes"]["ApiKey"]["type"], "apiKey")
        self.assertNotIn("securityDefinitions", result)

    def test_already_openapi3(self):
        """Test that OpenAPI 3.0 docs are returned unchanged"""
        openapi_doc = {
            "openapi": "3.0.0",
            "info": {"title": "Test"},
            "paths": {}
        }
        
        result = OpenApiConverter.swagger_to_openapi3(openapi_doc)
        
        self.assertEqual(result["openapi"], "3.0.0")
        self.assertEqual(result, openapi_doc)

    def test_invalid_input(self):
        """Test handling of invalid input"""
        self.assertIsNone(OpenApiConverter.swagger_to_openapi3(None))
        self.assertEqual(OpenApiConverter.swagger_to_openapi3([]), [])
        self.assertEqual(OpenApiConverter.swagger_to_openapi3("string"), "string")

    def test_no_security_definitions(self):
        """Test conversion without security definitions"""
        swagger_doc = {
            "swagger": "2.0",
            "info": {"title": "Test"},
            "paths": {}
        }
        
        result = OpenApiConverter.swagger_to_openapi3(swagger_doc)
        
        self.assertEqual(result["openapi"], "3.0.0")
        self.assertNotIn("securityDefinitions", result)
