"""
CLI command for "docs" command
"""
import click

from samcli.cli.main import common_options, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

HELP_TEXT = """Launch the AWS SAM CLI documentation in a browser! This command will
    show information about setting up credentials, the
    AWS SAM CLI lifecycle and other useful details. 
"""


@click.command("docs", help=HELP_TEXT)
@common_options
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli():
    """
    `sam docs` command entry point
    """

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli()  # pragma: no cover


def do_cli():
    """
    Implementation of the ``cli`` method
    """
    from samcli.commands.docs.docs_context import DocsContext

    with DocsContext() as docs_context:
        docs_context.run()
