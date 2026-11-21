"""Unit tests for OpenAPI generation exceptions"""

from unittest import TestCase

from samcli.commands.exceptions import UserException
from samcli.commands.generate.openapi.exceptions import (
    GenerateOpenApiException,
    ApiResourceNotFoundException,
    InvalidApiResourceException,
    OpenApiExtractionException,
    TemplateTransformationException,
    NoApiResourcesFoundException,
    MultipleApiResourcesException,
)


class TestGenerateOpenApiException(TestCase):
    """Test base GenerateOpenApiException"""

    def test_is_user_exception(self):
        """Test that GenerateOpenApiException inherits from UserException"""
        exception = GenerateOpenApiException("Test error")
        self.assertIsInstance(exception, UserException)

    def test_exception_message(self):
        """Test exception with custom message"""
        message = "Test error message"
        exception = GenerateOpenApiException(message)
        self.assertEqual(str(exception), message)


class TestApiResourceNotFoundException(TestCase):
    """Test ApiResourceNotFoundException"""

    def test_exception_with_api_id_only(self):
        """Test exception with only API ID"""
        api_id = "MyApi"
        exception = ApiResourceNotFoundException(api_id)

        self.assertEqual(exception.api_id, api_id)
        self.assertIn("MyApi", str(exception))
        self.assertIn("not found", str(exception))

    def test_exception_with_api_id_and_message(self):
        """Test exception with API ID and custom message"""
        api_id = "MyApi"
        message = "Check your template configuration"
        exception = ApiResourceNotFoundException(api_id, message)

        self.assertEqual(exception.api_id, api_id)
        self.assertIn("MyApi", str(exception))
        self.assertIn("Check your template configuration", str(exception))

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = ApiResourceNotFoundException("MyApi")
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestInvalidApiResourceException(TestCase):
    """Test InvalidApiResourceException"""

    def test_exception_with_api_id_only(self):
        """Test exception with only API ID"""
        api_id = "MyApi"
        exception = InvalidApiResourceException(api_id)

        self.assertEqual(exception.api_id, api_id)
        self.assertIn("MyApi", str(exception))
        self.assertIn("not valid", str(exception))

    def test_exception_with_api_id_and_message(self):
        """Test exception with API ID and custom message"""
        api_id = "MyApi"
        message = "Missing required properties"
        exception = InvalidApiResourceException(api_id, message)

        self.assertEqual(exception.api_id, api_id)
        self.assertIn("MyApi", str(exception))
        self.assertIn("Missing required properties", str(exception))

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = InvalidApiResourceException("MyApi")
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestOpenApiExtractionException(TestCase):
    """Test OpenApiExtractionException"""

    def test_exception_with_message(self):
        """Test exception with message"""
        message = "Could not extract OpenAPI from template"
        exception = OpenApiExtractionException(message)

        self.assertIn("Failed to extract OpenAPI definition", str(exception))
        self.assertIn("Could not extract OpenAPI from template", str(exception))

    def test_exception_without_message(self):
        """Test exception without message"""
        exception = OpenApiExtractionException()

        self.assertIn("Failed to extract OpenAPI definition", str(exception))

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = OpenApiExtractionException("test")
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestTemplateTransformationException(TestCase):
    """Test TemplateTransformationException"""

    def test_exception_with_message(self):
        """Test exception with message"""
        message = "Invalid SAM template structure"
        exception = TemplateTransformationException(message)

        self.assertIn("Failed to transform SAM template", str(exception))
        self.assertIn("Invalid SAM template structure", str(exception))

    def test_exception_without_message(self):
        """Test exception without message"""
        exception = TemplateTransformationException()

        self.assertIn("Failed to transform SAM template", str(exception))

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = TemplateTransformationException("test")
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestNoApiResourcesFoundException(TestCase):
    """Test NoApiResourcesFoundException"""

    def test_exception_with_default_message(self):
        """Test exception with default message"""
        exception = NoApiResourcesFoundException()

        self.assertIn("No API resources found", str(exception))
        self.assertIn("AWS::Serverless::Api", str(exception))
        self.assertIn("AWS::Serverless::HttpApi", str(exception))

    def test_exception_with_custom_message(self):
        """Test exception with custom message"""
        message = "Template is empty"
        exception = NoApiResourcesFoundException(message)

        self.assertIn("No API resources found", str(exception))
        self.assertIn("Template is empty", str(exception))

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = NoApiResourcesFoundException()
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestMultipleApiResourcesException(TestCase):
    """Test MultipleApiResourcesException"""

    def test_exception_with_single_api(self):
        """Test exception with single API in list"""
        api_ids = ["MyApi"]
        exception = MultipleApiResourcesException(api_ids)

        self.assertEqual(exception.api_ids, api_ids)
        self.assertIn("Multiple API resources found", str(exception))
        self.assertIn("MyApi", str(exception))
        self.assertIn("--api-logical-id", str(exception))

    def test_exception_with_multiple_apis(self):
        """Test exception with multiple APIs"""
        api_ids = ["Api1", "Api2", "Api3"]
        exception = MultipleApiResourcesException(api_ids)

        self.assertEqual(exception.api_ids, api_ids)
        self.assertIn("Multiple API resources found", str(exception))
        self.assertIn("Api1", str(exception))
        self.assertIn("Api2", str(exception))
        self.assertIn("Api3", str(exception))
        self.assertIn("--api-logical-id", str(exception))

    def test_exception_message_format(self):
        """Test exception message formatting with commas"""
        api_ids = ["FirstApi", "SecondApi"]
        exception = MultipleApiResourcesException(api_ids)

        message = str(exception)
        # Should have comma-separated API IDs
        self.assertIn("FirstApi, SecondApi", message)

    def test_exception_is_generate_openapi_exception(self):
        """Test that it inherits from GenerateOpenApiException"""
        exception = MultipleApiResourcesException(["Api1"])
        self.assertIsInstance(exception, GenerateOpenApiException)


class TestExceptionInheritance(TestCase):
    """Test exception inheritance hierarchy"""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from GenerateOpenApiException"""
        exceptions_to_test = [
            ApiResourceNotFoundException("test"),
            InvalidApiResourceException("test"),
            OpenApiExtractionException("test"),
            TemplateTransformationException("test"),
            NoApiResourcesFoundException("test"),
            MultipleApiResourcesException(["test"]),
        ]

        for exception in exceptions_to_test:
            with self.subTest(exception=type(exception).__name__):
                self.assertIsInstance(exception, GenerateOpenApiException)
                self.assertIsInstance(exception, UserException)
