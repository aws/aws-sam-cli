"""
CLI command for "show" command
"""

import logging
from samcli.commands.deploy.command import HELP_TEXT

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.commands._utils.options import guided_deploy_stack_name, template_click_option
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Use this command to fetch CloudFormation Output from an existing stack.\n
"""


@click.command("show", help=HELP_TEXT, short_help="Show CloudFormation template output")
@click.option(
    "--stack-name",
    required=False,
    help="The name of the AWS CloudFormation stack you're fetchting output for.",
)
@cli_framework_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(ctx, stack_name):
    """
    `sam show` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(stack_name)


def do_cli(stack_name):
    """
    Implementation of the ``cli`` method
    """
    from .show_context import ShowOutputContext

    with ShowOutputContext(stack_name) as context:
        context.show()
