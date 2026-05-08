"""
Command group for "list" suite for commands.
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "endpoints": "samcli.commands.list.endpoints.command.cli",
        "resources": "samcli.commands.list.resources.command.cli",
        "stack-outputs": "samcli.commands.list.stack_outputs.command.cli",
    },
)
def cli():
    """
    Get local and deployed state of serverless application.
    """
