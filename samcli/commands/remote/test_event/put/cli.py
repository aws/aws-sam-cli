"""CLI command for "test-event put" command."""

import logging
import sys
from io import TextIOWrapper
from typing import Optional

import click
from yaml import YAMLError

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.remote.exceptions import IllFormedEventData
from samcli.commands.remote.test_event.put.core.command import RemoteTestEventPutCommand
from samcli.commands.remote.test_event.utils import not_empty_callback, required_with_custom_error_callback
from samcli.lib.cli_validation.remote_invoke_options_validations import (
    stack_name_or_resource_id_atleast_one_option_validation,
)
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Saves an event from a local file as a remote test event.
"""

SHORT_HELP = "Put a remote test event."

DESCRIPTION = """
  Saves an event from a local file as a remote test event. It fails if the event already exists, but it can be forced
  with the --force parameter to overwrite. 
"""


@click.command(
    "put",
    cls=RemoteTestEventPutCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    short_help=SHORT_HELP,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.option("--stack-name", help="Name of the stack to get the resource information from")
@click.option("--name", help="Name of the event to be put", required=True, callback=not_empty_callback)
@click.option(
    "--file",
    help="File with the contents of the event to be saved (or `-` for stdin)",
    type=click.File("r"),
    callback=required_with_custom_error_callback(
        "The option '--file' is required (You can provide '-' to read from stdin)"
    ),
)
@click.option("--force", "-f", is_flag=True, help="Force saving the event even if it already exists")
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
    resource_id: Optional[str],
    name: str,
    file: TextIOWrapper,
    force: bool,
    config_file: str,
    config_env: str,
):
    """
    `sam remote test-event put` command entry point
    """
    do_cli(
        stack_name,
        resource_id,
        name,
        file,
        force,
        ctx.region,
        ctx.profile,
        config_file,
        config_env,
    )


def do_cli(
    stack_name: Optional[str],
    resource_id: Optional[str],
    name: str,
    file: TextIOWrapper,
    force: bool,
    region: str,
    profile: str,
    config_file: str,
    config_env: str,
):
    """
    Implementation of ``cli`` method
    """
    import json
    from json import JSONDecodeError

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

    if file == sys.stdin:
        LOG.info("Reading event from stdin")

    try:
        contents = file.read()
        if not contents.strip():
            raise IllFormedEventData("Event can't be empty")
        # parse_yaml to protect against JSON injection, then dump to json to keep proper JSON format
        data = yaml_parse(contents)
        event_data = json.dumps(data)
        LOG.debug("Creating remote event %s from resource: %s", name, function_resource)
        lambda_test_event.create_event(name, function_resource, event_data, force=force)
        click.echo(f"Put remote event '{name}' completed successfully")
    except (ValueError, YAMLError, JSONDecodeError) as ex:
        raise IllFormedEventData(f"File {file.name} doesn't contain a valid JSON:\n {ex}") from ex
