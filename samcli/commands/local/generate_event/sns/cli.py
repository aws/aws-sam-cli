"""
Generates a SNS Event for a Lambda Invoke
"""
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_sns_event


@click.command("sns", short_help="Generates a sample Amazon SNS event")
@click.option("--message", "-m",
              type=str,
              default="example message",
              help='The SNS message body (default: "example message")')
@click.option("--topic", "-t",
              type=str,
              default="arn:aws:sns:us-east-1:111122223333:ExampleTopic",
              help='The SNS topic (default: "arn:aws:sns:us-east-1:111122223333:ExampleTopic")')
@click.option("--subject", "-s",
              type=str,
              default="example subject",
              help='The SNS subject (default: "example subject")')
@cli_framework_options
@pass_context
def cli(ctx, message, topic, subject):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, message, topic, subject)  # pragma: no cover


def do_cli(ctx, message, topic, subject):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    event_dict = generate_sns_event(message, topic, subject)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
