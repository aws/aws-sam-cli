"""
CLI command for "remote callback heartbeat" command
"""

import logging

import click
from boto3 import Session

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.exceptions import UserException
from samcli.commands.remote.callback.heartbeat.core.command import RemoteCallbackHeartbeatCommand
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.durable_formatters import format_callback_heartbeat_message
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Send a callback heartbeat to a remote durable function execution.
"""

DESCRIPTION = """
  Send a callback heartbeat to a remote durable function execution.
"""


@click.command(
    "heartbeat",
    cls=RemoteCallbackHeartbeatCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    requires_credentials=True,
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.argument("callback_id", required=True)
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
    save_params: bool,
    config_file: str,
    config_env: str,
):
    """
    Send a callback heartbeat to a remote durable function execution
    """
    do_cli(ctx, callback_id)


def do_cli(ctx: Context, callback_id: str):
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

        # Call SendDurableExecutionCallbackHeartbeat
        durable_client.send_callback_heartbeat(callback_id)

        # Show success message
        click.echo(format_callback_heartbeat_message(callback_id))

    except Exception as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
