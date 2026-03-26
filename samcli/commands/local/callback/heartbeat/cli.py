"""
CLI command for "local callback heartbeat" command
"""

import logging
from typing import Any, Dict

import click

from samcli.cli.main import common_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.heartbeat.core.command import LocalCallbackHeartbeatCommand
from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.durable_formatters import format_callback_heartbeat_message

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Send a heartbeat callback to a durable function execution.
"""

DESCRIPTION = """
  Send a heartbeat callback to a durable function execution.
"""


@click.command(
    "heartbeat",
    cls=LocalCallbackHeartbeatCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@click.argument("callback_id", required=True)
@common_options
@track_command
def cli(callback_id: str):
    """
    Send a heartbeat callback to a durable function execution
    """
    do_cli(callback_id)


def do_cli(callback_id: str):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    try:
        _send_callback_heartbeat(callback_id=callback_id)
        click.echo(format_callback_heartbeat_message(callback_id))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _send_callback_heartbeat(callback_id: str) -> Dict[str, Any]:
    """
    Send heartbeat callback using the durable context.

    Args:
        callback_id: The callback ID to send response to

    Returns:
        Dict containing the API response
    """
    LOG.debug("Sending heartbeat callback for ID '%s'", callback_id)

    try:
        with DurableContext() as context:
            response = context.client.send_callback_heartbeat(callback_id)
            LOG.debug("Heartbeat callback sent successfully")
            return response

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
