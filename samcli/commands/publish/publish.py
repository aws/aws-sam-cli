"""Command group for "publish" suite of commands."""

import click

from .app.cli import cli as app_cli


@click.group()
def cli():
    """Publish your Serverless application to the targeted repository."""
    pass  # pragma: no cover


# Add individual commands under this group
cli.add_command(app_cli)
