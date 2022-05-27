"""
Sets up the cli for resources
"""

import click

from samcli.commands.list.cli_common.options import stack_name_option, output_option
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args


HELP_TEXT = """
Get a summary of the testable resources in the stack.\n
This command will show both the cloud and local endpoints that can
be used with sam local and sam sync. Currently the testable resources
are lambda functions and API Gateway API resources.
"""


@click.command(name="testable-resources", help=HELP_TEXT)
@stack_name_option
@output_option
@output_option
@aws_creds_options
@common_options
@pass_context
@print_cmdline_args
def cli(self, stack_name, output):
    """
    Generate an event for one of the services listed below:
    """
    do_cli(stack_name, output)


def do_cli(stack_name, output):
    pass
