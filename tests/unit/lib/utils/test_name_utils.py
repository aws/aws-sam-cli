"""
Tests for samcli.lib.utils.name_utils module
"""

from unittest import TestCase

from parameterized import parameterized

from samcli.lib.utils.name_utils import normalize_lambda_function_name, InvalidFunctionNameException


class TestNormalizeLambdaFunctionName(TestCase):
    """Test cases for normalize_lambda_function_name function"""

    @parameterized.expand(
        [
            # Simple function names (pass-through)
            ("my-function", "my-function"),
            ("function-with_mixed-chars123", "function-with_mixed-chars123"),
            # Full ARNs with versions/aliases
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function", "my-function"),
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST", "my-function"),
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function:1", "my-function"),
            ("arn:aws-cn:lambda:cn-north-1:123456789012:function:my-function", "my-function"),
            # Partial ARNs
            ("123456789012:function:my-function", "my-function"),
            ("123456789012:function:my-function:$LATEST", "my-function"),
            # Function names with versions/aliases
            ("my-function:$LATEST", "my-function"),
            ("my-function:v1", "my-function"),
            # Invalid partial ARN format (should pass through)
            ("123456789012:invalid:my-function", "123456789012:invalid:my-function"),
        ]
    )
    def test_normalize_lambda_function_name(self, input_name, expected_output):
        """Test normalize_lambda_function_name with various inputs"""
        result = normalize_lambda_function_name(input_name)
        self.assertEqual(result, expected_output)

    @parameterized.expand(
        [
            ("arn:aws:s3:::my-bucket/my-key",),
            ("arn:aws:lambda",),
            (":HelloWorld",),
            ("HelloWorld:",),
            ("",),
            (":",),
            ("function-with-invalid-chars!",),
            ("123456789012:function:",),
        ]
    )
    def test_raises_exception_for_invalid_function_names(self, invalid_name):
        """Test that invalid function names raise InvalidFunctionNameException"""
        with self.assertRaises(InvalidFunctionNameException) as exc_info:
            normalize_lambda_function_name(invalid_name)

        # Check that the error message matches AWS Lambda's format
        self.assertIn("1 validation error detected", str(exc_info.exception))
        self.assertIn(f"Value '{invalid_name}' at 'functionName'", str(exc_info.exception))
        self.assertIn("failed to satisfy constraint", str(exc_info.exception))
