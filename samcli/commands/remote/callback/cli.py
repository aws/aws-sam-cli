"""
CLI command group for "remote callback" commands
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    "callback",
    cls=LazyGroup,
    lazy_subcommands={
        "succeed": "samcli.commands.remote.callback.succeed.cli.cli",
        "fail": "samcli.commands.remote.callback.fail.cli.cli",
        "heartbeat": "samcli.commands.remote.callback.heartbeat.cli.cli",
    },
)
def cli():
    """
    Send callbacks to remote durable function executions
    """
