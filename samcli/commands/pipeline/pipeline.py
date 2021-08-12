"""
Command group for "pipeline" suite commands. It provides common CLI arguments, template parsing capabilities,
setting up stdin/stdout etc
"""

import click

from .bootstrap.cli import cli as bootstrap_cli
from .init.cli import cli as init_cli


@click.group()
def cli() -> None:
    """
    Manage the continuous delivery of the application
    """


# Add individual commands under this group
cli.add_command(bootstrap_cli)
cli.add_command(init_cli)
