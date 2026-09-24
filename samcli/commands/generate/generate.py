"""
Main CLI group for 'generate' commands
"""

import click

from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.generate.openapi.command import cli as openapi_cli


@click.group()
@common_options
@pass_context
@print_cmdline_args
@command_exception_handler
def cli(ctx):
    """
    Generate artifacts from SAM templates.

    This command group provides subcommands to generate various artifacts
    from your SAM templates, such as OpenAPI specifications, CloudFormation
    templates, and more.
    """
    pass


# Add openapi subcommand
cli.add_command(openapi_cli)
