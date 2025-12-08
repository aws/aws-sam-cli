"""
CLI command for "local execution history" command
"""

import logging
from typing import Any, Dict

import click

from samcli.cli.main import common_options as cli_framework_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.commands.local.execution.history.core.command import LocalExecutionHistoryCommand
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.durable_formatters import format_execution_history

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Get execution history of a durable function execution.
"""

DESCRIPTION = """
  Retrieve the execution history of a specific durable function execution.
"""


@click.command(
    "history",
    cls=LocalExecutionHistoryCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@cli_framework_options
@click.argument("durable_execution_arn", required=True)
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", show_default=True, help="Output format"
)
@track_command
def cli(durable_execution_arn, format):
    """
    Get execution history of a durable function execution
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(durable_execution_arn, format)


def do_cli(durable_execution_arn: str, format: str):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    try:
        # Get durable execution history via the durable context
        result = _get_durable_execution_history(durable_execution_arn=durable_execution_arn)

        # Output in requested format
        click.echo(format_execution_history(result, format, durable_execution_arn))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _get_durable_execution_history(durable_execution_arn: str) -> Dict[str, Any]:
    """
    Retrieve durable execution history using the durable context.

    Args:
        durable_execution_arn: ARN of the durable execution to retrieve history for

    Returns:
        Dict containing execution history from the emulator API
    """
    LOG.debug("Getting durable execution history for ARN '%s'", durable_execution_arn)

    try:
        with DurableContext() as context:
            LOG.debug("Calling get_durable_execution_history for ARN: %s", durable_execution_arn)
            response = context.client.get_durable_execution_history(durable_execution_arn)
            LOG.debug("Durable execution history retrieved successfully")
            return response

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
