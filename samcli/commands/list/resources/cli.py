"""
Sets up the cli for resources
"""

import click

from samcli.commands.list.cli_common.options import stack_name_option, output_option
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.telemetry.metric import track_command


HELP_TEXT = """
Get a list of resources that will be deployed to CloudFormation.\n
If a stack name is provided, the corresponding physical IDs of each
resource will be mapped to the logical ID of each resource.
"""


@click.command(name="resources", help=HELP_TEXT)
@stack_name_option
@output_option
@aws_creds_options
@common_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(self, stack_name, output):
    """
    Generate an event for one of the services listed below:
    """

    do_cli(stack_name=stack_name, output=output, region=self.region, profile=self.profile)


def do_cli(stack_name, output, region, profile):
    pass
