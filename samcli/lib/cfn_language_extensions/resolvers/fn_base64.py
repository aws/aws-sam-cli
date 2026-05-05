"""
Fn::Base64 intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Base64 intrinsic
function, which encodes a string to base64.
"""

import base64
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnBase64Resolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Base64 intrinsic function.

    Fn::Base64 encodes a string to base64. It can be applied to:
    - A literal string: {"Fn::Base64": "hello"} -> "aGVsbG8="
    - A nested intrinsic that resolves to a string: {"Fn::Base64": {"Ref": "MyParam"}}

    The resolver first resolves any nested intrinsic functions, then validates
    that the result is a string, and finally returns the base64-encoded value.

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Base64"

    Raises:
        InvalidTemplateException: If the resolved value is not a string.
    """

    FUNCTION_NAMES = ["Fn::Base64"]

    def resolve(self, value: Dict[str, Any]) -> str:
        """
        Resolve the Fn::Base64 intrinsic function.

        This method extracts the arguments from the Fn::Base64 function,
        resolves any nested intrinsic functions, validates that the result
        is a string, and returns the base64-encoded value.

        Args:
            value: A dictionary representing the Fn::Base64 intrinsic function.
                   E.g., {"Fn::Base64": "hello"} or
                   {"Fn::Base64": {"Ref": "MyStringParam"}}

        Returns:
            The base64-encoded string.

        Raises:
            InvalidTemplateException: If the resolved value is not a string.
                                      Error message: "Fn::Base64 layout is incorrect"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # First resolve any nested intrinsic functions
        # This handles cases like {"Fn::Base64": {"Ref": "MyStringParam"}}
        # or {"Fn::Base64": {"Fn::Sub": "Hello ${Name}"}}
        if self.parent is not None:
            resolved_args = self.parent.resolve_value(args)
        else:
            # If no parent resolver, use args as-is (for testing)
            resolved_args = args

        # Validate that the resolved value is a string
        if not isinstance(resolved_args, str):
            raise InvalidTemplateException("Fn::Base64 layout is incorrect")

        # Encode the string to base64
        # CloudFormation uses UTF-8 encoding for the input string
        encoded_bytes = base64.b64encode(resolved_args.encode("utf-8"))
        return encoded_bytes.decode("utf-8")
