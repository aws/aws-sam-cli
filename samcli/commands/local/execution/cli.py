"""
Command group for "execution" suite for durable function execution commands
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    "execution",
    cls=LazyGroup,
    lazy_subcommands={
        "get": "samcli.commands.local.execution.get.cli.cli",
        "history": "samcli.commands.local.execution.history.cli.cli",
        "stop": "samcli.commands.local.execution.stop.cli.cli",
    },
)
def cli():
    """
    Manage durable function executions
    """
