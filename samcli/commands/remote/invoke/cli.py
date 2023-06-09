"""CLI command for "invoke" command."""
import logging
from io import TextIOWrapper
from typing import cast

import click

from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.cli.types import RemoteInvokeOutputFormatType
from samcli.commands._utils.options import remote_invoke_parameter_option
from samcli.lib.cli_validation.remote_invoke_options_validations import (
    event_and_event_file_options_validation,
    stack_name_or_resource_id_atleast_one_option_validation,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeOutputFormat
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Invoke or send an event to cloud resources in your CFN stack
"""
SHORT_HELP = "Invoke a deployed resource in the cloud"


@click.command("invoke", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option("--stack-name", required=False, help="Name of the stack to get the resource information from")
@click.option("--resource-id", required=False, help="Name of the resource that will be invoked")
@click.option(
    "--event",
    "-e",
    help="The event that will be sent to the resource. The target parameter will depend on the resource type. "
    "For instance: 'Payload' for Lambda",
)
@click.option(
    "--event-file",
    type=click.File("r", encoding="utf-8"),
    help="The file that contains the event that will be sent to the resource",
)
@click.option(
    "--output-format",
    help="Output format for the boto API response",
    default=RemoteInvokeOutputFormat.DEFAULT.name.lower(),
    type=RemoteInvokeOutputFormatType(RemoteInvokeOutputFormat),
)
@remote_invoke_parameter_option
@stack_name_or_resource_id_atleast_one_option_validation
@event_and_event_file_options_validation
@common_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx: Context,
    stack_name: str,
    resource_id: str,
    event: str,
    event_file: TextIOWrapper,
    output_format: RemoteInvokeOutputFormat,
    parameter: dict,
    config_file: str,
    config_env: str,
) -> None:
    """
    `sam remote invoke` command entry point
    """

    do_cli(
        stack_name,
        resource_id,
        event,
        event_file,
        output_format,
        parameter,
        ctx.region,
        ctx.profile,
        config_file,
        config_env,
    )


def do_cli(
    stack_name: str,
    resource_id: str,
    event: str,
    event_file: TextIOWrapper,
    output_format: RemoteInvokeOutputFormat,
    parameter: dict,
    region: str,
    profile: str,
    config_file: str,
    config_env: str,
) -> None:
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.exceptions import UserException
    from samcli.commands.remote.remote_invoke_context import RemoteInvokeContext
    from samcli.lib.remote_invoke.exceptions import (
        ErrorBotoApiCallException,
        InvalideBotoResponseException,
        InvalidResourceBotoParameterException,
    )
    from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeExecutionInfo
    from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config, get_boto_resource_provider_with_config

    boto_client_provider = get_boto_client_provider_with_config(region_name=region)
    boto_resource_provider = get_boto_resource_provider_with_config(region_name=region)
    try:
        with RemoteInvokeContext(
            boto_client_provider=boto_client_provider,
            boto_resource_provider=boto_resource_provider,
            stack_name=stack_name,
            resource_id=resource_id,
        ) as remote_invoke_context:

            remote_invoke_input = RemoteInvokeExecutionInfo(
                payload=event, payload_file=event_file, parameters=parameter, output_format=output_format
            )

            remote_invoke_result = remote_invoke_context.run(remote_invoke_input=remote_invoke_input)

            if remote_invoke_result.is_succeeded():
                LOG.debug("Invoking resource was successfull, writing response to stdout")
                if remote_invoke_result.log_output:
                    LOG.debug("Writing log output to stderr")
                    remote_invoke_context.stderr.write(remote_invoke_result.log_output.encode())
                output_response = cast(str, remote_invoke_result.response)
                remote_invoke_context.stdout.write(output_response.encode())
            else:
                raise cast(Exception, remote_invoke_result.exception)
    except (ErrorBotoApiCallException, InvalideBotoResponseException, InvalidResourceBotoParameterException) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
