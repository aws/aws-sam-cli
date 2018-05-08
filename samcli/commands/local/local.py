"""
Command group for "local" suite for commands. It provides common CLI arguments, template parsing capabilities,
setting up stdin/stdout etc
"""

import click

from .invoke.cli import cli as invoke_cli
from .start_api.cli import cli as start_api_cli
from .generate_event.cli import cli as generate_event_cli


@click.group()
def cli():
    """
    Run your Serverless application locally for quick development & testing
    """
    pass  # pragma: no cover


# Add individual commands under this group
cli.add_command(invoke_cli)
cli.add_command(start_api_cli)
cli.add_command(generate_event_cli)
