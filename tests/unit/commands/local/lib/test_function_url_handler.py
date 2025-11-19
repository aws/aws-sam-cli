"""
Unit tests for FunctionUrlHandler
"""

import unittest
import json
import base64
from unittest.mock import Mock, MagicMock, patch, call
from parameterized import parameterized

from samcli.commands.local.lib.function_url_handler import (
    FunctionUrlHandler,
    FunctionUrlPayloadFormatter,
)


class TestFunctionUrlPayloadFormatter(unittest.TestCase):
    """Test the FunctionUrlPayloadFormatter class"""

    def test__format_lambda_request_get(self):
        """Test formatting GET request to Lambda v2.0 payload"""
        result = FunctionUrlPayloadFormatter._format_lambda_request(
            method="GET",
            path="/test",
            headers={"Host": "localhost", "User-Agent": "test"},
            query_params={"foo": "bar"},
            body=None,
            source_ip="127.0.0.1",
            user_agent="test-agent",
            host="localhost",
            port=3001,
        )

        self.assertEqual(result["version"], "2.0")
        self.assertEqual(result["routeKey"], "$default")
        self.assertEqual(result["rawPath"], "/test")
        self.assertEqual(result["rawQueryString"], "foo=bar")
        self.assertEqual(result["requestContext"]["http"]["method"], "GET")
        self.assertEqual(result["queryStringParameters"], {"foo": "bar"})
        self.assertIsNone(result["body"])
        self.assertFalse(result["isBase64Encoded"])

    def test__format_lambda_request_post_with_body(self):
        """Test formatting POST request with body"""
        result = FunctionUrlPayloadFormatter._format_lambda_request(
            method="POST",
            path="/test",
            headers={"Content-Type": "application/json"},
            query_params={},
            body='{"key": "value"}',
            source_ip="127.0.0.1",
            user_agent="test-agent",
            host="localhost",
            port=3001,
        )

        self.assertEqual(result["requestContext"]["http"]["method"], "POST")
        self.assertEqual(result["body"], '{"key": "value"}')
        self.assertFalse(result["isBase64Encoded"])

    def test__format_lambda_request_with_cookies(self):
        """Test formatting request with cookies"""
        headers = {"Cookie": "session=abc123; user=john"}
        result = FunctionUrlPayloadFormatter._format_lambda_request(
            method="GET",
            path="/",
            headers=headers,
            query_params={},
            body=None,
            source_ip="127.0.0.1",
            user_agent="test",
            host="localhost",
            port=3001,
        )

        self.assertEqual(result["cookies"], ["session=abc123", "user=john"])

    def test__parse_lambda_response_simple_string(self):
        """Test formatting simple string response"""
        status, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response("Hello World")

        self.assertEqual(status, 200)
        self.assertEqual(headers, {})
        self.assertEqual(body, "Hello World")

    def test__parse_lambda_response_with_status_and_headers(self):
        """Test formatting response with status code and headers"""
        lambda_response = {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": '{"created": true}',
        }

        status, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response(lambda_response)

        self.assertEqual(status, 201)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(body, '{"created": true}')

    def test__parse_lambda_response_base64_encoded(self):
        """Test formatting base64 encoded response"""
        original_body = b"binary data"
        encoded_body = base64.b64encode(original_body).decode()

        lambda_response = {"statusCode": 200, "body": encoded_body, "isBase64Encoded": True}

        status, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response(lambda_response)

        self.assertEqual(status, 200)
        self.assertEqual(body, original_body)

    def test__parse_lambda_response_multi_value_headers(self):
        """Test formatting response with multi-value headers"""
        lambda_response = {
            "statusCode": 200,
            "headers": {"Content-Type": "text/plain"},
            "multiValueHeaders": {"Set-Cookie": ["cookie1=value1", "cookie2=value2"]},
            "body": "test",
        }

        status, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response(lambda_response)

        self.assertEqual(status, 200)
        self.assertEqual(headers["Set-Cookie"], "cookie1=value1, cookie2=value2")

    def test__parse_lambda_response_with_cookies(self):
        """Test formatting response with cookies"""
        lambda_response = {"statusCode": 200, "cookies": ["session=xyz789", "theme=dark"], "body": "test"}

        status, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response(lambda_response)

        self.assertEqual(status, 200)
        self.assertEqual(headers["Set-Cookie"], "session=xyz789; theme=dark")


