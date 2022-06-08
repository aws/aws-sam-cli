"""
Sets up the cli for stack-outputs
"""

import click

from samcli.commands.list.cli_common.options import output_option
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.telemetry.metric import track_command


HELP_TEXT = """
Get the stack outputs as defined in the SAM/CloudFormation template.
"""


@click.command(name="stack-outputs", help=HELP_TEXT)
@click.option(
    "--stack-name",
    help="Name of corresponding deployed stack. ",
    required=True,
    type=click.STRING,
)
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
    from samcli.commands.list.stack_outputs.stack_outputs_context import StackOutputsContext

    with StackOutputsContext(
        stack_name=stack_name, output=output, region=region, profile=profile
    ) as stack_output_context:
        stack_output_context.run()

