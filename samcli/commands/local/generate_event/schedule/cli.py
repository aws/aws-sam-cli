"""
Generates a Schedule Event for a Lambda Invoke
"""
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_schedule_event


@click.command("schedule", short_help="Generates a sample scheduled event")
@click.option("--region", "-r",
              type=str,
              default="us-east-1",
              help='The region the event should come from (default: "us-east-1")')
@cli_framework_options
@pass_context
def cli(ctx, region):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, region)  # pragma: no cover


def do_cli(ctx, region):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    event_dict = generate_schedule_event(region)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
