"""
CLI command for "local callback fail" command
"""

import logging
from typing import Any, Dict, List, Optional

import click

from samcli.cli.main import common_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.fail.core.command import LocalCallbackFailCommand
from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.durable_formatters import format_callback_failure_message

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Send a failure callback to a durable function execution.
"""

DESCRIPTION = """
  Send a failure callback to a durable function execution.
"""


@click.command(
    "fail",
    cls=LocalCallbackFailCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@click.argument("callback_id", required=True)
@click.option("--error-data", help="Additional error data")
@click.option("--stack-trace", multiple=True, help="Stack trace entries (can be specified multiple times)")
@click.option("--error-type", help="Type of error")
@click.option("--error-message", help="Detailed error message")
@common_options
@track_command
def cli(
    callback_id: str,
    error_data: Optional[str],
    stack_trace: tuple,
    error_type: Optional[str],
    error_message: Optional[str],
):
    """
    Send a failure callback to a durable function execution
    """
    do_cli(callback_id, error_data, stack_trace, error_type, error_message)


def do_cli(
    callback_id: str,
    error_data: Optional[str],
    stack_trace: tuple,
    error_type: Optional[str],
    error_message: Optional[str],
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    try:
        _send_callback_failure(
            callback_id=callback_id,
            error_data=error_data,
            stack_trace=list(stack_trace) if stack_trace else None,
            error_type=error_type,
            error_message=error_message,
        )
        click.echo(format_callback_failure_message(callback_id, error_data, error_type, error_message))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _send_callback_failure(
    callback_id: str,
    error_data: Optional[str],
    stack_trace: Optional[List[str]],
    error_type: Optional[str],
    error_message: Optional[str],
) -> Dict[str, Any]:
    """
    Send failure callback using the durable context.

    Args:
        callback_id: The callback ID to send response to
        error_data: Additional error data
        stack_trace: Stack trace entries as list of strings
        error_type: Type of error
        error_message: Detailed error message

    Returns:
        Dict containing the API response
    """
    LOG.debug("Sending failure callback for ID '%s'", callback_id)

    try:
        with DurableContext() as context:
            response = context.client.send_callback_failure(
                callback_id, error_data, stack_trace, error_type, error_message
            )
            LOG.debug("Failure callback sent successfully")
            return response

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
