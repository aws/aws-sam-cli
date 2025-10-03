"""
Tests for samcli.lib.utils.name_utils module
"""

import pytest

from samcli.lib.utils.name_utils import normalize_lambda_function_name, InvalidFunctionNameException


class TestNormalizeLambdaFunctionName:
    """Test cases for normalize_lambda_function_name function"""

    def test_returns_function_name_unchanged_when_not_arn(self):
        """Test that regular function names are returned unchanged"""
        function_name = "my-function"
        result = normalize_lambda_function_name(function_name)
        assert result == function_name

    def test_extracts_function_name_from_basic_lambda_arn(self):
        """Test extracting function name from basic Lambda ARN"""
        arn = "arn:aws:lambda:us-east-1:123456789012:function:my-function"
        result = normalize_lambda_function_name(arn)
        assert result == "my-function"

    def test_extracts_function_name_from_versioned_lambda_arn(self):
        """Test extracting function name from versioned Lambda ARN"""
        arn = "arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST"
        result = normalize_lambda_function_name(arn)
        assert result == "my-function"

    def test_extracts_function_name_from_numbered_version_lambda_arn(self):
        """Test extracting function name from numbered version Lambda ARN"""
        arn = "arn:aws:lambda:us-east-1:123456789012:function:my-function:1"
        result = normalize_lambda_function_name(arn)
        assert result == "my-function"

    def test_extracts_function_name_from_different_partition(self):
        """Test extracting function name from Lambda ARN in different partition"""
        arn = "arn:aws-cn:lambda:cn-north-1:123456789012:function:my-function"
        result = normalize_lambda_function_name(arn)
        assert result == "my-function"

    def test_extracts_function_name_from_partial_arn(self):
        """Test extracting function name from partial ARN format"""
        partial_arn = "123456789012:function:my-function"
        result = normalize_lambda_function_name(partial_arn)
        assert result == "my-function"

    def test_extracts_function_name_from_partial_arn_with_version(self):
        """Test extracting function name from partial ARN with version"""
        partial_arn = "123456789012:function:my-function:$LATEST"
        result = normalize_lambda_function_name(partial_arn)
        assert result == "my-function"

    def test_extracts_function_name_from_partial_arn_with_numeric_version(self):
        """Test extracting function name from partial ARN with numeric version"""
        partial_arn = "123456789012:function:my-function:1"
        result = normalize_lambda_function_name(partial_arn)
        assert result == "my-function"

    def test_extracts_function_name_with_alias(self):
        """Test extracting function name from function name with alias"""
        function_with_alias = "my-function:v1"
        result = normalize_lambda_function_name(function_with_alias)
        assert result == "my-function"

    def test_extracts_function_name_with_latest_alias(self):
        """Test extracting function name from function name with $LATEST alias"""
        function_with_alias = "my-function:$LATEST"
        result = normalize_lambda_function_name(function_with_alias)
        assert result == "my-function"

    def test_raises_exception_for_non_lambda_arn(self):
        """Test that non-Lambda ARNs raise InvalidFunctionNameException"""
        arn = "arn:aws:s3:::my-bucket/my-key"
        with pytest.raises(InvalidFunctionNameException):
            normalize_lambda_function_name(arn)

    def test_returns_unchanged_for_invalid_arn(self):
        """Test that invalid ARNs are returned unchanged"""
        invalid_arn = "not-an-arn"
        result = normalize_lambda_function_name(invalid_arn)
        assert result == invalid_arn

    def test_raises_exception_for_malformed_arn(self):
        """Test that malformed ARNs raise InvalidFunctionNameException"""
        malformed_arn = "arn:aws:lambda"
        with pytest.raises(InvalidFunctionNameException):
            normalize_lambda_function_name(malformed_arn)

    def test_returns_unchanged_for_invalid_partial_arn(self):
        """Test that invalid partial ARNs are returned unchanged"""
        invalid_partial = "123456789012:invalid:my-function"
        result = normalize_lambda_function_name(invalid_partial)
        assert result == invalid_partial

    def test_handles_function_name_with_hyphens_and_underscores(self):
        """Test handling function names with special characters"""
        function_name = "my-function_name"
        result = normalize_lambda_function_name(function_name)
        assert result == function_name

    def test_extracts_function_name_with_special_characters_from_arn(self):
        """Test extracting function name with special characters from ARN"""
        arn = "arn:aws:lambda:us-east-1:123456789012:function:my-function_name-test"
        result = normalize_lambda_function_name(arn)
        assert result == "my-function_name-test"

    def test_extracts_function_name_with_special_characters_from_partial_arn(self):
        """Test extracting function name with special characters from partial ARN"""
        partial_arn = "123456789012:function:my-function_name-test"
        result = normalize_lambda_function_name(partial_arn)
        assert result == "my-function_name-test"

    def test_handles_complex_function_names(self):
        """Test handling complex function names with multiple special characters"""
        complex_names = [
            "my-function-with-many-hyphens",
            "my_function_with_underscores",
            "MyFunctionWithCamelCase",
            "function123WithNumbers",
            "function-with_mixed-chars123",
        ]

        for name in complex_names:
            # Test plain function name
            result = normalize_lambda_function_name(name)
            assert result == name

            # Test with alias
            result = normalize_lambda_function_name(f"{name}:v1")
            assert result == name

            # Test with full ARN
            arn = f"arn:aws:lambda:us-east-1:123456789012:function:{name}"
            result = normalize_lambda_function_name(arn)
            assert result == name

            # Test with partial ARN
            partial_arn = f"123456789012:function:{name}"
            result = normalize_lambda_function_name(partial_arn)
            assert result == name

    def test_raises_exception_for_invalid_function_names(self):
        """Test that invalid function names raise InvalidFunctionNameException"""
        invalid_names = [
            ":HelloWorld",  # Starts with colon
            "HelloWorld:",  # Ends with colon (empty alias)
            "",  # Empty string
            ":",  # Just colon
            "function-with-invalid-chars!",  # Invalid characters
            "123456789012:function:",  # Partial ARN with empty function name
        ]

        for invalid_name in invalid_names:
            with pytest.raises(InvalidFunctionNameException) as exc_info:
                normalize_lambda_function_name(invalid_name)

            # Check that the error message matches AWS Lambda's format
            assert "1 validation error detected" in str(exc_info.value)
            assert f"Value '{invalid_name}' at 'functionName'" in str(exc_info.value)
            assert "failed to satisfy constraint" in str(exc_info.value)
