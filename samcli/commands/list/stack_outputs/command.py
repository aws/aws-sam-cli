"""
Sets up the cli for stack-outputs
"""

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.list.cli_common.options import output_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

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
@configuration_option(provider=ConfigProvider(section="parameters"))
@output_option
@aws_creds_options
@common_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(self, stack_name, output, config_file, config_env):
    """
    `sam list stack-outputs` command entry point
    """
    do_cli(stack_name=stack_name, output=output, region=self.region, profile=self.profile)


def do_cli(stack_name, output, region, profile):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.list.stack_outputs.stack_outputs_context import StackOutputsContext

    with StackOutputsContext(
        stack_name=stack_name, output=output, region=region, profile=profile
    ) as stack_output_context:
        stack_output_context.run()
