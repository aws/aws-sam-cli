"""
Base resource policy processor for CloudFormation Language Extensions.

This module provides the ResourcePolicyProcessor base class that handles
validation and resolution of resource policy attributes (DeletionPolicy,
UpdateReplacePolicy) on CloudFormation resources.

Both DeletionPolicyProcessor and UpdateReplacePolicyProcessor inherit from
this base class, eliminating code duplication.

Requirements:
    - 7.1-7.2: Resolve parameter references in policy values
    - 7.3: Substitute parameter values for Ref in policies
    - 7.4: Raise exception for AWS::NoValue references
    - 7.5: Raise exception for non-string resolved values
"""

from typing import Any, Dict, Optional

from samcli.lib.cfn_language_extensions.exceptions import (
    InvalidTemplateException,
    PublicFacingErrorMessages,
)
from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext


class ResourcePolicyProcessor:
    """
    Base class for validating and resolving resource policy attributes.

    This processor handles DeletionPolicy and UpdateReplacePolicy attributes
    on CloudFormation resources, resolving parameter references and validating
    that the final value is a valid string. It rejects AWS::NoValue references
    as they are not supported for resource policies.

    Subclasses only need to set POLICY_NAME to the appropriate attribute name.

    Attributes:
        POLICY_NAME: The name of the policy attribute this processor handles.
        UNSUPPORTED_PSEUDO_PARAMS: Set of pseudo-parameters not supported for policies.
    """

    POLICY_NAME: str = ""
    UNSUPPORTED_PSEUDO_PARAMS = {"AWS::NoValue"}

    def process_template(self, context: TemplateProcessingContext) -> None:
        """
        Process the template by validating and resolving policy attributes.

        Iterates through all resources and processes any policy attributes found.

        Args:
            context: The mutable template processing context.

        Raises:
            InvalidTemplateException: If a policy value is invalid.
        """
        resources = context.fragment.get("Resources", {})

        if not isinstance(resources, dict):
            return

        for logical_id, resource in resources.items():
            if not isinstance(resource, dict):
                continue

            policy = resource.get(self.POLICY_NAME)
            if policy is not None:
                resolved_policy = self._resolve_and_validate_policy(logical_id, policy, context)
                resource[self.POLICY_NAME] = resolved_policy

    def _resolve_and_validate_policy(self, logical_id: str, policy: Any, context: TemplateProcessingContext) -> str:
        """
        Resolve and validate a policy value.

        Args:
            logical_id: The logical ID of the resource.
            policy: The policy value to resolve and validate.
            context: The template processing context.

        Returns:
            The resolved policy value as a string.

        Raises:
            InvalidTemplateException: If the policy is invalid.
        """
        if isinstance(policy, str):
            return policy

        if isinstance(policy, list):
            raise InvalidTemplateException(PublicFacingErrorMessages.invalid_policy_string(self.POLICY_NAME))

        if isinstance(policy, dict):
            return self._resolve_intrinsic_policy(logical_id, policy, context)

        raise InvalidTemplateException(PublicFacingErrorMessages.unresolved_policy(self.POLICY_NAME, logical_id))

    def _resolve_intrinsic_policy(
        self, logical_id: str, policy: Dict[str, Any], context: TemplateProcessingContext
    ) -> str:
        """
        Resolve an intrinsic function in a policy value.

        Args:
            logical_id: The logical ID of the resource.
            policy: The policy dict containing an intrinsic function.
            context: The template processing context.

        Returns:
            The resolved policy value as a string.

        Raises:
            InvalidTemplateException: If the policy is invalid.
        """
        if "Ref" in policy:
            ref_target = policy["Ref"]

            if ref_target in self.UNSUPPORTED_PSEUDO_PARAMS:
                raise InvalidTemplateException(PublicFacingErrorMessages.not_supported_for_policies(ref_target))

            resolved_value = self._resolve_parameter_ref(ref_target, context)

            if resolved_value is not None:
                if not isinstance(resolved_value, str):
                    raise InvalidTemplateException(
                        PublicFacingErrorMessages.unresolved_policy(self.POLICY_NAME, logical_id)
                    )
                return resolved_value

            raise InvalidTemplateException(PublicFacingErrorMessages.unresolved_policy(self.POLICY_NAME, logical_id))

        raise InvalidTemplateException(PublicFacingErrorMessages.unresolved_policy(self.POLICY_NAME, logical_id))

    def _resolve_parameter_ref(self, ref_target: str, context: TemplateProcessingContext) -> Optional[Any]:
        """
        Resolve a Ref to a parameter.

        Args:
            ref_target: The reference target string.
            context: The template processing context.

        Returns:
            The parameter value if found, None otherwise.
        """
        if ref_target in context.parameter_values:
            return context.parameter_values[ref_target]

        if context.parsed_template is not None:
            if ref_target in context.parsed_template.parameters:
                param_def = context.parsed_template.parameters[ref_target]
                if isinstance(param_def, dict) and "Default" in param_def:
                    return param_def["Default"]

        return None
