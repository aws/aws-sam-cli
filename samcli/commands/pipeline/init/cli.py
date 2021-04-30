"""
CLI command for "pipeline init" command
"""
from typing import Any, Optional

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.pipeline.init.interactive_init_flow import do_interactive
from samcli.lib.telemetry.metric import track_command

SHORT_HELP = "Generates CI/CD pipeline configuration files."
HELP_TEXT = """
Generates CI/CD pipeline configuration files for a chosen CI/CD provider such as Jenkins, 
GitLab CI/CD or GitHub Actions
"""


@click.command("init", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@cli_framework_options
@pass_context
@track_command  # pylint: disable=R0914
def cli(
    ctx: Any,
    config_env: Optional[str],
    config_file: Optional[str],
) -> None:
    """
    `sam pipeline init` command entry point
    """

    # Currently we support interactive mode only, i.e. the user doesn't provide the required arguments during the call
    # so we call do_cli without any arguments. This will change after supporting the non interactive mode.
    do_cli()


def do_cli() -> None:
    """
    implementation of `sam pipeline init` command
    """
    # TODO non-interactive mode
    do_interactive()
