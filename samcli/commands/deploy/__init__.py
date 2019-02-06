"""
CLI command for "deploy" command
"""

import click

from samcli.cli.main import pass_context, common_options
from samcli.lib.samlib.cloudformation_command import execute_command
from samcli.commands.exceptions import UserException


SHORT_HELP = "Deploy an AWS SAM application. This is an alias for 'aws cloudformation deploy'."


HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
This is an alias for aws cloudformation deploy. To learn about other parameters you can use,
run aws cloudformation deploy help.
"""


@click.command("deploy", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True}, help=HELP_TEXT)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.option('--template-file',
              required=True,
              type=click.Path(),
              help="The path where your AWS SAM template is located")
@click.option('--stack-name',
              required=True,
              help="The name of the AWS CloudFormation stack you're deploying to. "
                   "If you specify an existing stack, the command updates the stack. "
                   "If you specify a new stack, the command creates it.")
@common_options
@pass_context
def cli(ctx, args, template_file, stack_name):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(args, template_file, stack_name)  # pragma: no cover


def do_cli(args, template_file, stack_name):
    args = args + ('--stack-name', stack_name)

    try:
        execute_command("deploy", args, template_file=template_file)
    except OSError as ex:
        raise UserException(str(ex))
