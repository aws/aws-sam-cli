"""
CFN IaC helper functions
"""
from typing import Dict

from samcli.lib.iac.plugins_interfaces import Stack
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider


def get_resolved_cfn_template(
    template: Stack, parameter_overrides: Dict[str, str], global_parameter_overrides: Dict[str, str]
) -> Stack:
    return SamBaseProvider.get_resolved_template_dict(
        template,
        SamLocalStackProvider.merge_parameter_overrides(parameter_overrides, global_parameter_overrides),
        normalize_resource_metadata=False,
    )
