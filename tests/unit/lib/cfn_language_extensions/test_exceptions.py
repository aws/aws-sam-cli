"""
Unit tests for exception classes.

Tests cover:
- InvalidTemplateException with and without cause chaining
- UnresolvableReferenceError for partial resolution
- PublicFacingErrorMessages matching Kotlin implementation
"""

import pytest

from samcli.lib.cfn_language_extensions import (
    InvalidTemplateException,
    UnresolvableReferenceError,
    PublicFacingErrorMessages,
)


class TestInvalidTemplateException:
    """Tests for InvalidTemplateException class."""

    def test_basic_exception_message(self):
        """Test exception with just a message."""
        exc = InvalidTemplateException("Test error message")

        assert str(exc) == "Test error message"
        assert exc.args[0] == "Test error message"
        assert exc.cause is None

    def test_exception_with_cause(self):
        """Test exception with cause chaining (Requirement 11.4)."""
        original_error = KeyError("missing_key")
        exc = InvalidTemplateException("Mapping lookup failed", cause=original_error)

        assert exc.cause is original_error
        assert "Mapping lookup failed" in str(exc)
        assert "caused by:" in str(exc)
        assert "missing_key" in str(exc)

    def test_exception_str_without_cause(self):
        """Test __str__ returns just message when no cause."""
        exc = InvalidTemplateException("Simple error")

        assert str(exc) == "Simple error"

    def test_exception_str_with_cause(self):
        """Test __str__ includes cause information."""
        cause = ValueError("Invalid value")
        exc = InvalidTemplateException("Processing failed", cause=cause)

        result = str(exc)
        assert result == "Processing failed (caused by: Invalid value)"

    def test_exception_is_catchable_as_exception(self):
        """Test that InvalidTemplateException can be caught as Exception."""
        with pytest.raises(Exception):
            raise InvalidTemplateException("Test")

    def test_exception_preserves_cause_type(self):
        """Test that the cause exception type is preserved."""
        cause = TypeError("type error")
        exc = InvalidTemplateException("Wrapper", cause=cause)

        assert isinstance(exc.cause, TypeError)


class TestUnresolvableReferenceError:
    """Tests for UnresolvableReferenceError class."""

    def test_ref_to_resource(self):
        """Test error for Ref to a resource."""
        exc = UnresolvableReferenceError("Ref", "MyBucket")

        assert exc.reference_type == "Ref"
        assert exc.reference_target == "MyBucket"
        assert str(exc) == "Cannot resolve Ref to 'MyBucket'"

    def test_getatt_reference(self):
        """Test error for Fn::GetAtt reference."""
        exc = UnresolvableReferenceError("Fn::GetAtt", "MyBucket.Arn")

        assert exc.reference_type == "Fn::GetAtt"
        assert exc.reference_target == "MyBucket.Arn"
        assert str(exc) == "Cannot resolve Fn::GetAtt to 'MyBucket.Arn'"

    def test_import_value_reference(self):
        """Test error for Fn::ImportValue reference."""
        exc = UnresolvableReferenceError("Fn::ImportValue", "SharedVpcId")

        assert exc.reference_type == "Fn::ImportValue"
        assert exc.reference_target == "SharedVpcId"
        assert str(exc) == "Cannot resolve Fn::ImportValue to 'SharedVpcId'"

    def test_exception_is_catchable(self):
        """Test that UnresolvableReferenceError can be caught."""
        with pytest.raises(UnresolvableReferenceError) as exc_info:
            raise UnresolvableReferenceError("Ref", "TestResource")

        assert exc_info.value.reference_type == "Ref"
        assert exc_info.value.reference_target == "TestResource"


