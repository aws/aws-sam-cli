"""
CLI command for "destroy" command
"""

import click

from samcli.cli.main import pass_context, common_options
from samcli.lib.samlib.cloudformation_command import execute_command
from samcli.commands.exceptions import UserException


SHORT_HELP = "Destroy an AWS SAM application. This is an alias for 'aws cloudformation destroy'."


HELP_TEXT = """The sam destroy command destroy a Cloudformation Stack and destroys your resources.

\b
e.g. sam destroy --stack-name sam-app

\b
This is an alias for aws cloudformation destroy. To learn about other parameters you can use,
run aws cloudformation destroy help.
"""


@click.command("destroy", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True}, help=HELP_TEXT)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.option('--stack-name',
              required=True,
              help="The name of the AWS CloudFormation stack you're destroying to. "
                   "If you specify an existing stack, the command updates the stack. "
                   "If you specify a new stack, the command creates it.")
@common_options
@pass_context
def cli(ctx, args, stack_name):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(args, stack_name)  # pragma: no cover


def do_cli(args, stack_name):
    args = args + ('--stack-name', stack_name)

    try:
        execute_command("destroy", args)
    except OSError as ex:
        raise UserException(str(ex))
