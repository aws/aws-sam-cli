"""
Command group for "remote" suite for commands. It provides common CLI arguments for interacting with
cloud resources such as Lambda Function.
"""

import click

from samcli.cli.lazy_group import LazyGroup


@click.group(
    cls=LazyGroup,
    lazy_subcommands={
        "invoke": "samcli.commands.remote.invoke.cli.cli",
        "test-event": "samcli.commands.remote.test_event.test_event.cli",
        "execution": "samcli.commands.remote.execution.cli.cli",
        "callback": "samcli.commands.remote.callback.cli.cli",
    },
)
def cli():
    """
    Interact with your Serverless application in the cloud for quick development & testing
    """
