"""CLI command for "test-event delete" command."""

import logging
from typing import Optional

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.remote.test_event.delete.core.command import RemoteTestEventDeleteCommand
from samcli.commands.remote.test_event.utils import not_empty_callback
from samcli.lib.cli_validation.remote_invoke_options_validations import (
    stack_name_or_resource_id_atleast_one_option_validation,
)
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Delete a remote test event for a function.
"""

SHORT_HELP = "Delete a remote test event for a function"

DESCRIPTION = """
  Delete a remote test event for a specific function stored on EventBridge Schema Registry. 
  Delete the entire schema if there are no remaining test events.
"""


@click.command(
    "delete",
    cls=RemoteTestEventDeleteCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    short_help=SHORT_HELP,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.option("--stack-name", help="Name of the stack to get the resource information from")
@click.option("--name", help="Name of the event to be deleted", required=True, callback=not_empty_callback)
@click.argument("resource-id", required=False)
@aws_creds_options
@common_options
@print_cmdline_args
@stack_name_or_resource_id_atleast_one_option_validation
@pass_context
@check_newer_version
@track_command
@command_exception_handler
def cli(
    ctx: Context,
    stack_name: Optional[str],
    name: str,
    resource_id: Optional[str],
    config_file: str,
    config_env: str,
) -> None:
    """
    `sam remote test-event delete` command entry point
    """

    do_cli(
        stack_name,
        resource_id,
        name,
        ctx.region,
        ctx.profile,
        config_file,
        config_env,
    )


def do_cli(
    stack_name: Optional[str],
    resource_id: Optional[str],
    event_name: str,
    region: str,
    profile: str,
    config_file: str,
    config_env: str,
) -> None:
    """
    Implimentation of ``cli`` method
    """
    from samcli.commands.exceptions import UserException
    from samcli.commands.remote.remote_invoke_context import RemoteInvokeContext
    from samcli.lib.remote_invoke.exceptions import (
        ErrorBotoApiCallException,
        InvalideBotoResponseException,
        InvalidResourceBotoParameterException,
    )
    from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config, get_boto_resource_provider_with_config

    boto_client_provider = get_boto_client_provider_with_config(region_name=region, profile=profile)
    boto_resource_provider = get_boto_resource_provider_with_config(region_name=region, profile=profile)

    function_resource = None
    try:
        with RemoteInvokeContext(
            boto_client_provider=boto_client_provider,
            boto_resource_provider=boto_resource_provider,
            stack_name=stack_name,
            resource_id=resource_id,
        ) as remote_invoke_context:
            if not remote_invoke_context.resource_summary:
                raise remote_invoke_context.missing_resource_exception()
            function_resource = remote_invoke_context.resource_summary
            lambda_test_event = remote_invoke_context.get_lambda_shared_test_event_provider()

    except (ErrorBotoApiCallException, InvalideBotoResponseException, InvalidResourceBotoParameterException) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex

    LOG.debug("Deleting remote event '%s' from resource: %s", event_name, function_resource)
    lambda_test_event.delete_event(event_name, function_resource)

    click.echo(f"Delete remote event '{event_name}' completed successfully")
