"""
CLI command group for "local callback" commands
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    "callback",
    cls=LazyGroup,
    lazy_subcommands={
        "succeed": "samcli.commands.local.callback.succeed.cli.cli",
        "fail": "samcli.commands.local.callback.fail.cli.cli",
        "heartbeat": "samcli.commands.local.callback.heartbeat.cli.cli",
    },
)
def cli():
    """
    Send callbacks to durable function executions
    """
