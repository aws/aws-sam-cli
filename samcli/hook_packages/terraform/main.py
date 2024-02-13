"""
Module for Terraform hook entry points
"""

from .hooks.prepare.hook import prepare as prepare_hook


def prepare(params: dict) -> dict:
    return prepare_hook(params)
