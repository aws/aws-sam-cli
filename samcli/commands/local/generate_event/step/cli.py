"""
Generates a Step Function Event for Lambda Invocation
"""
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_step_event


@click.command("step", short_help="Generates a sample Amazon Step Function event")
@click.option("--key", "-k",
              type=str,
              default="hello",
              help='The key of the message to emit to Lambda.')
@click.option("--value", "-v",
              type=str,
              default="world",
              help='The value of the message to emit to Lambda.')
@click.option("--filepath", "-f",
              type=str,
              default="",
              help='Path to a JSON file containing a message to emit to Lambda. \
              NOTE: If used, overrides the key and value parameters.',)
@cli_framework_options
@pass_context
def cli(ctx, key, value, filepath):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, key, value, filepath)  # pragma: no cover


def do_cli(ctx, key, value, filepath):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    if not filepath:
        event_dict = generate_step_event(key, value)
    else:
        with open(filepath, 'r') as data_file:
            data = data_file.read()
            event_dict = json.loads(data)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
