"""
Fn::Ref intrinsic function resolver.

This module provides the resolver for the CloudFormation Ref intrinsic
function, which returns the value of a parameter, pseudo-parameter, or
resource reference.

Requirements:
    - 10.1: WHEN Ref is applied to a template parameter, THEN THE Resolver SHALL
            return the parameter's value from the context
    - 9.2: WHEN a pseudo-parameter (AWS::Region, AWS::AccountId, etc.) is referenced,
           THEN THE Resolver SHALL return the value from the PseudoParameterValues
           if provided
    - 9.3: WHEN a pseudo-parameter is referenced but no value is provided, THEN THE
           Resolver SHALL preserve the reference unresolved
"""

from typing import Any, Dict, Optional

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException, UnresolvableReferenceError
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver

# Set of AWS pseudo-parameters that can be resolved
PSEUDO_PARAMETERS = {
    "AWS::AccountId",
    "AWS::NotificationARNs",
    "AWS::NoValue",
    "AWS::Partition",
    "AWS::Region",
    "AWS::StackId",
    "AWS::StackName",
    "AWS::URLSuffix",
}


class FnRefResolver(IntrinsicFunctionResolver):
    """
    Resolves Ref intrinsic function.

    Ref returns the value of a specified parameter, pseudo-parameter, or
    resource. This resolver handles:
    - Template parameters: Returns the value from context.parameter_values
    - Pseudo-parameters: Returns the value from context.pseudo_parameters
    - Resource references: Preserved in partial mode (cannot be resolved locally)

    Attributes:
        FUNCTION_NAMES: List containing "Ref"

    Example:
        >>> resolver = FnRefResolver(context, parent_resolver)
        >>> resolver.resolve({"Ref": "MyParameter"})
        # Returns the value of MyParameter from context.parameter_values
        >>> resolver.resolve({"Ref": "AWS::Region"})
        # Returns the region from context.pseudo_parameters

    Requirements:
        - 10.1: Return parameter value from context for parameter references
        - 9.2: Return pseudo-parameter value if provided
        - 9.3: Preserve pseudo-parameter reference if no value provided
    """

    FUNCTION_NAMES = ["Ref"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the Ref intrinsic function.

        This method extracts the reference target from the Ref function and
        resolves it based on the target type:
        - If it's a template parameter, returns the parameter value
        - If it's a pseudo-parameter with a provided value, returns that value
        - If it's a pseudo-parameter without a value, preserves the Ref
        - If it's a resource reference, preserves the Ref (in partial mode)

        Args:
            value: A dictionary representing the Ref intrinsic function.
                   E.g., {"Ref": "MyParameter"} or {"Ref": "AWS::Region"}

        Returns:
            The resolved value for parameters and pseudo-parameters,
            or the original Ref dict for unresolvable references.

        Raises:
            InvalidTemplateException: If the Ref target is invalid.

        Example:
            >>> resolver.resolve({"Ref": "MyParameter"})
            "parameter-value"
            >>> resolver.resolve({"Ref": "AWS::Region"})
            "us-east-1"
            >>> resolver.resolve({"Ref": "MyResource"})
            {"Ref": "MyResource"}  # Preserved in partial mode
        """
        # Extract the reference target
        ref_target = self.get_function_args(value)

        # If ref_target is an intrinsic function (dict), resolve it first
        if isinstance(ref_target, dict) and self.parent is not None:
            ref_target = self.parent.resolve_value(ref_target)

        # Validate that ref_target is a string
        if not isinstance(ref_target, str):
            raise InvalidTemplateException("Ref layout is incorrect")

        # Try to resolve as a template parameter first
        param_value = self._resolve_parameter(ref_target)
        if param_value is not None:
            return param_value

        # Try to resolve as a pseudo-parameter
        pseudo_value = self._resolve_pseudo_parameter(ref_target)
        if pseudo_value is not None:
            return pseudo_value

        # Check if it's a pseudo-parameter without a provided value
        if ref_target in PSEUDO_PARAMETERS:
            # Preserve the reference unresolved (Requirement 9.3)
            return {"Ref": ref_target}

        # If not a parameter or pseudo-parameter, it's likely a resource reference
        from samcli.lib.cfn_language_extensions.models import ResolutionMode

        if self.context.resolution_mode == ResolutionMode.FULL:
            raise UnresolvableReferenceError("Ref", ref_target)
        # In partial mode, preserve the reference
        return {"Ref": ref_target}

    def _resolve_parameter(self, ref_target: str) -> Optional[Any]:
        """
        Attempt to resolve a reference as a template parameter.

        Args:
            ref_target: The reference target string.

        Returns:
            The parameter value if found, None otherwise.

        Requirements:
            - 10.1: Return parameter value from context
        """
        # Check parameter_values in context
        if ref_target in self.context.parameter_values:
            value = self.context.parameter_values[ref_target]
            # Convert comma-separated string to list for List type parameters
            return self._convert_list_parameter(ref_target, value)

        # Check parsed_template parameters if available
        if self.context.parsed_template is not None:
            if ref_target in self.context.parsed_template.parameters:
                # Parameter exists but no value provided - check for default
                param_def = self.context.parsed_template.parameters[ref_target]
                if isinstance(param_def, dict) and "Default" in param_def:
                    value = param_def["Default"]
                    # Convert comma-separated string to list for List type parameters
                    return self._convert_list_parameter(ref_target, value)

        return None

    def _convert_list_parameter(self, param_name: str, value: Any) -> Any:
        """
        Convert a parameter value to a list if the parameter type is a List type.

        CloudFormation List parameters can have comma-separated string defaults
        that need to be converted to actual lists.

        Args:
            param_name: The parameter name.
            value: The parameter value.

        Returns:
            The value converted to a list if appropriate, otherwise unchanged.
        """
        # If already a list, return as-is
        if isinstance(value, list):
            return value

        # Check if this parameter is a List type
        if self.context.parsed_template is not None:
            if param_name in self.context.parsed_template.parameters:
                param_def = self.context.parsed_template.parameters[param_name]
                if isinstance(param_def, dict):
                    param_type = param_def.get("Type", "")
                    # List types in CloudFormation start with "List<" or are
                    # "CommaDelimitedList" or "AWS::SSM::Parameter::Value<List<...>>"
                    if param_type.startswith("List<") or param_type == "CommaDelimitedList" or "List<" in param_type:
                        # Convert comma-separated string to list
                        if isinstance(value, str):
                            return [v.strip() for v in value.split(",")]

        return value

    def _resolve_pseudo_parameter(self, ref_target: str) -> Optional[Any]:
        """
        Attempt to resolve a reference as a pseudo-parameter.

        Args:
            ref_target: The reference target string.

        Returns:
            The pseudo-parameter value if found and provided, None otherwise.

        Requirements:
            - 9.2: Return pseudo-parameter value if provided
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
            "AWS::Partition": pseudo.partition or self._derive_partition(pseudo.region),
            "AWS::URLSuffix": pseudo.url_suffix or self._derive_url_suffix(pseudo.region),
        }

        if ref_target in pseudo_map:
            value = pseudo_map[ref_target]
            if value is not None:
                return value

        return None

    def _derive_partition(self, region: str) -> str:
        """
        Derive the AWS partition from the region.

        Args:
            region: The AWS region string.

        Returns:
            The partition string (aws, aws-cn, or aws-us-gov).
        """
        if region.startswith("cn-"):
            return "aws-cn"
        elif region.startswith("us-gov-"):
            return "aws-us-gov"
        else:
            return "aws"

    def _derive_url_suffix(self, region: str) -> str:
        """
        Derive the AWS URL suffix from the region.

        Args:
            region: The AWS region string.

        Returns:
            The URL suffix string.
        """
        if region.startswith("cn-"):
            return "amazonaws.com.cn"
        else:
            return "amazonaws.com"
