"""
Tests for samcli.lib.utils.name_utils module
"""

from unittest import TestCase

from parameterized import parameterized

from samcli.lib.utils.name_utils import (
    normalize_lambda_function_name,
    normalize_sam_function_identifier,
    InvalidFunctionNameException,
)


class TestNormalizeSamFunctionIdentifier(TestCase):
    """Test cases for normalize_sam_function_identifier function"""

    @parameterized.expand(
        [
            # Simple function names (pass-through)
            ("my-function", "my-function"),
            ("function-with_mixed-chars123", "function-with_mixed-chars123"),
            ("my-function:v1", "my-function"),
            ("my-function:$LATEST", "my-function"),
            # Full ARNs with versions/aliases
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function", "my-function"),
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST", "my-function"),
            ("arn:aws:lambda:us-east-1:123456789012:function:my-function:1", "my-function"),
            ("arn:aws-cn:lambda:cn-north-1:123456789012:function:my-function", "my-function"),
            # Partial ARNs
            ("123456789012:function:my-function", "my-function"),
            ("123456789012:function:my-function:$LATEST", "my-function"),
            # Invalid partial ARN format (should pass through)
            ("123456789012:invalid:my-function", "123456789012:invalid:my-function"),
            # Nested stack paths with simple function names
            ("NestedStack/my-function", "NestedStack/my-function"),
            ("NestedStack/my-function:v1", "NestedStack/my-function"),
            ("LocalNestedStack/Function1", "LocalNestedStack/Function1"),
            ("LocalNestedStack/Function2", "LocalNestedStack/Function2"),
            # Deep nested stack paths
            ("Stack1/Stack2/my-function", "Stack1/Stack2/my-function"),
            ("ChildStackX/ChildStackY/FunctionA", "ChildStackX/ChildStackY/FunctionA"),
            ("Stack1/Stack2/Stack3/my-function", "Stack1/Stack2/Stack3/my-function"),
            # Nested stack paths with ARNs
            ("NestedStack/arn:aws:lambda:us-east-1:123456789012:function:my-function", "NestedStack/my-function"),
            (
                "Stack1/Stack2/arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST",
                "Stack1/Stack2/my-function",
            ),
            # Nested stack paths with partial ARNs
            ("NestedStack/123456789012:function:my-function", "NestedStack/my-function"),
        ]
    )
    def test_normalize_sam_function_identifier(self, input_name, expected_output):
        """Test normalize_sam_function_identifier with various inputs"""
        result = normalize_sam_function_identifier(input_name)
        self.assertEqual(result, expected_output)

    @parameterized.expand(
        [
            ("arn:aws:lambda",),
            (":HelloWorld",),
            ("HelloWorld:",),
            ("",),
            (":",),
            ("function-with-invalid-chars!",),
            ("123456789012:function:",),
            ("Stack1/Stack2/function-with-invalid-chars!",),
            ("NestedStack/",),
        ]
    )
    def test_raises_exception_for_invalid_function_names(self, invalid_name):
        """Test that invalid function names raise InvalidFunctionNameException"""
        with self.assertRaises(InvalidFunctionNameException) as exc_info:
            normalize_sam_function_identifier(invalid_name)

        # Check that the error message matches AWS Lambda's format
        self.assertIn("1 validation error detected", str(exc_info.exception))
        self.assertIn("failed to satisfy constraint", str(exc_info.exception))
