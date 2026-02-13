"""
Fn::Select intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Select intrinsic
function, which selects an item from a list by index.

Fn::Select format: {"Fn::Select": [index, [list, of, items]]}

Requirements:
    - 10.5: WHEN Fn::Select is applied to a list with an index, THEN THE
            Resolver SHALL return the element at that index
    - 10.9: WHEN Fn::Select is applied with an out-of-bounds index, THEN THE
            Resolver SHALL raise an Invalid_Template_Exception
"""

from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnSelectResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Select intrinsic function.

    Fn::Select selects an item from a list by its 0-based index.
    The format is: {"Fn::Select": [index, [list, of, items]]}

    The resolver:
    - First resolves any nested intrinsic functions in the list
    - Selects the item at the specified index
    - Returns the selected item
    - Raises InvalidTemplateException for out-of-bounds index

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Select"

    Example:
        >>> resolver = FnSelectResolver(context, parent_resolver)
        >>> resolver.resolve({"Fn::Select": [0, ["a", "b", "c"]]})
        "a"
        >>> resolver.resolve({"Fn::Select": [2, ["a", "b", "c"]]})
        "c"

    Raises:
        InvalidTemplateException: If the layout is incorrect (not a list of
                                  [index, list]) or if the index is out of bounds.

    Requirements:
        - 10.5: Return the element at the specified index
        - 10.9: Raise exception for out-of-bounds index
    """

    FUNCTION_NAMES = ["Fn::Select"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the Fn::Select intrinsic function.

        This method extracts the index and list from the Fn::Select function,
        resolves any nested intrinsic functions, and returns the item at the
        specified index.

        Args:
            value: A dictionary representing the Fn::Select intrinsic function.
                   E.g., {"Fn::Select": [0, ["a", "b", "c"]]}

        Returns:
            The item at the specified index in the list.

        Raises:
            InvalidTemplateException: If the layout is incorrect or index is
                                      out of bounds.
                                      Error message: "Fn::Select layout is incorrect"
                                      or "Fn::Select index out of bounds"

        Example:
            >>> resolver.resolve({"Fn::Select": [0, ["a", "b", "c"]]})
            "a"
            >>> resolver.resolve({"Fn::Select": [1, ["x", "y"]]})
            "y"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate the layout: must be a list with exactly 2 elements
        if not isinstance(args, list) or len(args) != 2:
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        index = args[0]
        source_list = args[1]

        # Resolve any nested intrinsic functions in the index
        if self.parent is not None:
            index = self.parent.resolve_value(index)

        # Validate index is an integer (or can be converted to one)
        if isinstance(index, str):
            try:
                index = int(index)
            except ValueError:
                raise InvalidTemplateException("Fn::Select layout is incorrect")
        elif not isinstance(index, int):
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        # Resolve any nested intrinsic functions in the source list
        if self.parent is not None:
            source_list = self.parent.resolve_value(source_list)

        # If the source list is still an intrinsic function (unresolved), preserve the Fn::Select.
        # An intrinsic function is a dict with exactly one key that starts with
        # "Fn::" or is "Ref" or "Condition".
        if isinstance(source_list, dict):
            if len(source_list) == 1:
                key = next(iter(source_list.keys()))
                if key.startswith("Fn::") or key in ("Ref", "Condition"):
                    # Return the original value with resolved index if possible
                    return {"Fn::Select": [index, source_list]}
            # If it's a dict but not an intrinsic function, raise error
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        # Validate the source list
        if not isinstance(source_list, list):
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        # Check for out-of-bounds index
        # Requirement 10.9: Raise exception for out-of-bounds index
        if index < 0 or index >= len(source_list):
            raise InvalidTemplateException("Fn::Select index out of bounds")

        # Return the item at the specified index
        # Requirement 10.5: Return the element at that index
        return source_list[index]
