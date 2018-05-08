"""
Generates a Kinesis Event for a Lambda Invoke
"""
import base64
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_kinesis_event


@click.command("kinesis", short_help="Generates a sample Amazon Kinesis event")
@click.option("--region", "-r",
              type=str,
              default="us-east-1",
              help='The region the event should come from (default: "us-east-1")')
@click.option("--partition", "-p",
              type=str,
              default="partitionKey-03",
              help='The Kinesis partition key (default: "partitionKey-03")')
@click.option("--sequence", "-s",
              type=str,
              default="49545115243490985018280067714973144582180062593244200961",
              help='The Kinesis sequence number (default: "49545115243490985018280067714973144582180062593244200961")')
@click.option("--data", "-d",
              type=str,
              default="Hello, this is a test 123.",
              help='The Kinesis message payload. There is no need to base64 this - sam will do this for you '
                   '(default: "Hello, this is a test 123.")')
@cli_framework_options
@pass_context
def cli(ctx, region, partition, sequence, data):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, region, partition, sequence, data)  # pragma: no cover


def do_cli(ctx, region, partition, sequence, data):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    # base64 encode the data
    date_base64 = base64.urlsafe_b64encode(data.encode('utf8'))
    event_dict = generate_kinesis_event(region, partition, sequence, date_base64)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
