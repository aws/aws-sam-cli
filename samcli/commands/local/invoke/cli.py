"""
CLI command for "local invoke" command
"""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.cli_common.options import invoke_common_options
from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.invoke_context import InvokeContext
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

LOG = logging.getLogger(__name__)


HELP_TEXT = """
You can use this command to execute your function in a Lambda-like environment locally.
You can pass in the event body via stdin or by using the -e (--event) parameter.
Logs from the Lambda function will be output via stdout.\n
\b
Invoking a Lambda function using an event file
$ sam local invoke "HelloWorldFunction" -e event.json\n
\b
Invoking a Lambda function using input from stdin
$ echo '{"message": "Hey, are you there?" }' | sam local invoke "HelloWorldFunction" \n
"""


@click.command("invoke", help=HELP_TEXT, short_help="Invokes a local Lambda function once.")
@click.option("--event", '-e',
              type=click.Path(),
              default="-",  # Defaults to stdin
              help="JSON file containing event data passed to the Lambda function during invoke. If this option "
                   "is not specified, we will default to reading JSON from stdin")
@invoke_common_options
@cli_framework_options
@click.argument('function_identifier', required=False)
@pass_context
def cli(ctx, function_identifier, template, event, env_vars, debug_port, debug_args, docker_volume_basedir,
        docker_network, log_file, skip_pull_image, profile):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, function_identifier, template, event, env_vars, debug_port, debug_args, docker_volume_basedir,
           docker_network, log_file, skip_pull_image, profile)  # pragma: no cover


def do_cli(ctx, function_identifier, template, event, env_vars, debug_port, debug_args, docker_volume_basedir,
           docker_network, log_file, skip_pull_image, profile):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    LOG.debug("local invoke command is called")

    event_data = _get_event(event)

    # Pass all inputs to setup necessary context to invoke function locally.
    # Handler exception raised by the processor for invalid args and print errors
    try:

        with InvokeContext(template_file=template,
                           function_identifier=function_identifier,
                           env_vars_file=env_vars,
                           debug_port=debug_port,
                           debug_args=debug_args,
                           docker_volume_basedir=docker_volume_basedir,
                           docker_network=docker_network,
                           log_file=log_file,
                           skip_pull_image=skip_pull_image,
                           aws_profile=profile) as context:

            # Invoke the function
            context.local_lambda_runner.invoke(context.function_name,
                                               event=event_data,
                                               stdout=context.stdout,
                                               stderr=context.stderr)

    except FunctionNotFound:
        raise UserException("Function {} not found in template".format(function_identifier))
    except InvalidSamDocumentException as ex:
        raise UserException(str(ex))


def _get_event(event_file_name):
    """
    Read the event JSON data from the given file. If no file is provided, read the event from stdin.

    :param string event_file_name: Path to event file, or '-' for stdin
    :return string: Contents of the event file or stdin
    """

    if event_file_name == "-":
        # If event is empty, listen to stdin for event data until EOF
        LOG.info("Reading invoke payload from stdin (you can also pass it from file with --event)")

    # click.open_file knows to open stdin when filename is '-'. This is safer than manually opening streams, and
    # accidentally closing a standard stream
    with click.open_file(event_file_name, 'r') as fp:
        return fp.read()
