"""
Module for Terraform hook entry points
"""
from samcli.lib.hook.hooks import IacPrepareParams, IacPrepareOutput
from .hooks import TerraformHooks


def prepare(params: dict) -> IacPrepareOutput:
    tf_hooks = TerraformHooks()
    return tf_hooks.prepare(IacPrepareParams(**params))
