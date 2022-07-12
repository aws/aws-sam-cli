"""
Module for Terraform hook entry points
"""
from .hooks import TerraformHooks


def prepare(params: dict) -> dict:
    tf_hooks = TerraformHooks()
    return tf_hooks.prepare(params)
