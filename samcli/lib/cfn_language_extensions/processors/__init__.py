"""
Template processors for CloudFormation Language Extensions.

This module provides the various processors used in the template
processing pipeline, including parsing, intrinsic function resolution,
and policy validation.
"""

from samcli.lib.cfn_language_extensions.processors.deletion_policy import DeletionPolicyProcessor
from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor
from samcli.lib.cfn_language_extensions.processors.parsing import TemplateParsingProcessor
from samcli.lib.cfn_language_extensions.processors.update_replace_policy import UpdateReplacePolicyProcessor

__all__ = [
    "TemplateParsingProcessor",
    "ForEachProcessor",
    "DeletionPolicyProcessor",
    "UpdateReplacePolicyProcessor",
]
