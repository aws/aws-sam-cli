"""
CLI command for "remote execution stop" command
"""

import logging

import click
from boto3 import Session

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.cli.types import DurableExecutionArnType
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.exceptions import UserException
from samcli.commands.remote.execution.stop.core.command import RemoteExecutionStopCommand
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.durable_formatters import format_stop_execution_message
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Stop a durable function execution.
"""

SHORT_HELP = "Stop remote durable execution"

DESCRIPTION = """
  Stop a running durable function execution in AWS Lambda.
"""


@click.command(
    "stop",
    cls=RemoteExecutionStopCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    short_help=SHORT_HELP,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.argument("durable_execution_arn", type=DurableExecutionArnType(), required=True)
@click.option("--error-message", help="Error message to associate with the stopped execution")
@click.option("--error-type", help="Error type to associate with the stopped execution")
@click.option("--error-data", help="Error data to associate with the stopped execution")
@click.option("--stack-trace", multiple=True, help="Stack trace entries (can be specified multiple times)")
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
    durable_execution_arn: str,
    error_message: str,
    error_type: str,
    error_data: str,
    stack_trace: tuple,
    save_params: bool,
    config_file: str,
    config_env: str,
):
    """
    Stop a remote durable function execution
    """
    do_cli(ctx, durable_execution_arn, error_message, error_type, error_data, list(stack_trace))


def do_cli(
    ctx: Context, durable_execution_arn: str, error_message=None, error_type=None, error_data=None, stack_trace=None
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

        # Call StopDurableExecution with optional parameters
        durable_client.stop_durable_execution(
            durable_execution_arn,
            error_message=error_message,
            error_type=error_type,
            error_data=error_data,
            stack_trace=stack_trace,
        )

        # Output formatted message
        click.echo(format_stop_execution_message(durable_execution_arn, error_type, error_message, error_data))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
