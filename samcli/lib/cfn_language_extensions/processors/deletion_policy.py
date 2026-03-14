"""
DeletionPolicy processor for CloudFormation Language Extensions.

This module provides the DeletionPolicyProcessor which validates and resolves
DeletionPolicy attributes on CloudFormation resources.
"""

from samcli.lib.cfn_language_extensions.processors.resource_policy import ResourcePolicyProcessor


class DeletionPolicyProcessor(ResourcePolicyProcessor):
    """
    Validates and resolves DeletionPolicy attributes on resources.

    Valid DeletionPolicy values are: "Delete", "Retain", "Snapshot"
    """

    POLICY_NAME = "DeletionPolicy"
