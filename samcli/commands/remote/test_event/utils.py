"""Utilities for Remote Test Event commands"""

from typing import Any

import click


def required_with_custom_error_callback(custom_error: str):
    """
    It returns a callback with a custom error message when the configured option is not provided.
    You shouldn't add `required=True` to the click.option for this to work correctly.

    Parameters
    ----------
    custom_error : str
        Error message that should be thrown when the option is not provided.
    """

    def callback(ctx: click.core.Context, param: click.Option, provided_value: Any):
        is_option_provided: Any = provided_value or ctx.default_map.get(param.name)  # type: ignore
        if not is_option_provided:
            raise click.BadOptionUsage(
                option_name=param.name,  # type: ignore
                ctx=ctx,
                message=custom_error,
            )
        return provided_value

    return callback


def not_empty_callback(ctx: click.core.Context, param: click.Option, provided_value: Any):
    """
    Callback that checks that the option is not empty.
    This works on an option that's already marked with `required=True`, but this enforces
    that it's also not empty (Usually possible forcing an empty string like  `--param-name ""`)

    """
    is_option_provided = provided_value or ctx.default_map.get(param.name)  # type: ignore
    if not is_option_provided:
        raise click.BadOptionUsage(
            option_name=param.name,  # type: ignore
            ctx=ctx,
            message=(f"Value for option '{param.name}' can't be empty."),
        )
    return provided_value
