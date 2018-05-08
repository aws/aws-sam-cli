"""
Generates a S3 Event for a Lambda Invoke
"""
import json

import click

from samcli.cli.main import pass_context, common_options as cli_framework_options
from samcli.commands.local.lib.events import generate_s3_event


@click.command("s3", short_help="Generates a sample Amazon S3 event")
@click.option("--region", "-r",
              type=str,
              default="us-east-1",
              help='The region the event should come from (default: "us-east-1")')
@click.option("--bucket", "-b",
              type=str,
              default="example-bucket",
              help='The S3 bucket the event should reference (default: "example-bucket")')
@click.option("--key", "-k",
              type=str,
              default="test/key",
              help='The S3 key the event should reference (default: "test/key")')
@cli_framework_options
@pass_context
def cli(ctx, region, bucket, key):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, region, bucket, key)  # pragma: no cover


def do_cli(ctx, region, bucket, key):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    event_dict = generate_s3_event(region, bucket, key)
    event = json.dumps(event_dict, indent=4)
    click.echo(event)
