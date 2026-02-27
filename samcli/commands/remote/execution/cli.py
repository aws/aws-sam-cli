"""
Command group for "execution" suite for durable function execution commands
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    "execution",
    cls=LazyGroup,
    lazy_subcommands={
        "get": "samcli.commands.remote.execution.get.cli.cli",
        "history": "samcli.commands.remote.execution.history.cli.cli",
        "stop": "samcli.commands.remote.execution.stop.cli.cli",
    },
)
def cli():
    """
    Manage durable function executions
    """
