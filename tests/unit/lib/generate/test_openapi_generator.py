"""
Unit tests for OpenAPI Generator
"""

from unittest import TestCase
from unittest.mock import Mock, patch, mock_open
from samcli.lib.generate.openapi_generator import OpenApiGenerator
from samcli.commands.generate.openapi.exceptions import (
    NoApiResourcesFoundException,
    ApiResourceNotFoundException,
    MultipleApiResourcesException,
    OpenApiExtractionException,
    TemplateTransformationException,
)


class TestOpenApiGenerator(TestCase):
    def setUp(self):
        self.template_file = "template.yaml"
        self.generator = OpenApiGenerator(template_file=self.template_file)

    def test_init(self):
        """Test OpenApiGenerator initialization"""
        generator = OpenApiGenerator(
            template_file="test.yaml",
            api_logical_id="MyApi",
            parameter_overrides={"Key": "Value"},
            region="us-east-1",
            profile="default",
        )

        self.assertEqual(generator.template_file, "test.yaml")
        self.assertEqual(generator.api_logical_id, "MyApi")
        self.assertEqual(generator.parameter_overrides, {"Key": "Value"})
        self.assertEqual(generator.region, "us-east-1")
        self.assertEqual(generator.profile, "default")

    @patch("builtins.open", new_callable=mock_open, read_data="Resources:\n  MyApi:\n    Type: AWS::Serverless::Api")
    def test_load_template_success(self, mock_file):
        """Test successful template loading"""
        template = self.generator._load_template()

        self.assertIsInstance(template, dict)
        self.assertIn("Resources", template)

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_template_file_not_found(self, mock_file):
        """Test template loading with file not found"""
        with self.assertRaises(OpenApiExtractionException) as context:
            self.generator._load_template()

        self.assertIn("Template file not found", str(context.exception))

    def test_find_api_resources(self):
        """Test finding API resources in template"""
        template = {
            "Resources": {
                "MyApi": {"Type": "AWS::Serverless::Api", "Properties": {}},
                "MyFunction": {"Type": "AWS::Serverless::Function", "Properties": {}},
                "MyHttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {}},
            }
        }

        api_resources = self.generator._find_api_resources(template)

        self.assertEqual(len(api_resources), 2)
        self.assertIn("MyApi", api_resources)
        self.assertIn("MyHttpApi", api_resources)
        self.assertNotIn("MyFunction", api_resources)

    def test_find_api_resources_empty(self):
        """Test finding API resources when none exist"""
        template = {
            "Resources": {
                "MyFunction": {"Type": "AWS::Serverless::Function", "Properties": {}},
            }
        }

        api_resources = self.generator._find_api_resources(template)

        self.assertEqual(len(api_resources), 0)

    def test_select_api_resource_single(self):
        """Test selecting API when only one exists"""
        api_resources = {"MyApi": {"Type": "AWS::Serverless::Api", "Properties": {}}}

        logical_id, resource = self.generator._select_api_resource(api_resources)

        self.assertEqual(logical_id, "MyApi")
        self.assertEqual(resource["Type"], "AWS::Serverless::Api")

    def test_select_api_resource_specified(self):
        """Test selecting specific API by logical ID"""
        api_resources = {
            "Api1": {"Type": "AWS::Serverless::Api", "Properties": {}},
            "Api2": {"Type": "AWS::Serverless::Api", "Properties": {}},
        }

        generator = OpenApiGenerator(template_file="test.yaml", api_logical_id="Api2")
        logical_id, resource = generator._select_api_resource(api_resources)

        self.assertEqual(logical_id, "Api2")

    def test_select_api_resource_not_found(self):
        """Test selecting API that doesn't exist"""
        api_resources = {
            "Api1": {"Type": "AWS::Serverless::Api", "Properties": {}},
        }

        generator = OpenApiGenerator(template_file="test.yaml", api_logical_id="Api2")

        with self.assertRaises(ApiResourceNotFoundException):
            generator._select_api_resource(api_resources)

    def test_select_api_resource_multiple_no_id(self):
        """Test selecting API when multiple exist and none specified"""
        api_resources = {
            "Api1": {"Type": "AWS::Serverless::Api", "Properties": {}},
            "Api2": {"Type": "AWS::Serverless::Api", "Properties": {}},
        }

        with self.assertRaises(MultipleApiResourcesException):
            self.generator._select_api_resource(api_resources)

    def test_extract_existing_definition_body(self):
        """Test extracting existing OpenAPI from DefinitionBody"""
        resource = {
            "Type": "AWS::Serverless::Api",
            "Properties": {
                "DefinitionBody": {
                    "swagger": "2.0",
                    "paths": {"/hello": {"get": {}}},
                }
            },
        }

        openapi_doc = self.generator._extract_existing_definition(resource, "MyApi")

        self.assertIsNotNone(openapi_doc)
        self.assertEqual(openapi_doc["swagger"], "2.0")
        self.assertIn("paths", openapi_doc)

    def test_extract_existing_definition_none(self):
        """Test extracting OpenAPI when none defined"""
        resource = {"Type": "AWS::Serverless::Api", "Properties": {}}

        openapi_doc = self.generator._extract_existing_definition(resource, "MyApi")

        self.assertIsNone(openapi_doc)

    def test_validate_openapi_valid(self):
        """Test validating valid OpenAPI document"""
        openapi_doc = {
            "swagger": "2.0",
            "paths": {"/hello": {"get": {}}},
        }

        result = self.generator._validate_openapi(openapi_doc)

        self.assertTrue(result)

    def test_validate_openapi_missing_version(self):
        """Test validating OpenAPI without version field"""
        openapi_doc = {
            "paths": {"/hello": {"get": {}}},
        }

        result = self.generator._validate_openapi(openapi_doc)

        self.assertFalse(result)

    def test_validate_openapi_missing_paths(self):
        """Test validating OpenAPI without paths"""
        openapi_doc = {
            "swagger": "2.0",
        }

        result = self.generator._validate_openapi(openapi_doc)

        self.assertFalse(result)

    def test_validate_openapi_invalid_type(self):
        """Test validating invalid OpenAPI document type"""
        result = self.generator._validate_openapi(None)
        self.assertFalse(result)

        result = self.generator._validate_openapi([])
        self.assertFalse(result)

        result = self.generator._validate_openapi("string")
        self.assertFalse(result)

    def test_has_implicit_api_true(self):
        """Test detecting implicit API"""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Events": {"ApiEvent": {"Type": "Api", "Properties": {"Path": "/hello", "Method": "get"}}}
                    },
                }
            }
        }

        result = self.generator._has_implicit_api(template)

        self.assertTrue(result)

    def test_has_implicit_api_false(self):
        """Test detecting no implicit API"""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Events": {"S3Event": {"Type": "S3", "Properties": {"Bucket": "my-bucket"}}}},
                }
            }
        }

        result = self.generator._has_implicit_api(template)

        self.assertFalse(result)

    def test_get_api_resources_info(self):
        """Test getting API resources information"""
        template = {
            "Resources": {
                "MyApi": {"Type": "AWS::Serverless::Api", "Properties": {}},
                "MyHttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {}},
            }
        }

        with patch.object(self.generator, "_load_template", return_value=template):
            info = self.generator.get_api_resources_info()

        self.assertEqual(len(info), 2)
        self.assertEqual(info[0]["LogicalId"], "MyApi")
        self.assertEqual(info[0]["Type"], "AWS::Serverless::Api")

    def test_get_api_resources_info_error(self):
        """Test getting API resources info with error"""
        with patch.object(self.generator, "_load_template", side_effect=Exception("Error")):
            info = self.generator.get_api_resources_info()

        self.assertEqual(info, [])

    def test_find_api_resources_no_resources_key(self):
        """Test finding API resources when Resources key missing"""
        template = {}
        api_resources = self.generator._find_api_resources(template)
        self.assertEqual(len(api_resources), 0)

    def test_validate_openapi_with_openapi3(self):
        """Test validating OpenAPI 3.0 document"""
        openapi_doc = {
            "openapi": "3.0.0",
            "paths": {"/hello": {"get": {}}},
        }
        result = self.generator._validate_openapi(openapi_doc)
        self.assertTrue(result)

    def test_has_implicit_api_no_events(self):
        """Test detecting no implicit API when no events"""
        template = {"Resources": {"MyFunction": {"Type": "AWS::Serverless::Function", "Properties": {}}}}
        result = self.generator._has_implicit_api(template)
        self.assertFalse(result)

    def test_has_implicit_api_no_functions(self):
        """Test detecting no implicit API when no functions"""
        template = {"Resources": {}}
        result = self.generator._has_implicit_api(template)
        self.assertFalse(result)

    def test_extract_existing_definition_with_ref(self):
        """Test extracting when DefinitionBody has Ref"""
        resource = {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionBody": {"Ref": "SomeParameter"}}}
        openapi_doc = self.generator._extract_existing_definition(resource, "MyApi")
        # Refs are not expanded, so result should be the Ref dict
        self.assertIsNotNone(openapi_doc)

    def test_find_api_resources_multiple_types(self):
        """Test finding both RestApi and HttpApi"""
        template = {
            "Resources": {
                "RestApi": {"Type": "AWS::Serverless::Api", "Properties": {}},
                "HttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {}},
                "Table": {"Type": "AWS::DynamoDB::Table", "Properties": {}},
            }
        }
        api_resources = self.generator._find_api_resources(template)
        self.assertEqual(len(api_resources), 2)
        self.assertIn("RestApi", api_resources)
        self.assertIn("HttpApi", api_resources)
