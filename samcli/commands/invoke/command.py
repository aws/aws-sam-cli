"""
CLI command for "invoke" command
"""

import logging

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.events import get_event
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
You can use this command to remotly execute your function in AWS.
You can pass in an event body using the -e (--event) parameter.
Logs from the Lambda function will be written to stdout.\n
\b
Invoking a Lambda function without an input event
$ sam invoke "HelloWorldFunction --stack-name mystack"\n
\b
Invoking a specific Lambda version
$ sam invoke "HelloWorldFunction --stack-name mystack --qualifier 7"\n
\b
Invoking a Lambda function using an event file
$ sam invoke "HelloWorldFunction" --stack-name mystack -e event.json\n
\b
Invoking a Lambda function using input from stdin
$ echo '{"message": "Hey, are you there?" }' | sam invoke "HelloWorldFunction" --stack-name mystack --event -
\b
You can also invoke using the function's name.
$ sam invoke mystack-HelloWorldFunction-1FJ8PD36GML2Q \n
"""


@click.command("invoke", help=HELP_TEXT, short_help="Invokes a remote lambda from aws")
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option("--qualifier", default=None, help="Version of the Lambda Function.")
@click.option("--stack-name", default=None, help="Name of the AWS CloudFormation stack that the function is a part of.")
@click.option(
    "--event",
    "-e",
    type=click.Path(),
    help="JSON file containing event data passed to the Lambda function during invoke. If this option "
         "is not specified, no event is assumed. Pass in the value '-' to input JSON via stdin",
)
@cli_framework_options
@aws_creds_options
@click.argument("function_name", required=False)
@pass_context
@track_command
@check_newer_version
def cli(
        ctx,
        function_name,
        event,
        stack_name,
        qualifier,
        config_file,
        config_env,
):  # pylint: disable=redefined-builtin
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(function_name, stack_name, event, qualifier)  # pragma: no cover


def do_cli(function_name, stack_name, event, qualifier):
    """
    Implementation of the ``cli`` method
    """
    from .invoke_context import InvokeCommandContext

    LOG.debug("'invoke' command is called")

    if event:
        event_data = get_event(event)
    else:
        event_data = "{}"

    with InvokeCommandContext(
            function_name,
            stack_name=stack_name
    ) as context:

        context.lambda_runner.invoke(
            context.function_physical_id, event=event_data, qualifier=qualifier,
            stdout=click.get_binary_stream('stdout'), stderr=click.get_binary_stream('stderr')
        )
