"""
Exception classes for CloudFormation Language Extensions processing.

This module provides exception classes that match the Kotlin implementation
for consistent error handling and messaging.
"""

from typing import Optional


class InvalidTemplateException(Exception):
    """
    Raised when template processing fails due to invalid template structure or content.

    This exception supports cause chaining to preserve the original exception
    that triggered the error.

    Attributes:
        cause: The original exception that caused this error, if any.

    Example:
        >>> try:
        ...     # Some operation that fails
        ...     raise KeyError("missing_key")
        ... except KeyError as e:
        ...     raise InvalidTemplateException("Mapping lookup failed", cause=e)
    """

    def __init__(self, message: str, cause: Optional[Exception] = None):
        """
        Initialize the exception with a message and optional cause.

        Args:
            message: The error message describing what went wrong.
            cause: The original exception that caused this error, if any.
        """
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:
        """Return string representation including cause if present."""
        if self.cause:
            return f"{self.args[0]} (caused by: {self.cause})"
        return str(self.args[0])


class UnresolvableReferenceError(Exception):
    """
    Raised when a reference cannot be resolved in the current context.

    This exception is used during partial resolution mode to signal that
    a reference (e.g., Fn::Ref to a resource, Fn::GetAtt) cannot be
    resolved locally and should be preserved in the output.

    Attributes:
        reference_type: The type of reference (e.g., "Ref", "Fn::GetAtt").
        reference_target: The target of the reference (e.g., resource logical ID).

    Example:
        >>> raise UnresolvableReferenceError("Ref", "MyBucket")
        UnresolvableReferenceError: Cannot resolve Ref to 'MyBucket'
    """

    def __init__(self, reference_type: str, reference_target: str):
        """
        Initialize the exception with reference details.

        Args:
            reference_type: The type of reference (e.g., "Ref", "Fn::GetAtt").
            reference_target: The target of the reference.
        """
        self.reference_type = reference_type
        self.reference_target = reference_target
        super().__init__(f"Cannot resolve {reference_type} to '{reference_target}'")


class PublicFacingErrorMessages:
    """
    Error messages matching the Kotlin implementation.

    This class provides standardized error messages for consistency
    with the original CloudFormation Language Extensions implementation.
    All error messages are designed to be user-friendly and actionable.
    """

    # Static error messages
    INTERNAL_FAILURE = "Internal Failure"
    INVALID_INPUT = "Invalid input passed to the AWS::LanguageExtensions Transform"
    UNRESOLVED_CONDITIONS = "Unable to resolve Conditions section"
    ERROR_PARSING_TEMPLATE = "Error parsing the template"

    @staticmethod
    def not_supported_for_policies(logical_id: str) -> str:
        """
        Generate error message for unsupported policy references.

        Args:
            logical_id: The logical ID that is not supported (e.g., "AWS::NoValue").

        Returns:
            Error message indicating the logical ID is not supported for policies.
        """
        return f"{logical_id} is not supported for DeletionPolicy or UpdateReplacePolicy"

    @staticmethod
    def unresolved_policy(attr_name: str, logical_id: str) -> str:
        """
        Generate error message for unresolved policy expressions.

        Args:
            attr_name: The policy attribute name (e.g., "DeletionPolicy").
            logical_id: The resource logical ID.

        Returns:
            Error message indicating the policy expression is unsupported.
        """
        return f"Unsupported expression for {attr_name} in resource {logical_id}"

    @staticmethod
    def resolution_error(logical_id: str) -> str:
        """
        Generate error message for resource resolution errors.

        Args:
            logical_id: The resource logical ID that failed to resolve.

        Returns:
            Error message indicating a resolution error occurred.
        """
        return f"Error resolving resource {logical_id} in template"

    @staticmethod
    def resolve_type_mismatch(fn_type: str) -> str:
        """
        Generate error message for type mismatches during resolution.

        Args:
            fn_type: The intrinsic function type (e.g., "Fn::Length").

        Returns:
            Error message indicating a type mismatch occurred.
        """
        return f"{fn_type} resolve value type mismatch"

    @staticmethod
    def invalid_policy_string(attr_name: str) -> str:
        """
        Generate error message for invalid policy string values.

        Args:
            attr_name: The policy attribute name (e.g., "DeletionPolicy").

        Returns:
            Error message indicating policy members must be strings.
        """
        return f"Every {attr_name} member must be a string"

    @staticmethod
    def layout_incorrect(fn_name: str) -> str:
        """
        Generate error message for incorrect intrinsic function layout.

        Args:
            fn_name: The intrinsic function name (e.g., "Fn::Length").

        Returns:
            Error message indicating the function layout is incorrect.
        """
        return f"{fn_name} layout is incorrect"
