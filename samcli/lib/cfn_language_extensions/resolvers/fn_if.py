"""
Fn::If intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::If intrinsic
function, which returns one of two values based on a condition.

Fn::If format: {"Fn::If": [condition_name, value_if_true, value_if_false]}
"""

from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver

# Special AWS::NoValue reference that indicates a property should be removed
AWS_NO_VALUE = "AWS::NoValue"


class FnIfResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::If intrinsic function.

    Fn::If returns one of two values based on a condition. The format is:
    {"Fn::If": [condition_name, value_if_true, value_if_false]}

    The resolver:
    - Looks up the condition by name in resolved_conditions or evaluates it
    - Returns value_if_true if the condition is true
    - Returns value_if_false if the condition is false
    - Handles AWS::NoValue special case (returns None to indicate removal)
    - Raises InvalidTemplateException for non-existent conditions

    Attributes:
        FUNCTION_NAMES: List containing "Fn::If"

    Raises:
        InvalidTemplateException: If the layout is incorrect or the condition
                                  doesn't exist.
    """

    FUNCTION_NAMES = ["Fn::If"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the Fn::If intrinsic function.

        This method extracts the condition name and two value branches from
        the Fn::If function, evaluates the condition, and returns the
        appropriate branch value.

        Args:
            value: A dictionary representing the Fn::If intrinsic function.
                   E.g., {"Fn::If": ["IsProduction", "prod", "dev"]}

        Returns:
            The value_if_true if condition is true, value_if_false otherwise.
            Returns None if the selected branch is a Ref to AWS::NoValue.

        Raises:
            InvalidTemplateException: If the layout is incorrect (not a list
                                      of exactly 3 elements) or if the
                                      condition doesn't exist.
                                      Error message: "Fn::If layout is incorrect"
                                      or "Condition '{name}' not found"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate the layout: must be a list with exactly 3 elements
        # [condition_name, value_if_true, value_if_false]
        if not isinstance(args, list) or len(args) != 3:
            raise InvalidTemplateException("Fn::If layout is incorrect")

        condition_name = args[0]
        value_if_true = args[1]
        value_if_false = args[2]

        # Validate condition name is a string
        if not isinstance(condition_name, str):
            raise InvalidTemplateException("Fn::If layout is incorrect")

        # Evaluate the condition
        condition_result = self._evaluate_condition(condition_name)

        # Select the appropriate branch based on condition result
        # IMPORTANT: Only resolve the selected branch, NOT the unselected branch
        # This is critical for templates where the unselected branch contains
        # intrinsic functions that would fail if evaluated (e.g., Fn::Select
        # with an out-of-bounds index that's only valid when the condition is true)
        if condition_result:
            selected_value = value_if_true
        else:
            selected_value = value_if_false

        # Handle AWS::NoValue special case
        # If the selected value is {"Ref": "AWS::NoValue"}, return None
        # to indicate the property should be removed
        if self._is_no_value_ref(selected_value):
            return None

        # Resolve any nested intrinsic functions in the selected value ONLY
        if self.parent is not None:
            return self.parent.resolve_value(selected_value)

        return selected_value

    def _evaluate_condition(self, condition_name: str) -> bool:
        """
        Evaluate a condition by name.

        This method looks up the condition in the resolved_conditions cache
        first. If not found, it attempts to evaluate the condition from
        the template's Conditions section.

        Args:
            condition_name: The name of the condition to evaluate.

        Returns:
            The boolean result of the condition evaluation.

        Raises:
            InvalidTemplateException: If the condition doesn't exist or
                                      circular references are detected.
        """
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
            # Resolve the condition definition using the parent resolver
            # This allows nested intrinsic functions in conditions to be resolved
            condition_def = conditions[condition_name]

            if self.parent is not None:
                resolved = self.parent.resolve_value(condition_def)
            else:
                resolved = condition_def

            # Convert to boolean
            result = self._to_boolean(resolved)

            # Cache the result
            self.context.resolved_conditions[condition_name] = result

            return result
        finally:
            # Remove from evaluating set
            self.context._evaluating_conditions.discard(condition_name)

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
        return bool(value)

    def _is_no_value_ref(self, value: Any) -> bool:
        """
        Check if a value is a Ref to AWS::NoValue.

        AWS::NoValue is a special pseudo-parameter that indicates a property
        should be removed from the template. When Fn::If returns AWS::NoValue,
        the property containing the Fn::If should be removed.

        Args:
            value: The value to check.

        Returns:
            True if the value is {"Ref": "AWS::NoValue"}, False otherwise.
        """
        if not isinstance(value, dict):
            return False

        if len(value) != 1:
            return False

        return value.get("Ref") == AWS_NO_VALUE
