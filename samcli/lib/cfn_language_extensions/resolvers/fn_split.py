"""
Fn::Split intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Split intrinsic
function, which splits a string by a delimiter into a list.

Fn::Split format: {"Fn::Split": [delimiter, "string-to-split"]}
"""

from typing import Any, Dict, List, Union

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver
from samcli.lib.cfn_language_extensions.utils import is_intrinsic_key


class FnSplitResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Split intrinsic function.

    Fn::Split splits a string into a list of strings using a specified delimiter.
    The format is: {"Fn::Split": [delimiter, "string-to-split"]}

    The resolver:
    - First resolves any nested intrinsic functions in the source string
    - Splits the string by the specified delimiter
    - Returns the resulting list of strings

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Split"

    Raises:
        InvalidTemplateException: If the layout is incorrect (not a list of
                                  [delimiter, string]).
    """

    FUNCTION_NAMES = ["Fn::Split"]

    _EXPECTED_ARGS = 2

    def resolve(self, value: Dict[str, Any]) -> Union[List[str], Dict[str, Any]]:
        """
        Resolve the Fn::Split intrinsic function.

        This method extracts the delimiter and source string from the Fn::Split
        function, resolves any nested intrinsic functions, and splits the string
        by the delimiter.

        Args:
            value: A dictionary representing the Fn::Split intrinsic function.
                   E.g., {"Fn::Split": [",", "a,b,c"]}

        Returns:
            A list of strings resulting from splitting the source string.

        Raises:
            InvalidTemplateException: If the layout is incorrect.
                                      Error message: "Fn::Split layout is incorrect"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate the layout: must be a list with exactly 2 elements
        if not isinstance(args, list) or len(args) != self._EXPECTED_ARGS:
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        delimiter = args[0]
        source_string = args[1]

        # Resolve any nested intrinsic functions in the delimiter
        if self.parent is not None:
            delimiter = self.parent.resolve_value(delimiter)

        # Validate delimiter is a string
        if not isinstance(delimiter, str):
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        # Reject empty delimiter - Kotlin throws error for this
        if delimiter == "":
            raise InvalidTemplateException("Fn::Split delimiter cannot be empty")

        # Resolve any nested intrinsic functions in the source string
        if self.parent is not None:
            source_string = self.parent.resolve_value(source_string)

        # If source_string is still an unresolved intrinsic, preserve the Fn::Split
        if isinstance(source_string, dict):
            # Check if it's an intrinsic function (single key starting with Fn:: or Ref)
            if len(source_string) == 1:
                key = next(iter(source_string.keys()))
                if is_intrinsic_key(key):
                    # Return the original Fn::Split with resolved delimiter
                    return {"Fn::Split": [delimiter, source_string]}
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        # Validate the source string
        if not isinstance(source_string, str):
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        # Split the string by the delimiter
        return source_string.split(delimiter)
