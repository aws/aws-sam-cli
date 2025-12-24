"""
CLI command for "remote callback fail" command
"""

import logging
from typing import Optional

import click
from boto3 import Session

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.exceptions import UserException
from samcli.commands.remote.callback.fail.core.command import RemoteCallbackFailCommand
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.durable_formatters import format_callback_failure_message
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Send a callback failure to a remote durable function execution.
"""

DESCRIPTION = """
  Send a callback failure to a remote durable function execution.
"""


@click.command(
    "fail",
    cls=RemoteCallbackFailCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=True,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.argument("callback_id", required=True)
@click.option("--error-data", help="Additional error data")
@click.option("--stack-trace", multiple=True, help="Stack trace entries (can be specified multiple times)")
@click.option("--error-type", help="Type of error")
@click.option("--error-message", help="Detailed error message")
@common_options
@aws_creds_options
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(
    ctx: Context,
    callback_id: str,
    error_data: Optional[str],
    stack_trace: tuple,
    error_type: Optional[str],
    error_message: Optional[str],
    save_params: bool,
    config_file: str,
    config_env: str,
):
    """
    Send a callback failure to a remote durable function execution
    """
    do_cli(ctx, callback_id, error_data, stack_trace, error_type, error_message)


def do_cli(
    ctx: Context,
    callback_id: str,
    error_data: Optional[str],
    stack_trace: tuple,
    error_type: Optional[str],
    error_message: Optional[str],
):
    """
    Implementation of the ``cli`` method
    """
    try:
        # Create boto3 session
        session = Session(profile_name=ctx.profile, region_name=ctx.region)

        # Create client provider with session
        client_provider = get_boto_client_provider_from_session_with_config(session)

        # Create lambda client
        lambda_client = client_provider("lambda")

        # Create durable functions client wrapper
        durable_client = DurableFunctionsClient(lambda_client)

        # Call SendDurableExecutionCallbackFailure
        durable_client.send_callback_failure(
            callback_id, error_data, list(stack_trace) if stack_trace else None, error_type, error_message
        )

        # Show success message
        click.echo(format_callback_failure_message(callback_id, error_data, error_type, error_message))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
