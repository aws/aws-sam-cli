"""
This file contains validations remote invoke options
"""

import logging
import sys
from functools import wraps

import click

from samcli.commands._utils.option_validator import Validator

LOG = logging.getLogger(__name__)


def event_and_event_file_options_validation(func):
    """
    This function validates the cases when both --event and --event-file are provided and
    logs if "-" is provided for --event-file and event is read from stdin.

    Parameters
    ----------
    func :
        Command that would be executed, in this case it is 'sam remote invoke'

    Returns
    -------
        A wrapper function which will first validate options and will execute command if validation succeeds
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()

        event = ctx.params.get("event")
        event_file = ctx.params.get("event_file")
        test_event_name = ctx.params.get("test_event_name")

        def more_than_one():
            return (event and event_file) or (event and test_event_name) or (event_file and test_event_name)

        validator = Validator(
            validation_function=more_than_one,
            exception=click.BadOptionUsage(
                option_name="--event-file",
                ctx=ctx,
                message="Only one of '--event-file', '--event' and '--test-event-name' can be provided. "
                "Please check that you don't have more than one specified in the command or in a configuration file",
            ),
        )
        validator.validate()

        # If "-" is provided for --event-file, click uses it as a special file to refer to stdin.
        if event_file and event_file.fileno() == sys.stdin.fileno():
            LOG.info("Reading event from stdin (you can also pass it from file with --event-file)")
        return func(*args, **kwargs)

    return wrapped


def stack_name_or_resource_id_atleast_one_option_validation(func):
    """
    This function validates that atleast one of --stack-name option or resource_id argument should is be provided

    Parameters
    ----------
    func :
        Command that would be executed, in this case it is 'sam remote invoke'

    Returns
    -------
        A wrapper function which will first validate options and will execute command if validation succeeds
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()

        stack_name = ctx.params.get("stack_name")
        resource_id = ctx.params.get("resource_id")

        validator = Validator(
            validation_function=lambda: not (stack_name or resource_id),
            exception=click.BadOptionUsage(
                option_name="--resource-id",
                ctx=ctx,
                message="At least 1 of --stack-name or --resource-id parameters should be provided.",
            ),
        )

        validator.validate()

        return func(*args, **kwargs)

    return wrapped
