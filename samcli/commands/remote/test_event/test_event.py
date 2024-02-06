"""Command group for "test-event" suite of commands."""

import click

from samcli.commands.remote.test_event.delete.cli import cli as delete_cli
from samcli.commands.remote.test_event.get.cli import cli as get_cli
from samcli.commands.remote.test_event.list.cli import cli as list_cli
from samcli.commands.remote.test_event.put.cli import cli as put_cli


@click.group("test-event")
def cli():
    """
    Manage remote test events
    """


cli.add_command(delete_cli)
cli.add_command(get_cli)
cli.add_command(put_cli)
cli.add_command(list_cli)
