"""
Fn::Sub intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::Sub intrinsic
function, which performs string substitution with ${} placeholders.

Fn::Sub supports two forms:
- Short form: {"Fn::Sub": "Hello ${Name}"} - substitutes from parameters/pseudo-parameters
- Long form: {"Fn::Sub": ["Hello ${Name}", {"Name": "World"}]} - uses variable map
"""

import re
from typing import Any, Dict, Optional, Tuple

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException, UnresolvableReferenceError
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver
from samcli.lib.cfn_language_extensions.utils import PSEUDO_PARAMETERS, derive_partition, derive_url_suffix

# Regex pattern to match ${VarName} or ${VarName.Attribute} placeholders
# Matches: ${Name}, ${AWS::Region}, ${MyResource.Arn}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")


class FnSubResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::Sub intrinsic function.

    Fn::Sub substitutes variables in a string. It supports two forms:

    Short form:
        {"Fn::Sub": "Hello ${Name}"}
        Variables are resolved from parameters and pseudo-parameters.

    Long form:
        {"Fn::Sub": ["Hello ${Name}", {"Name": "World"}]}
        Variables are first looked up in the variable map, then in
        parameters and pseudo-parameters.

    Variable syntax:
        - ${VarName} - References a parameter, pseudo-parameter, or variable map entry
        - ${Resource.Attribute} - References a resource attribute (preserved in partial mode)
        - ${!Literal} - Literal ${Literal} (escape syntax)

    Attributes:
        FUNCTION_NAMES: List containing "Fn::Sub"
    """

    FUNCTION_NAMES = ["Fn::Sub"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the Fn::Sub intrinsic function.

        This method handles both short form and long form Fn::Sub:
        - Short form: {"Fn::Sub": "string with ${placeholders}"}
        - Long form: {"Fn::Sub": ["string with ${placeholders}", {"Var": "value"}]}

        Args:
            value: A dictionary representing the Fn::Sub intrinsic function.

        Returns:
            The string with placeholders substituted. If some placeholders
            cannot be resolved (e.g., resource attributes), they are preserved
            in the output in partial mode.

        Raises:
            InvalidTemplateException: If the Fn::Sub layout is incorrect.
        """
        args = self.get_function_args(value)

        # Parse the arguments to get template string and variable map
        template_string, variable_map = self._parse_args(args)

        # Resolve any intrinsic functions in the variable map values
        resolved_variable_map = self._resolve_variable_map(variable_map)

        # Perform the substitution
        return self._substitute(template_string, resolved_variable_map)

    def _parse_args(self, args: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Parse Fn::Sub arguments into template string and variable map.

        Args:
            args: The Fn::Sub arguments (string or list).

        Returns:
            A tuple of (template_string, variable_map).

        Raises:
            InvalidTemplateException: If the arguments are invalid.
        """
        # Short form: just a string
        if isinstance(args, str):
            return args, {}

        # Long form: [string, variable_map]
        if isinstance(args, list):
            if len(args) != 2:
                raise InvalidTemplateException("Fn::Sub layout is incorrect")

            template_string = args[0]
            variable_map = args[1]

            if not isinstance(template_string, str):
                raise InvalidTemplateException("Fn::Sub layout is incorrect")

            if not isinstance(variable_map, dict):
                raise InvalidTemplateException("Fn::Sub layout is incorrect")

            return template_string, variable_map

        # Invalid type
        raise InvalidTemplateException("Fn::Sub layout is incorrect")

    def _resolve_variable_map(self, variable_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve intrinsic functions in variable map values.

        Args:
            variable_map: The variable map from Fn::Sub long form.

        Returns:
            A new dict with resolved values.

        Raises:
            InvalidTemplateException: If a variable value is null.
        """
        if not variable_map:
            return {}

        resolved = {}
        for key, val in variable_map.items():
            # Check for null values - Kotlin throws error for null substitution values
            if val is None:
                raise InvalidTemplateException(f"Fn::Sub variable '{key}' has null value")
            # Use parent resolver to resolve any intrinsic functions
            if self.parent is not None:
                resolved[key] = self.parent.resolve_value(val)
            else:
                resolved[key] = val

        return resolved

    def _substitute(self, template_string: str, variable_map: Dict[str, Any]) -> str:
        """
        Perform variable substitution in the template string.

        Args:
            template_string: The string with ${} placeholders.
            variable_map: The variable map for substitution.

        Returns:
            The string with placeholders substituted.
        """

        def replace_placeholder(match: re.Match) -> str:
            """Replace a single placeholder with its value."""
            var_name = str(match.group(1))

            # Handle escape syntax: ${!Literal} -> ${Literal}
            if var_name.startswith("!"):
                return "${" + var_name[1:] + "}"

            # Try to resolve the variable
            resolved_value = self._resolve_variable(var_name, variable_map)

            if resolved_value is not None:
                # Convert to string for substitution
                return self._value_to_string(resolved_value)

            # If not resolved, check resolution mode
            from samcli.lib.cfn_language_extensions.models import ResolutionMode

            if self.context.resolution_mode == ResolutionMode.FULL:
                raise UnresolvableReferenceError("Fn::Sub", var_name)
            # In partial mode, preserve the placeholder
            return str(match.group(0))

        result = PLACEHOLDER_PATTERN.sub(replace_placeholder, template_string)
        return str(result)

    def _resolve_variable(self, var_name: str, variable_map: Dict[str, Any]) -> Optional[Any]:
        """
        Resolve a variable name to its value.

        Resolution order:
        1. Variable map (from long form)
        2. Template parameters
        3. Pseudo-parameters

        For resource attributes (e.g., MyResource.Arn), returns None
        to preserve the placeholder in partial mode.

        Args:
            var_name: The variable name from the placeholder.
            variable_map: The variable map from Fn::Sub long form.

        Returns:
            The resolved value, or None if not resolvable.
        """
        # Check if it's a resource attribute reference (contains a dot)
        if "." in var_name:
            # This is a GetAtt-style reference (e.g., MyResource.Arn)
            # Check if it's in the variable map first
            if var_name in variable_map:
                return variable_map[var_name]
            # Otherwise, cannot resolve locally - preserve it
            return None

        # 1. Check variable map first
        if var_name in variable_map:
            return variable_map[var_name]

        # 2. Check template parameters
        param_value = self._resolve_from_parameters(var_name)
        if param_value is not None:
            return param_value

        # 3. Check pseudo-parameters
        pseudo_value = self._resolve_from_pseudo_parameters(var_name)
        if pseudo_value is not None:
            return pseudo_value

        # 4. Check if it's a known pseudo-parameter without a value
        if self._is_pseudo_parameter(var_name):
            # Preserve the placeholder
            return None

        # 5. Assume it's a resource reference - preserve it
        return None

    def _resolve_from_parameters(self, var_name: str) -> Optional[Any]:
        """
        Attempt to resolve a variable from template parameters.

        Args:
            var_name: The variable name.

        Returns:
            The parameter value if found, None otherwise.
        """
        # Check parameter_values in context
        if var_name in self.context.parameter_values:
            return self.context.parameter_values[var_name]

        # Check parsed_template parameters for default values
        if self.context.parsed_template is not None:
            if var_name in self.context.parsed_template.parameters:
                param_def = self.context.parsed_template.parameters[var_name]
                if isinstance(param_def, dict) and "Default" in param_def:
                    return param_def["Default"]

        return None

    def _resolve_from_pseudo_parameters(self, var_name: str) -> Optional[Any]:
        """
        Attempt to resolve a variable from pseudo-parameters.

        Args:
            var_name: The variable name.

        Returns:
            The pseudo-parameter value if found and provided, None otherwise.
        """
        if self.context.pseudo_parameters is None:
            return None

        pseudo = self.context.pseudo_parameters

        # Map pseudo-parameter names to their values
        pseudo_map = {
            "AWS::AccountId": pseudo.account_id,
            "AWS::Region": pseudo.region,
            "AWS::StackId": pseudo.stack_id,
            "AWS::StackName": pseudo.stack_name,
            "AWS::NotificationARNs": pseudo.notification_arns,
            "AWS::Partition": pseudo.partition or derive_partition(pseudo.region),
            "AWS::URLSuffix": pseudo.url_suffix or derive_url_suffix(pseudo.region),
        }

        if var_name in pseudo_map:
            value = pseudo_map[var_name]
            if value is not None:
                return value

        return None

    def _is_pseudo_parameter(self, var_name: str) -> bool:
        """
        Check if a variable name is a pseudo-parameter.

        Args:
            var_name: The variable name.

        Returns:
            True if it's a pseudo-parameter name.
        """
        return var_name in PSEUDO_PARAMETERS

    def _value_to_string(self, value: Any) -> str:
        """
        Convert a value to string for substitution.

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
        elif isinstance(value, list):
            # Join list elements with comma
            return ",".join(self._value_to_string(item) for item in value)
        elif isinstance(value, dict):
            # If it's an unresolved intrinsic, we can't substitute it
            # This shouldn't happen in normal flow, but handle gracefully
            return str(value)
        else:
            return str(value)
