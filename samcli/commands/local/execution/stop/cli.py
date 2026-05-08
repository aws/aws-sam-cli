"""
CLI command for "local execution stop" command
"""

import logging
from typing import Optional

import click

from samcli.cli.main import common_options as cli_framework_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.commands.local.execution.stop.core.command import LocalExecutionStopCommand
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.durable_formatters import format_stop_execution_message

LOG = logging.getLogger(__name__)

HELP_TEXT = """
    Stop a durable function execution.
"""

DESCRIPTION = """
  Stop a running durable function execution.
"""


@click.command(
    "stop",
    cls=LocalExecutionStopCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=False,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@cli_framework_options
@click.argument("durable_execution_arn", required=True)
@click.option("--error-message", help="Error message to associate with the stopped execution")
@click.option("--error-type", help="Error type to associate with the stopped execution")
@click.option("--error-data", help="Error data to associate with the stopped execution")
@click.option("--stack-trace", multiple=True, help="Stack trace entries (can be specified multiple times)")
@track_command
def cli(durable_execution_arn, error_message, error_type, error_data, stack_trace):
    """
    Stop a durable function execution
    """
    do_cli(durable_execution_arn, error_message, error_type, error_data, list(stack_trace))


def do_cli(
    durable_execution_arn: str,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    error_data: Optional[str] = None,
    stack_trace: Optional[list] = None,
):
    """
    Implementation of the ``cli`` method
    """
    try:
        _stop_durable_execution(
            durable_execution_arn=durable_execution_arn,
            error_message=error_message,
            error_type=error_type,
            error_data=error_data,
            stack_trace=stack_trace,
        )
        click.echo(format_stop_execution_message(durable_execution_arn, error_type, error_message, error_data))
    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex


def _stop_durable_execution(
    durable_execution_arn: str,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    error_data: Optional[str] = None,
    stack_trace: Optional[list] = None,
):
    """
    Stop durable execution using the durable context.
    """
    LOG.debug("Stopping durable execution for ARN '%s'", durable_execution_arn)

    try:
        with DurableContext() as context:
            response = context.client.stop_durable_execution(
                durable_execution_arn,
                error_message=error_message,
                error_type=error_type,
                error_data=error_data,
                stack_trace=stack_trace,
            )
            LOG.debug("Durable execution stopped successfully")
            return response
    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
