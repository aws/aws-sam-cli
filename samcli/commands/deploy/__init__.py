"""
CLI command for "deploy" command
"""

import click

from samcli.cli.main import pass_context, common_options
from samcli.lib.samlib.cloudformation_command import execute_command


SHORT_HELP = "Deploy an AWS SAM application. This is an alias for 'aws cloudformation deploy'."


@click.command("deploy", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@common_options
@pass_context
def cli(ctx, args):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(args)  # pragma: no cover


def do_cli(args):
    execute_command("deploy", args)
