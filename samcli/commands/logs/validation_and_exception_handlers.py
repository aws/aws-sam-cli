"""
Contains helper functions for validation and exception handling of "sam logs" command
"""
from functools import wraps
from typing import Dict, Any, Callable

import click
from botocore.exceptions import ClientError
from click import Context, BadOptionUsage

from samcli.commands.exceptions import InvalidStackNameException
from samcli.lib.utils.boto_utils import get_client_error_code


def stack_name_cw_log_group_validation(func):
    """
    Wrapper Validation function that will run last after the all cli parmaters have been loaded
    to check for conditions surrounding `--stack-name` and `--cw-log-group`. The
    reason they are done last instead of in callback functions, is because the options depend
    on each other, and this breaks cyclic dependencies.

    :param func: Click command function
    :return: Click command function after validation
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()
        stack_name = ctx.params.get("stack_name")
        cw_log_groups = ctx.params.get("cw_log_group")
        names = ctx.params.get("name")

        # if --name is provided --stack-name should be provided as well
        if names and not stack_name:
            raise BadOptionUsage(
                option_name="--stack-name",
                ctx=ctx,
                message="Missing option. Please provide '--stack-name' when using '--name' option",
            )

        # either --stack-name or --cw-log-group flags should be provided
        if not stack_name and not cw_log_groups:
            raise BadOptionUsage(
                option_name="--stack-name",
                ctx=ctx,
                message="Missing option. Please provide '--stack-name' or '--cw-log-group'",
            )

        return func(*args, **kwargs)

    return wrapped


def _handle_client_error(ex: ClientError) -> None:
    """
    Handles client error which was caused by ListStackResources event
    """
    operation_name = ex.operation_name
    client_error_code = get_client_error_code(ex)
    if client_error_code == "ValidationError" and operation_name == "ListStackResources":
        click_context: Context = click.get_current_context()
        stack_name_value = click_context.params.get("stack_name")
        raise InvalidStackNameException(
            f"Invalid --stack-name parameter. Stack with id '{stack_name_value}' does not exist"
        )


SAM_LOGS_ADDITIONAL_EXCEPTION_HANDLERS: Dict[Any, Callable] = {ClientError: _handle_client_error}
