"""
This file contains validation for --payload and --payload-file options
"""
from functools import wraps

import click

from samcli.commands._utils.option_validator import Validator


def payload_and_payload_file_options_validation(func):
    """
    This function validates that both --payload and --payload-file should not be provided

    Parameters
    ----------
    func :
        Command that would be executed, in this case it is 'sam test'

    Returns
    -------
        A wrapper function which will first validate options and will execute command if validation succeeds
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()

        payload = ctx.params.get("payload")
        payload_file = ctx.params.get("payload_file")

        validator = Validator(
            validation_function=lambda: payload and payload_file,
            exception=click.BadOptionUsage(
                option_name="--payload-file",
                ctx=ctx,
                message="Both '--payload-file' and '--payload' cannot be provided. "
                "Please check that you don't have both specified in the command or in a configuration file",
            ),
        )

        validator.validate()

        return func(*args, **kwargs)

    return wrapped
