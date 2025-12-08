"""
CLI command for "remote execution history" command
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
from samcli.commands.remote.execution.history.core.command import RemoteExecutionHistoryCommand
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.durable_formatters import format_execution_history
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Get execution history of a durable function execution.
"""

SHORT_HELP = "Get remote durable execution history"

DESCRIPTION = """
  Retrieve the execution history of a specific durable function execution from AWS Lambda.
"""


@click.command(
    "history",
    cls=RemoteExecutionHistoryCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    short_help=SHORT_HELP,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.argument("durable_execution_arn", type=DurableExecutionArnType(), required=True)
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", show_default=True, help="Output format"
)
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
    format: str,
    save_params: bool,
    config_file: str,
    config_env: str,
):
    """
    Get execution history of a remote durable function execution
    """
    do_cli(ctx, durable_execution_arn, format)


def do_cli(ctx: Context, durable_execution_arn: str, format: str):
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

        # Call GetDurableExecutionHistory
        result = durable_client.get_durable_execution_history(durable_execution_arn)

        # Output in requested format
        click.echo(format_execution_history(result, format, durable_execution_arn))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
