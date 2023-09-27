"""
Command group for "remote" suite for commands. It provides common CLI arguments for interacting with
cloud resources such as Lambda Function.
"""

import click

from samcli.commands.remote.invoke.cli import cli as invoke_cli
from samcli.commands.remote.test_event.test_event import cli as event_cli


@click.group()
def cli():
    """
    Interact with your Serverless application in the cloud for quick development & testing
    """


# Add individual commands under this group
cli.add_command(invoke_cli)
cli.add_command(event_cli)
