"""
This file contains validation for --event and --event-file options
"""
from functools import wraps

import click

from samcli.commands._utils.option_validator import Validator


def event_and_event_file_options_validation(func):
    """
    This function validates that both --event and --event-file should not be provided

    Parameters
    ----------
    func :
        Command that would be executed, in this case it is 'sam remote_invoke'

    Returns
    -------
        A wrapper function which will first validate options and will execute command if validation succeeds
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()

        event = ctx.params.get("event")
        event_file = ctx.params.get("event_file")

        validator = Validator(
            validation_function=lambda: event and event_file,
            exception=click.BadOptionUsage(
                option_name="--event-file",
                ctx=ctx,
                message="Both '--event-file' and '--event' cannot be provided. "
                "Please check that you don't have both specified in the command or in a configuration file",
            ),
        )

        validator.validate()

        return func(*args, **kwargs)

    return wrapped
