"""
Fn::Length intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Length intrinsic
function, which returns the number of elements in a list.

Requirements:
    - 3.1: WHEN Fn::Length is applied to a list, THEN THE Resolver SHALL return
           the number of elements in the list
    - 3.2: WHEN Fn::Length is applied to a nested intrinsic function that resolves
           to a list, THEN THE Resolver SHALL first resolve the inner function
           and then return the length
    - 3.3: WHEN Fn::Length is applied to a non-list value, THEN THE Resolver SHALL
           raise an Invalid_Template_Exception indicating incorrect layout
    - 3.4: WHEN Fn::Length references a parameter that resolves to a CommaDelimitedList,
           THEN THE Resolver SHALL return the count of items in the list
"""

from typing import Any, Dict, Union

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnLengthResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Length intrinsic function.

    Fn::Length returns the number of elements in a list. It can be applied to:
    - A literal list: {"Fn::Length": [1, 2, 3]} -> 3
    - A nested intrinsic that resolves to a list: {"Fn::Length": {"Ref": "MyList"}}
    - A parameter that is a CommaDelimitedList

    The resolver first resolves any nested intrinsic functions, then validates
    that the result is a list, and finally returns the length.

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Length"

    Example:
        >>> resolver = FnLengthResolver(context, parent_resolver)
        >>> resolver.resolve({"Fn::Length": [1, 2, 3]})
        3
        >>> resolver.resolve({"Fn::Length": {"Ref": "MyListParam"}})
        # Returns length of the resolved parameter value

    Raises:
        InvalidTemplateException: If the resolved value is not a list.

    Requirements:
        - 3.1: Return the number of elements in a list
        - 3.2: Resolve nested intrinsics first, then return length
        - 3.3: Raise InvalidTemplateException for non-list input
        - 3.4: Handle CommaDelimitedList parameters
    """

    FUNCTION_NAMES = ["Fn::Length"]

    def resolve(self, value: Dict[str, Any]) -> Union[int, Dict[str, Any]]:
        """
        Resolve the Fn::Length intrinsic function.

        This method extracts the arguments from the Fn::Length function,
        resolves any nested intrinsic functions, validates that the result
        is a list, and returns the length.

        Args:
            value: A dictionary representing the Fn::Length intrinsic function.
                   E.g., {"Fn::Length": [1, 2, 3]} or
                   {"Fn::Length": {"Ref": "MyListParam"}}

        Returns:
            The number of elements in the resolved list.

        Raises:
            InvalidTemplateException: If the resolved value is not a list.
                                      Error message: "Fn::Length layout is incorrect"

        Example:
            >>> resolver.resolve({"Fn::Length": [1, 2, 3]})
            3
            >>> resolver.resolve({"Fn::Length": []})
            0
            >>> resolver.resolve({"Fn::Length": "not-a-list"})
            InvalidTemplateException: Fn::Length layout is incorrect
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # First resolve any nested intrinsic functions
        # This handles cases like {"Fn::Length": {"Ref": "MyListParam"}}
        # or {"Fn::Length": {"Fn::Split": [",", "a,b,c"]}}
        if self.parent is not None:
            resolved_args = self.parent.resolve_value(args)
        else:
            # If no parent resolver, use args as-is (for testing)
            resolved_args = args

        # If the resolved value is still an intrinsic function (unresolved),
        # preserve the Fn::Length for later resolution.
        # An intrinsic function is a dict with exactly one key that starts with
        # "Fn::" or is "Ref" or "Condition".
        if isinstance(resolved_args, dict):
            if len(resolved_args) == 1:
                key = next(iter(resolved_args.keys()))
                if key.startswith("Fn::") or key in ("Ref", "Condition"):
                    return {"Fn::Length": resolved_args}
            # If it's a dict but not an intrinsic function, raise error
            raise InvalidTemplateException("Fn::Length layout is incorrect")

        # Validate that the resolved value is a list
        if not isinstance(resolved_args, list):
            raise InvalidTemplateException("Fn::Length layout is incorrect")

        # Return the length of the list
        return len(resolved_args)
