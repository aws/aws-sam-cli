"""
Command group for "test-runner" suite commands.
"""

import click

from .init.cli import cli as init_cli


@click.group()
def cli() -> None:
    """
    Run integration tests in the cloud.
    """


# Add individual commands under this group
cli.add_command(init_cli)
