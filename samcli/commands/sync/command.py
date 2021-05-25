"""CLI command for "sync" command."""

import logging

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.commands._utils.options import template_common_option

from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Update/sync local artifacts to AWS
"""
SHORT_HELP = "Sync a project to AWS"


@click.command("sync", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@template_common_option
@click.option("--infra", help="Sync infrastructure")
@click.option(
    "--stack-name",
    required=False,
    help="The name of the AWS CloudFormation stack you're deploying to. "
    "If you specify an existing stack, the command updates the stack. "
    "If you specify a new stack, the command creates it.",
)
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
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template_file)  # pragma: no cover


def do_cli(ctx, template):
    """Sync the application to AWS based on command line inputs."""
