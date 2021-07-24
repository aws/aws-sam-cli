"""
CLI command for "check" command
"""

import logging

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.cli.cli_config_file import TomlProvider, configuration_option
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands._utils.options import template_option_without_build


from .calculations import Calculations
from .print_results import PrintResults

SHORT_HELP = "Checks template for bottle necks."


HELP_TEXT = """
Check your application to determine if any endpoints will not be able to
provide the expected arival rate of data. You will need to provide the
expected duration of each lambda function, as well as the expected 
per-second arrival rate. You will then be informed of the expected cost
of running this application, as well as any bottle necks that may exist.

This command must be run in the main directory of your application. 
This command will work on any SAM application. It can also run 
on a CloudFormation template.

Connections between resources can be made after all required data is
provided
"""

LOG = logging.getLogger(__name__)


@click.command(
    "check",
    short_help=SHORT_HELP,
    help=HELP_TEXT,
)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@aws_creds_options
@cli_framework_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    template_file,
    config_file,
    config_env,
):
    """
    `sam check` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(ctx, template_file)  # pragma: no cover


def do_cli(ctx, template_path):
    """
    Implementation of the ``cli`` method
    """


    from samcli.commands.check.lib.command_context import CheckContext

    context = CheckContext(ctx.region, ctx.profile, template_path)
    context.run()
