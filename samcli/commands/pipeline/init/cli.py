"""
CLI command for "pipeline init" command
"""
from typing import Any, Optional

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.pipeline.init.interactive_init_flow import InteractiveInitFlow
from samcli.lib.telemetry.metric import track_command

SHORT_HELP = "Generates a CI/CD pipeline configuration file."
HELP_TEXT = """
This command generates a pipeline configuration file that your CI/CD system can use to deploy
serverless applications using AWS SAM.

Before using sam pipeline init, you must bootstrap the necessary resources for each stage in your pipeline.
You can do this by running sam pipeline init --bootstrap to be guided through the setup and configuration
file generation process, or refer to resources you have previously created with the sam pipeline bootstrap command.
"""


@click.command("init", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--bootstrap",
    is_flag=True,
    default=False,
    help="Enable interactive mode that walks the user through creating necessary AWS infrastructure resources.",
)
@cli_framework_options
@pass_context
@track_command  # pylint: disable=R0914
def cli(ctx: Any, config_env: Optional[str], config_file: Optional[str], bootstrap: bool) -> None:
    """
    `sam pipeline init` command entry point
    """

    # Currently we support interactive mode only, i.e. the user doesn't provide the required arguments during the call
    # so we call do_cli without any arguments. This will change after supporting the non interactive mode.
    do_cli(bootstrap)


def do_cli(bootstrap: bool) -> None:
    """
    implementation of `sam pipeline init` command
    """
    # TODO non-interactive mode
    init_flow = InteractiveInitFlow(bootstrap)
    init_flow.do_interactive()
