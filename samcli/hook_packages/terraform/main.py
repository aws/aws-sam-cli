"""
Module for Terraform hook entry points
"""
from .hooks.prepare import prepare as tf_prepare


def prepare(params: dict) -> dict:
    return tf_prepare(params)
