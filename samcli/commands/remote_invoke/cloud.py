"""
Command group for "cloud" suite for commands. It provides common CLI arguments, template parsing capabilities,
setting up stdin/stdout etc
"""

import click

from .invoke.cli import cli as invoke_cli


@click.group()
def cli():
    """
    Run your Serverless application on cloud for quick development & testing
    """


# Add individual commands under this group
cli.add_command(invoke_cli)
