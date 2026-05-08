"""Command group for "test-event" suite of commands."""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    "test-event",
    cls=LazyGroup,
    lazy_subcommands={
        "delete": "samcli.commands.remote.test_event.delete.cli.cli",
        "get": "samcli.commands.remote.test_event.get.cli.cli",
        "put": "samcli.commands.remote.test_event.put.cli.cli",
        "list": "samcli.commands.remote.test_event.list.cli.cli",
    },
)
def cli():
    """
    Manage remote test events
    """
