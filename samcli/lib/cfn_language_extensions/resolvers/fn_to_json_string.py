"""
Fn::ToJsonString intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::ToJsonString intrinsic
function, which converts a dictionary or list to a JSON string representation.

Requirements:
    - 4.1: WHEN Fn::ToJsonString is applied to a dictionary, THEN THE Resolver SHALL
           return a JSON string representation of that dictionary
    - 4.2: WHEN Fn::ToJsonString is applied to a list, THEN THE Resolver SHALL
           return a JSON string representation of that list
    - 4.3: WHEN Fn::ToJsonString contains nested intrinsic functions that can be
           resolved, THEN THE Resolver SHALL resolve those intrinsics before
           converting to JSON
    - 4.4: WHEN Fn::ToJsonString contains intrinsic functions that cannot be resolved
           (e.g., Fn::GetAtt), THEN THE Resolver SHALL preserve those intrinsics
           in the JSON output
    - 4.5: WHEN Fn::ToJsonString is applied to an invalid layout, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
"""

import json
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnToJsonStringResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::ToJsonString intrinsic function.

    Fn::ToJsonString converts a dictionary or list to a JSON string representation.
    It can be applied to:
    - A literal dictionary: {"Fn::ToJsonString": {"key": "value"}} -> '{"key":"value"}'
    - A literal list: {"Fn::ToJsonString": [1, 2, 3]} -> '[1,2,3]'
    - A nested intrinsic that resolves to a dict/list

    The resolver first resolves any nested intrinsic functions where possible,
    then converts the result to a compact JSON string (no extra whitespace).

    Unresolvable intrinsic functions (like Fn::GetAtt) are preserved in the
    JSON output as their original dictionary representation.

    Attributes:
        FUNCTION_NAMES: List containing "Fn::ToJsonString"

    Example:
        >>> resolver = FnToJsonStringResolver(context, parent_resolver)
        >>> resolver.resolve({"Fn::ToJsonString": {"key": "value"}})
        '{"key":"value"}'
        >>> resolver.resolve({"Fn::ToJsonString": [1, 2, 3]})
        '[1,2,3]'
        >>> # With unresolvable intrinsic preserved
        >>> resolver.resolve({"Fn::ToJsonString": {"arn": {"Fn::GetAtt": ["Bucket", "Arn"]}}})
        '{"arn":{"Fn::GetAtt":["Bucket","Arn"]}}'

    Raises:
        InvalidTemplateException: If the input is not a dictionary or list.

    Requirements:
        - 4.1: Return JSON string representation of dictionaries
        - 4.2: Return JSON string representation of lists
        - 4.3: Resolve nested intrinsics before converting to JSON
        - 4.4: Preserve unresolvable intrinsics in JSON output
        - 4.5: Raise InvalidTemplateException for invalid layout
    """

    FUNCTION_NAMES = ["Fn::ToJsonString"]

    def resolve(self, value: Dict[str, Any]) -> str:
        """
        Resolve the Fn::ToJsonString intrinsic function.

        This method extracts the arguments from the Fn::ToJsonString function,
        resolves any nested intrinsic functions where possible (preserving
        unresolvable ones), validates that the result is a dictionary or list,
        and returns a compact JSON string representation.

        Args:
            value: A dictionary representing the Fn::ToJsonString intrinsic function.
                   E.g., {"Fn::ToJsonString": {"key": "value"}} or
                   {"Fn::ToJsonString": [1, 2, 3]}

        Returns:
            A compact JSON string representation of the resolved value.
            Uses separators=(',', ':') for minimal whitespace.

        Raises:
            InvalidTemplateException: If the resolved value is not a dictionary or list.
                                      Error message: "Fn::ToJsonString layout is incorrect"

        Example:
            >>> resolver.resolve({"Fn::ToJsonString": {"key": "value"}})
            '{"key":"value"}'
            >>> resolver.resolve({"Fn::ToJsonString": [1, 2, 3]})
            '[1,2,3]'
            >>> resolver.resolve({"Fn::ToJsonString": "not-valid"})
            InvalidTemplateException: Fn::ToJsonString layout is incorrect
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate that the input is a dictionary or list before resolution
        # This catches cases where the input is a primitive type
        if not isinstance(args, (dict, list)):
            raise InvalidTemplateException("Fn::ToJsonString layout is incorrect")

        # Check for unsupported intrinsics BEFORE resolution
        # This matches Kotlin behavior where Fn::And etc. are rejected before being resolved
        self._check_for_unsupported_intrinsics(args)

        # Resolve any nested intrinsic functions where possible
        # The parent resolver will preserve unresolvable intrinsics (like Fn::GetAtt)
        # in partial resolution mode
        if self.parent is not None:
            resolved_args = self.parent.resolve_value(args)
        else:
            # If no parent resolver, use args as-is (for testing)
            resolved_args = args

        # Check for unresolved intrinsics that return non-String values
        # These cannot be serialized to JSON properly
        self._check_for_unresolved_non_string_intrinsics(resolved_args)

        # After resolution, validate the result is still a dictionary or list
        # This handles cases where a nested intrinsic resolves to a non-dict/list
        if not isinstance(resolved_args, (dict, list)):
            raise InvalidTemplateException("Fn::ToJsonString layout is incorrect")

        # Convert to JSON string with compact separators (no extra whitespace)
        # This matches the CloudFormation behavior for Fn::ToJsonString
        return json.dumps(resolved_args, separators=(",", ":"))

    def _check_for_unsupported_intrinsics(self, value: Any) -> None:
        """
        Check for intrinsic functions that are not supported in Fn::ToJsonString.

        This check is performed BEFORE resolution to match Kotlin behavior.

        Args:
            value: The value to check.

        Raises:
            InvalidTemplateException: If an unsupported intrinsic is found.
        """
        if isinstance(value, dict):
            if len(value) == 1:
                key = next(iter(value.keys()))
                inner_value = value[key]

                # Check for AWS::NotificationARNs pseudo-parameter
                if key == "Ref" and inner_value == "AWS::NotificationARNs":
                    raise InvalidTemplateException(
                        "Fn::ToJsonString does not support AWS::NotificationARNs pseudo parameter"
                    )

                # Condition intrinsics are not supported in Fn::ToJsonString
                condition_intrinsics = {"Fn::And", "Fn::Or", "Fn::Not", "Fn::Equals"}
                if key in condition_intrinsics:
                    raise InvalidTemplateException(f"Fn::ToJsonString does not support {key} intrinsic function")
            # Recursively check nested values
            for v in value.values():
                self._check_for_unsupported_intrinsics(v)
        elif isinstance(value, list):
            for item in value:
                self._check_for_unsupported_intrinsics(item)

    def _check_for_unresolved_non_string_intrinsics(self, value: Any) -> None:
        """
        Check for unresolved intrinsic functions that return non-String values.

        Fn::ToJsonString cannot properly serialize unresolved intrinsics that
        return non-String values (like Fn::Split which returns a list).

        This check is performed AFTER resolution.

        Args:
            value: The value to check.

        Raises:
            InvalidTemplateException: If an unsupported intrinsic is found.
        """
        if isinstance(value, dict):
            if len(value) == 1:
                key = next(iter(value.keys()))
                inner_value = value[key]

                # Intrinsics that return non-String values and must be resolved
                # Note: Fn::Cidr and Fn::GetAZs are allowed because they can be
                # wrapped in Fn::Select which returns a single string
                non_string_intrinsics = {
                    "Fn::Split",  # Returns list, must be resolved
                }
                # Only reject if it looks like a valid intrinsic (has a list argument)
                if key in non_string_intrinsics and isinstance(inner_value, list):
                    raise InvalidTemplateException(f"Unable to resolve {key} intrinsic function")
            # Recursively check nested values
            for v in value.values():
                self._check_for_unresolved_non_string_intrinsics(v)
        elif isinstance(value, list):
            for item in value:
                self._check_for_unresolved_non_string_intrinsics(item)
