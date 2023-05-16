"""
Command group for "list" suite for commands.
"""

import click

from samcli.commands.list.endpoints.command import cli as testable_resources_cli
from samcli.commands.list.resources.command import cli as resources_cli
from samcli.commands.list.stack_outputs.command import cli as stack_outputs_cli


@click.group()
def cli():
    """
    Get local and deployed state of serverless application.
    """


# Add individual commands under this group
cli.add_command(resources_cli)
cli.add_command(stack_outputs_cli)
cli.add_command(testable_resources_cli)
