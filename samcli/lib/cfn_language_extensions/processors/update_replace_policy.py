"""
UpdateReplacePolicy processor for CloudFormation Language Extensions.

This module provides the UpdateReplacePolicyProcessor which validates and resolves
UpdateReplacePolicy attributes on CloudFormation resources.
"""

from samcli.lib.cfn_language_extensions.processors.resource_policy import ResourcePolicyProcessor


class UpdateReplacePolicyProcessor(ResourcePolicyProcessor):
    """
    Validates and resolves UpdateReplacePolicy attributes on resources.

    Valid UpdateReplacePolicy values are: "Delete", "Retain", "Snapshot"
    """

    POLICY_NAME = "UpdateReplacePolicy"
