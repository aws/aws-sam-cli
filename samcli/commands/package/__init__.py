"""
CLI command for "package" command
"""

from functools import partial
import click

from samcli.cli.main import pass_context, common_options
from samcli.commands._utils.options import get_or_default_template_file_name, _TEMPLATE_OPTION_DEFAULT_VALUE
from samcli.lib.samlib.cloudformation_command import execute_command
from samcli.commands.exceptions import UserException


SHORT_HELP = "Package an AWS SAM application. This is an alias for 'aws cloudformation package'."


@click.command("package", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True})
@click.option('--template-file',
              default=_TEMPLATE_OPTION_DEFAULT_VALUE,
              type=click.Path(),
              callback=partial(get_or_default_template_file_name, include_build=True),
              show_default=False,
              help="The path where your AWS SAM template is located")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@common_options
@pass_context
def cli(ctx, args, template_file):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(args, template_file)  # pragma: no cover


def do_cli(args, template_file):
    try:
        execute_command("package", args, template_file)
    except OSError as ex:
        raise UserException(str(ex))