class TestPublicFacingErrorMessages:
    """Tests for PublicFacingErrorMessages class matching Kotlin implementation."""

    def test_internal_failure_constant(self):
        """Test INTERNAL_FAILURE constant."""
        assert PublicFacingErrorMessages.INTERNAL_FAILURE == "Internal Failure"

    def test_invalid_input_constant(self):
        """Test INVALID_INPUT constant."""
        assert PublicFacingErrorMessages.INVALID_INPUT == (
            "Invalid input passed to the AWS::LanguageExtensions Transform"
        )

    def test_unresolved_conditions_constant(self):
        """Test UNRESOLVED_CONDITIONS constant."""
        assert PublicFacingErrorMessages.UNRESOLVED_CONDITIONS == ("Unable to resolve Conditions section")

    def test_error_parsing_template_constant(self):
        """Test ERROR_PARSING_TEMPLATE constant (Requirement 11.5)."""
        assert PublicFacingErrorMessages.ERROR_PARSING_TEMPLATE == ("Error parsing the template")

    def test_not_supported_for_policies(self):
        """Test not_supported_for_policies message."""
        result = PublicFacingErrorMessages.not_supported_for_policies("AWS::NoValue")

        assert result == "AWS::NoValue is not supported for DeletionPolicy or UpdateReplacePolicy"

    def test_unresolved_policy(self):
        """Test unresolved_policy message."""
        result = PublicFacingErrorMessages.unresolved_policy("DeletionPolicy", "MyResource")

        assert result == "Unsupported expression for DeletionPolicy in resource MyResource"

    def test_resolution_error(self):
        """Test resolution_error message (Requirement 11.2)."""
        result = PublicFacingErrorMessages.resolution_error("MyLambdaFunction")

        assert result == "Error resolving resource MyLambdaFunction in template"

    def test_resolve_type_mismatch(self):
        """Test resolve_type_mismatch message (Requirement 11.3)."""
        result = PublicFacingErrorMessages.resolve_type_mismatch("Fn::Length")

        assert result == "Fn::Length resolve value type mismatch"

    def test_invalid_policy_string(self):
        """Test invalid_policy_string message."""
        result = PublicFacingErrorMessages.invalid_policy_string("DeletionPolicy")

        assert result == "Every DeletionPolicy member must be a string"

    def test_layout_incorrect(self):
        """Test layout_incorrect message (Requirement 11.1)."""
        result = PublicFacingErrorMessages.layout_incorrect("Fn::Length")

        assert result == "Fn::Length layout is incorrect"

    def test_layout_incorrect_various_functions(self):
        """Test layout_incorrect for various function names."""
        functions = ["Fn::ToJsonString", "Fn::FindInMap", "Fn::ForEach", "Fn::Sub"]

        for fn_name in functions:
            result = PublicFacingErrorMessages.layout_incorrect(fn_name)
            assert result == f"{fn_name} layout is incorrect"


class TestExceptionIntegration:
    """Integration tests for exception usage patterns."""

    def test_invalid_template_with_layout_error_message(self):
        """Test InvalidTemplateException with layout_incorrect message."""
        message = PublicFacingErrorMessages.layout_incorrect("Fn::Length")
        exc = InvalidTemplateException(message)

        assert str(exc) == "Fn::Length layout is incorrect"

    def test_invalid_template_with_resolution_error_message(self):
        """Test InvalidTemplateException with resolution_error message."""
        message = PublicFacingErrorMessages.resolution_error("MyResource")
        exc = InvalidTemplateException(message)

        assert str(exc) == "Error resolving resource MyResource in template"

    def test_invalid_template_with_type_mismatch_message(self):
        """Test InvalidTemplateException with resolve_type_mismatch message."""
        message = PublicFacingErrorMessages.resolve_type_mismatch("Fn::Sub")
        exc = InvalidTemplateException(message)

        assert str(exc) == "Fn::Sub resolve value type mismatch"

    def test_chained_exception_pattern(self):
        """Test typical exception chaining pattern."""
        try:
            # Simulate a lookup failure
            mappings = {"RegionMap": {"us-east-1": {"AMI": "ami-12345"}}}
            _ = mappings["RegionMap"]["us-west-2"]["AMI"]
        except KeyError as e:
            exc = InvalidTemplateException("Mapping 'RegionMap' key lookup failed", cause=e)

            assert exc.cause is not None
            assert "us-west-2" in str(exc.cause)
            assert "caused by:" in str(exc)
