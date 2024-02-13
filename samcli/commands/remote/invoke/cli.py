"""CLI command for "invoke" command."""

import logging
from io import TextIOWrapper

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.cli.types import RemoteInvokeOutputFormatType
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import remote_invoke_parameter_option
from samcli.commands.remote.invoke.core.command import RemoteInvokeCommand
from samcli.lib.cli_validation.remote_invoke_options_validations import (
    event_and_event_file_options_validation,
    stack_name_or_resource_id_atleast_one_option_validation,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeOutputFormat
from samcli.lib.telemetry.event import EventTracker
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Invoke or send an event to resources in the cloud.
"""
SHORT_HELP = "Invoke a deployed resource in the cloud"

DESCRIPTION = """
  Invoke or send an event to resources in the cloud.
  An event body can be passed using either -e (--event) or --event-file parameter.
  
  This command can be used to invoke a Lambda Function and get the output payload, start a State Machine execution
  and wait for the output of the final step, send a message to SQS Queue, or put a data record to
  Kinesis Data Streams.

  Returned response will be written to stdout. Lambda logs and Step Function execution
  errors will be written to stderr.
"""


@click.command(
    "invoke",
    cls=RemoteInvokeCommand,
    help=HELP_TEXT,
    description=DESCRIPTION,
    short_help=SHORT_HELP,
    requires_credentials=True,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.option("--stack-name", required=False, help="Name of the stack to get the resource information from")
@click.argument("resource-id", required=False)
@click.option(
    "--event",
    "-e",
    help="The event that will be sent to the resource. The target parameter will depend on the resource type. "
    "For instance: 'Payload' for Lambda which can be passed as a JSON string, 'Input' for Step Functions, "
    "'MessageBody' for SQS, and 'Data' for Kinesis data streams.",
)
@click.option(
    "--event-file",
    type=click.File("r", encoding="utf-8"),
    help="The file that contains the event that will be sent to the resource.",
)
@click.option(
    "--test-event-name",
    help="Name of the remote test event to send to the resource",
)
@click.option(
    "--output",
    help="Output the results from the command in a given output format. "
    "The text format prints a readable AWS API response. The json format prints the full AWS API response.",
    default=RemoteInvokeOutputFormat.TEXT.name.lower(),
    type=RemoteInvokeOutputFormatType(RemoteInvokeOutputFormat),
)
@remote_invoke_parameter_option
@stack_name_or_resource_id_atleast_one_option_validation
@event_and_event_file_options_validation
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
    stack_name: str,
    resource_id: str,
    event: str,
    event_file: TextIOWrapper,
    output: RemoteInvokeOutputFormat,
    test_event_name: str,
    parameter: dict,
    save_params: bool,
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
        output,
        parameter,
        test_event_name,
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
    output: RemoteInvokeOutputFormat,
    parameter: dict,
    test_event_name: str,
    region: str,
    profile: str,
    config_file: str,
    config_env: str,
) -> None:
    """
    Implementation of the ``cli`` method
    """
    from botocore.exceptions import (
        NoCredentialsError,
        NoRegionError,
        ProfileNotFound,
    )

    from samcli.commands.exceptions import UserException
    from samcli.commands.remote.remote_invoke_context import RemoteInvokeContext
    from samcli.lib.remote_invoke.exceptions import (
        ErrorBotoApiCallException,
        InvalideBotoResponseException,
        InvalidResourceBotoParameterException,
    )
    from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeEventType, RemoteInvokeExecutionInfo
    from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config, get_boto_resource_provider_with_config

    try:
        boto_client_provider = get_boto_client_provider_with_config(region_name=region, profile=profile)
        boto_resource_provider = get_boto_resource_provider_with_config(region_name=region, profile=profile)
        with RemoteInvokeContext(
            boto_client_provider=boto_client_provider,
            boto_resource_provider=boto_resource_provider,
            stack_name=stack_name,
            resource_id=resource_id,
        ) as remote_invoke_context:
            if (
                test_event_name
                and remote_invoke_context.resource_summary
                and remote_invoke_context.resource_summary.resource_type == AWS_LAMBDA_FUNCTION
            ):
                lambda_test_event = remote_invoke_context.get_lambda_shared_test_event_provider()
                LOG.debug("Retrieving remote event %s", test_event_name)
                event = lambda_test_event.get_event(test_event_name, remote_invoke_context.resource_summary)
                LOG.debug("Remote event contents: %s", event)
            elif test_event_name:
                LOG.info("Note: remote event is only supported for AWS Lambda Function resource.")
                test_event_name = ""

            event_type = RemoteInvokeEventType.get_event_type(
                event=event,
                event_file=event_file,
                test_event_name=test_event_name,
            )
            EventTracker.track_event("RemoteInvokeEventType", event_type)

            remote_invoke_input = RemoteInvokeExecutionInfo(
                payload=event, payload_file=event_file, parameters=parameter, output_format=output
            )

            remote_invoke_context.run(remote_invoke_input=remote_invoke_input)
    except (
        ErrorBotoApiCallException,
        InvalideBotoResponseException,
        InvalidResourceBotoParameterException,
        ProfileNotFound,
        NoCredentialsError,
        NoRegionError,
    ) as ex:
        raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex
