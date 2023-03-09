"""
CLI command for "docs" command
"""
import click

from samcli.cli.main import common_options, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.lib.utils.version_checker import check_newer_version

HELP_TEXT = """Launch the AWS SAM CLI documentation in a browser! This command will
    open a page containing information about setting up credentials, the
    AWS SAM CLI lifecycle and other useful details. From there, navigate the
    command reference as required.
"""


@click.command("docs", help=HELP_TEXT)
@click.option(
    "--config-file",
    help=(
        "The path and file name of the configuration file containing default parameter values to use. "
        "Its default value is 'samconfig.toml' in project directory. For more information about configuration files, "
        "see: "
        "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html."
    ),
    type=click.STRING,
    default="samconfig.toml",
    show_default=True,
)
@click.option(
    "--config-env",
    help=(
        "The environment name specifying the default parameter values in the configuration file to use. "
        "Its default value is 'default'. For more information about configuration files, see: "
        "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html."
    ),
    type=click.STRING,
    default="default",
    show_default=True,
)
@common_options
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(config_file: str, config_env: str):
    """
    `sam docs` command entry point
    """

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(
        config_file=config_file,
        config_env=config_env,
    )  # pragma: no cover


def do_cli(
    config_file: str,
    config_env: str,
):
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.docs.docs_context import DocsContext

    with DocsContext(
        config_file=config_file,
        config_env=config_env,
    ) as docs_context:
        docs_context.run()
