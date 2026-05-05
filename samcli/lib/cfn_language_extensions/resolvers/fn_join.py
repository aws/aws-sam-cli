"""
Fn::Join intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Join intrinsic
function, which joins list elements with a delimiter.

Fn::Join format: {"Fn::Join": [delimiter, [list, of, items]]}
"""

from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnJoinResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Join intrinsic function.

    Fn::Join concatenates a list of strings with a specified delimiter.
    The format is: {"Fn::Join": [delimiter, [list, of, items]]}

    The resolver:
    - First resolves any nested intrinsic functions in the list items
    - Joins all list elements with the specified delimiter
    - Returns the resulting string

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Join"

    Raises:
        InvalidTemplateException: If the layout is incorrect (not a list of
                                  [delimiter, list] or list items are not strings).
    """

    FUNCTION_NAMES = ["Fn::Join"]

    _EXPECTED_ARGS = 2

    def resolve(self, value: Dict[str, Any]) -> str:
        """
        Resolve the Fn::Join intrinsic function.

        This method extracts the delimiter and list from the Fn::Join function,
        resolves any nested intrinsic functions in the list items, and joins
        them with the delimiter.

        Args:
            value: A dictionary representing the Fn::Join intrinsic function.
                   E.g., {"Fn::Join": [",", ["a", "b", "c"]]}

        Returns:
            A string with all list elements joined by the delimiter.

        Raises:
            InvalidTemplateException: If the layout is incorrect.
                                      Error message: "Fn::Join layout is incorrect"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate the layout: must be a list with exactly 2 elements
        if not isinstance(args, list) or len(args) != self._EXPECTED_ARGS:
            raise InvalidTemplateException("Fn::Join layout is incorrect")

        delimiter = args[0]
        list_to_join = args[1]

        # Resolve any nested intrinsic functions in the delimiter
        if self.parent is not None:
            delimiter = self.parent.resolve_value(delimiter)

        # Validate delimiter is a string
        if not isinstance(delimiter, str):
            raise InvalidTemplateException("Fn::Join layout is incorrect")

        # Resolve any nested intrinsic functions in the list
        if self.parent is not None:
            list_to_join = self.parent.resolve_value(list_to_join)

        # Validate the list
        if not isinstance(list_to_join, list):
            raise InvalidTemplateException("Fn::Join layout is incorrect")

        # Convert all items to strings and join
        string_items = []
        for item in list_to_join:
            string_items.append(self._to_string(item))

        return delimiter.join(string_items)

    def _to_string(self, value: Any) -> str:
        """
        Convert a value to string for joining.

        Args:
            value: The value to convert.

        Returns:
            The string representation.
        """
        if isinstance(value, str):
            return value
        elif isinstance(value, bool):
            # CloudFormation uses lowercase for booleans
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return ""
        elif isinstance(value, dict):
            # If it's an unresolved intrinsic, convert to string representation
            # This handles cases where intrinsics couldn't be resolved
            return str(value)
        elif isinstance(value, list):
            # Nested lists - join with comma as default
            return ",".join(self._to_string(item) for item in value)
        else:
            return str(value)