class TestFunctionUrlHandler(unittest.TestCase):
    """Test the FunctionUrlHandler class"""

    def setUp(self):
        """Set up test fixtures"""
        self.function_name = "TestFunction"
        self.function_config = {
            "auth_type": "NONE",
            "cors": {
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST"],
                "AllowHeaders": ["Content-Type"],
                "MaxAge": 86400,
            },
        }
        self.local_lambda_runner = Mock()
        self.port = 3001
        self.host = "127.0.0.1"
        self.disable_authorizer = False
        self.stderr = Mock()
        self.is_debugging = False

    def test_init_creates_flask_app(self):
        """Test that FunctionUrlHandler initializes correctly (Flask created in create())"""
        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Verify service properties (Flask app created via create() method)
        self.assertEqual(service.function_name, self.function_name)
        self.assertEqual(service.local_lambda_runner, self.local_lambda_runner)
        self.assertEqual(service.port, self.port)
        self.assertEqual(service.host, self.host)
        self.assertIsNone(service._app)  # Not created until create() is called

    def test_create_flask_app(self):
        """Test that create() method initializes Flask app correctly"""
        with patch("flask.Flask") as flask_mock:
            app_mock = Mock()
            flask_mock.return_value = app_mock

            service = FunctionUrlHandler(
                function_name=self.function_name,
                function_config=self.function_config,
                local_lambda_runner=self.local_lambda_runner,
                port=self.port,
                host=self.host,
                disable_authorizer=self.disable_authorizer,
                stderr=self.stderr,
                is_debugging=self.is_debugging,
            )

            # Call create method (Flask imported inside)
            result = service.create()

            # Verify Flask was created with the function_url_handler module name
            flask_mock.assert_called_once_with('samcli.commands.local.lib.function_url_handler')
            self.assertEqual(service._app, app_mock)
            self.assertEqual(result, app_mock)
            self.assertEqual(app_mock.route.call_count, 2)  # Two route decorators

    def test_stop_service(self):
        """Test stopping the service"""
        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Stop should not raise any exceptions
        service.stop()

    def test_configure_routes(self):
        """Test that routes are configured correctly"""
        with patch("flask.Flask") as flask_mock:
            app_mock = Mock()
            flask_mock.return_value = app_mock

            service = FunctionUrlHandler(
                function_name=self.function_name,
                function_config=self.function_config,
                local_lambda_runner=self.local_lambda_runner,
                port=self.port,
                host=self.host,
                disable_authorizer=self.disable_authorizer,
                stderr=self.stderr,
                is_debugging=self.is_debugging,
            )

            # Create the app to trigger route configuration
            service.create()

            # Verify routes were registered
            self.assertEqual(app_mock.route.call_count, 2)  # Two route decorators

            # Check the route paths
            first_call = app_mock.route.call_args_list[0]
            second_call = app_mock.route.call_args_list[1]

            self.assertEqual(first_call[0][0], "/")
            self.assertEqual(first_call[1]["defaults"], {"path": ""})
            self.assertIn("GET", first_call[1]["methods"])
            self.assertIn("POST", first_call[1]["methods"])

            self.assertEqual(second_call[0][0], "/<path:path>")
            self.assertIn("GET", second_call[1]["methods"])
            self.assertIn("POST", second_call[1]["methods"])

    def test_handle_cors_preflight(self):
        """Test CORS preflight handling"""
        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        response = service._handle_cors_preflight()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertIn("Access-Control-Allow-Methods", response.headers)
        self.assertIn("Access-Control-Allow-Headers", response.headers)
        self.assertIn("Access-Control-Max-Age", response.headers)

    def test_get_cors_headers(self):
        """Test getting CORS headers from configuration"""
        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        headers = service._get_cors_headers()

        self.assertIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_get_cors_headers_with_credentials(self):
        """Test getting CORS headers with credentials enabled"""
        self.function_config["cors"]["AllowCredentials"] = True
        self.function_config["cors"]["ExposeHeaders"] = ["X-Custom-Header"]

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        headers = service._get_cors_headers()

        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(headers["Access-Control-Expose-Headers"], "X-Custom-Header")

    def test_get_cors_headers_no_config(self):
        """Test getting CORS headers when no config exists"""
        self.function_config["cors"] = None

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        headers = service._get_cors_headers()

        self.assertEqual(headers, {})

    def test_validate_iam_auth_with_valid_header(self):
        """Test IAM auth validation with valid header"""
        self.function_config["auth_type"] = "AWS_IAM"

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Create a mock request with valid auth header
        mock_request = Mock()
        mock_request.headers = {"Authorization": "AWS4-HMAC-SHA256 Credential=..."}

        result = service._validate_iam_auth(mock_request)

        self.assertTrue(result)

    def test_validate_iam_auth_with_invalid_header(self):
        """Test IAM auth validation with invalid header"""
        self.function_config["auth_type"] = "AWS_IAM"

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Create a mock request with invalid auth header
        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer token123"}

        result = service._validate_iam_auth(mock_request)

        self.assertFalse(result)

    def test_validate_iam_auth_with_no_header(self):
        """Test IAM auth validation with no header"""
        self.function_config["auth_type"] = "AWS_IAM"

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Create a mock request with no auth header
        mock_request = Mock()
        mock_request.headers = {}

        result = service._validate_iam_auth(mock_request)

        self.assertFalse(result)

    def test_validate_iam_auth_with_disable_flag(self):
        """Test IAM auth validation when disabled"""
        self.function_config["auth_type"] = "AWS_IAM"
        self.disable_authorizer = True

        service = FunctionUrlHandler(
            function_name=self.function_name,
            function_config=self.function_config,
            local_lambda_runner=self.local_lambda_runner,
            port=self.port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.stderr,
            is_debugging=self.is_debugging,
        )

        # Create a mock request with no auth header
        mock_request = Mock()
        mock_request.headers = {}

        result = service._validate_iam_auth(mock_request)

        # Should return True when authorizer is disabled
        self.assertTrue(result)

    @parameterized.expand(
        [
            ("GET",),
            ("POST",),
            ("PUT",),
            ("DELETE",),
            ("PATCH",),
            ("HEAD",),
            ("OPTIONS",),
        ]
    )
    def test_http_methods_support(self, method):
        """Test that all HTTP methods are supported"""
        with patch("flask.Flask") as flask_mock:
            app_mock = Mock()
            flask_mock.return_value = app_mock

            service = FunctionUrlHandler(
                function_name=self.function_name,
                function_config=self.function_config,
                local_lambda_runner=self.local_lambda_runner,
                port=self.port,
                host=self.host,
                disable_authorizer=self.disable_authorizer,
                stderr=self.stderr,
                is_debugging=self.is_debugging,
            )

            # Create app to configure routes
            service.create()

            # Check that the method is in the allowed methods for both routes
            for call in app_mock.route.call_args_list:
                if "methods" in call[1]:
                    self.assertIn(method, call[1]["methods"])


if __name__ == "__main__":
    unittest.main()
