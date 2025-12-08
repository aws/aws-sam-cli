"""
CLI command for "local callback succeed" command
"""

import logging
from typing import Any, Dict, Optional

import click

from samcli.cli.main import common_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.succeed.core.command import LocalCallbackSucceedCommand
from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.durable_formatters import format_callback_success_message

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Send a success callback to a durable function execution.
"""

DESCRIPTION = """
  Send a success callback to a durable function execution.
"""


@click.command(
    "succeed",
    cls=LocalCallbackSucceedCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@click.argument("callback_id", required=True)
@click.option("--result", "-r", help="Success result payload as string")
@common_options
@track_command
def cli(callback_id: str, result: Optional[str]):
    """
    Send a success callback to a durable function execution
    """
    do_cli(callback_id, result)


def do_cli(callback_id: str, result: Optional[str]):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    try:
        _send_callback_success(callback_id=callback_id, result=result)
        click.echo(format_callback_success_message(callback_id, result))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _send_callback_success(callback_id: str, result: Optional[str]) -> Dict[str, Any]:
    """
    Send success callback using the durable context.

    Args:
        callback_id: The callback ID to send response to
        result: Success result payload as string

    Returns:
        Dict containing the API response
    """
    LOG.debug("Sending success callback for ID '%s'", callback_id)

    try:
        with DurableContext() as context:
            response = context.client.send_callback_success(callback_id, result)
            LOG.debug("Success callback sent successfully")
            return response

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
