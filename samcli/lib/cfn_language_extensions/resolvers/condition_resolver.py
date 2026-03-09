"""
Condition intrinsic function resolvers.

This module provides resolvers for CloudFormation condition intrinsic functions:
- Fn::Equals: Compares two values for equality
- Fn::And: Returns true if all conditions are true
- Fn::Or: Returns true if any condition is true
- Fn::Not: Returns the inverse of a condition
- Condition: References a named condition from the Conditions section

"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver

if TYPE_CHECKING:
    from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext
    from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicResolver


class ConditionResolver(IntrinsicFunctionResolver):
    """
    Resolves condition intrinsic functions.

    This resolver handles the CloudFormation condition functions:
    - Fn::Equals: Compares two values for equality
    - Fn::And: Returns true if all conditions are true (2-10 conditions)
    - Fn::Or: Returns true if any condition is true (2-10 conditions)
    - Fn::Not: Returns the inverse of a condition
    - Condition: References a named condition from the Conditions section

    The resolver also detects circular condition references and raises
    InvalidTemplateException when detected.

    Attributes:
        FUNCTION_NAMES: List containing condition function names
        _evaluating_conditions: Set of condition names currently being evaluated
                                (used for circular reference detection)

    """

    FUNCTION_NAMES = ["Fn::Equals", "Fn::And", "Fn::Or", "Fn::Not", "Condition"]

    def __init__(
        self, context: "TemplateProcessingContext", parent_resolver: Optional["IntrinsicResolver"] = None
    ) -> None:
        """
        Initialize the resolver with context and parent resolver.

        Args:
            context: The template processing context containing parameters,
                     mappings, conditions, and other template state.
            parent_resolver: The parent IntrinsicResolver used for resolving
                             nested intrinsic functions.
        """
        super().__init__(context, parent_resolver)

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the condition intrinsic function.

        This method dispatches to the appropriate handler based on the
        function name.

        Args:
            value: A dictionary representing the condition intrinsic function.
                   E.g., {"Fn::Equals": ["a", "a"]} or {"Condition": "MyCondition"}

        Returns:
            A boolean value representing the condition result.

        Raises:
            InvalidTemplateException: If the function layout is incorrect or
                                      circular references are detected.
        """
        fn_name = self.get_function_name(value)
        args = self.get_function_args(value)

        if fn_name == "Fn::Equals":
            return self._resolve_equals(args)
        elif fn_name == "Fn::And":
            return self._resolve_and(args)
        elif fn_name == "Fn::Or":
            return self._resolve_or(args)
        elif fn_name == "Fn::Not":
            return self._resolve_not(args)
        elif fn_name == "Condition":
            return self._resolve_condition_reference(args)
        else:
            raise InvalidTemplateException(f"{fn_name} layout is incorrect")

    def _resolve_equals(self, args: Any) -> bool:
        """
        Resolve Fn::Equals intrinsic function.

        Fn::Equals compares two values and returns true if they are equal.

        Args:
            args: A list of exactly two values to compare.

        Returns:
            True if the values are equal, False otherwise.

        Raises:
            InvalidTemplateException: If args is not a list of exactly 2 elements,
                                      or if the values are not comparable types.

        """
        if not isinstance(args, list) or len(args) != 2:
            raise InvalidTemplateException("Fn::Equals layout is incorrect")

        # Resolve nested intrinsics in both values
        value1 = self._resolve_nested(args[0])
        value2 = self._resolve_nested(args[1])

        # Validate that values are comparable types (not complex objects)
        # Kotlin throws "Intrinsic function input type is invalid" for dicts
        # that are not intrinsic functions
        if self._is_invalid_equals_value(value1) or self._is_invalid_equals_value(value2):
            raise InvalidTemplateException("Intrinsic function input type is invalid")

        # CloudFormation Fn::Equals performs string comparison.
        # Convert both values to strings to handle cases where YAML parsing
        # produces booleans (e.g., bare `true`/`false`) but parameter overrides
        # are always strings (e.g., "true"/"false").
        str1 = str(value1).lower() if isinstance(value1, bool) else str(value1)
        str2 = str(value2).lower() if isinstance(value2, bool) else str(value2)

        return str1 == str2

    def _is_invalid_equals_value(self, value: Any) -> bool:
        """
        Check if a value is invalid for Fn::Equals comparison.

        Invalid values are dicts that are not intrinsic functions.
        Unresolved intrinsic functions (like {"Ref": "AWS::StackName"}) are valid
        because they will be resolved later.

        Args:
            value: The value to check.

        Returns:
            True if the value is invalid, False otherwise.
        """
        if not isinstance(value, dict):
            return False

        # Check if it's an intrinsic function (single key starting with Fn:: or Ref or Condition)
        if len(value) == 1:
            key = next(iter(value.keys()))
            if key.startswith("Fn::") or key == "Ref" or key == "Condition":
                return False  # Valid - it's an unresolved intrinsic

        # It's a dict but not an intrinsic function - invalid
        return True

    def _resolve_and(self, args: Any) -> bool:
        """
        Resolve Fn::And intrinsic function.

        Fn::And returns true if all conditions are true. It accepts 2-10 conditions.

        Args:
            args: A list of 2-10 condition values.

        Returns:
            True if all conditions are true, False otherwise.

        Raises:
            InvalidTemplateException: If args is not a list of 2-10 elements,
                                      or if any element is not a valid condition.

        """
        if not isinstance(args, list) or len(args) < 2 or len(args) > 10:
            raise InvalidTemplateException("Fn::And layout is incorrect")

        # Evaluate all conditions
        for condition in args:
            # Validate that each element is a valid condition operation
            self._validate_condition_element(condition)
            resolved = self._resolve_nested(condition)
            # Convert to boolean
            if not self._to_boolean(resolved):
                return False

        return True

    def _resolve_or(self, args: Any) -> bool:
        """
        Resolve Fn::Or intrinsic function.

        Fn::Or returns true if any condition is true. It accepts 2-10 conditions.

        Args:
            args: A list of 2-10 condition values.

        Returns:
            True if any condition is true, False otherwise.

        Raises:
            InvalidTemplateException: If args is not a list of 2-10 elements,
                                      or if any element is not a valid condition.

        """
        if not isinstance(args, list) or len(args) < 2 or len(args) > 10:
            raise InvalidTemplateException("Fn::Or layout is incorrect")

        # Evaluate all conditions
        for condition in args:
            # Validate that each element is a valid condition operation
            self._validate_condition_element(condition)
            resolved = self._resolve_nested(condition)
            # Convert to boolean
            if self._to_boolean(resolved):
                return True

        return False

    def _resolve_not(self, args: Any) -> bool:
        """
        Resolve Fn::Not intrinsic function.

        Fn::Not returns the inverse of a condition.

        Args:
            args: A list containing exactly one condition value.

        Returns:
            The inverse of the condition value.

        Raises:
            InvalidTemplateException: If args is not a list of exactly 1 element,
                                      or if the element is not a valid condition.

        """
        if not isinstance(args, list) or len(args) != 1:
            raise InvalidTemplateException("Fn::Not layout is incorrect")

        # Validate that the element is a valid condition operation
        self._validate_condition_element(args[0])
        resolved = self._resolve_nested(args[0])
        return not self._to_boolean(resolved)

    def _validate_condition_element(self, element: Any) -> None:
        """
        Validate that an element is a valid condition operation.

        Valid condition elements are:
        - Boolean values (True/False)
        - String "true"/"false" (case-insensitive)
        - Dicts with a single key that is a condition function
          (Fn::Equals, Fn::And, Fn::Or, Fn::Not, Condition)

        Args:
            element: The element to validate.

        Raises:
            InvalidTemplateException: If the element is not a valid condition.
        """
        # Boolean values are always valid
        if isinstance(element, bool):
            return

        # String "true"/"false" are valid
        if isinstance(element, str):
            if element.lower() in ("true", "false"):
                return

        # Dicts must have a single key that is a condition function
        if isinstance(element, dict) and len(element) == 1:
            key = next(iter(element.keys()))
            # Valid condition functions
            if key in self.FUNCTION_NAMES:
                return
            # Ref is NOT valid inside condition functions like Fn::And/Fn::Or/Fn::Not
            if key == "Ref":
                raise InvalidTemplateException("Conditions can only be boolean operations")

        # Other types are invalid
        raise InvalidTemplateException("Conditions can only be boolean operations")

    def _resolve_condition_reference(self, args: Any) -> bool:
        """
        Resolve a Condition reference.

        The Condition intrinsic function references a named condition from
        the Conditions section of the template.

        Args:
            args: The name of the condition to reference (string).

        Returns:
            The boolean value of the referenced condition.

        Raises:
            InvalidTemplateException: If the condition name is invalid,
                                      the condition doesn't exist, or
                                      circular references are detected.

        """
        if not isinstance(args, str):
            raise InvalidTemplateException("Condition layout is incorrect")

        condition_name = args

        # Check for circular reference using context's tracking set
        if condition_name in self.context._evaluating_conditions:
            raise InvalidTemplateException(f"Circular condition reference detected: {condition_name}")

        # Check if condition is already resolved in context
        if condition_name in self.context.resolved_conditions:
            return self.context.resolved_conditions[condition_name]

        # Get the condition definition from parsed template
        if self.context.parsed_template is None:
            raise InvalidTemplateException(f"Condition '{condition_name}' not found")

        conditions = self.context.parsed_template.conditions
        if condition_name not in conditions:
            raise InvalidTemplateException(f"Condition '{condition_name}' not found")

        # Mark this condition as being evaluated (for circular reference detection)
        self.context._evaluating_conditions.add(condition_name)

        try:
            # Resolve the condition definition
            condition_def = conditions[condition_name]
            resolved = self._resolve_nested(condition_def)
            result = self._to_boolean(resolved)

            # Cache the result
            self.context.resolved_conditions[condition_name] = result

            return result
        finally:
            # Remove from evaluating set
            self.context._evaluating_conditions.discard(condition_name)

    def _resolve_nested(self, value: Any) -> Any:
        """
        Resolve nested intrinsic functions.

        This method uses the parent resolver to resolve any nested intrinsic
        functions in the value.

        Args:
            value: The value to resolve.

        Returns:
            The resolved value.
        """
        if self.parent is not None:
            return self.parent.resolve_value(value)
        return value

    def _to_boolean(self, value: Any) -> bool:
        """
        Convert a value to a boolean.

        CloudFormation conditions can be:
        - Boolean values (True/False)
        - String "true"/"false" (case-insensitive)

        Args:
            value: The value to convert.

        Returns:
            The boolean representation of the value.

        Raises:
            InvalidTemplateException: If the value cannot be converted to boolean.
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lower_value = value.lower()
            if lower_value == "true":
                return True
            elif lower_value == "false":
                return False

        # For other types, use Python's truthiness
        # This handles cases where nested intrinsics return non-boolean values
        return bool(value)
