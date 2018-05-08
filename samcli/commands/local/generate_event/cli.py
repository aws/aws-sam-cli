"""
Command group for "generate-event" suite for commands.
"""

import click

from .s3.cli import cli as s3_cli
from .api.cli import cli as api_cli
from .dynamodb.cli import cli as dynamodb_cli
from .kinesis.cli import cli as kinesis_cli
from .schedule.cli import cli as schedule_cli
from .sns.cli import cli as sns_cli


HELP_TEXT = """
Generate a Lambda Event that can be used to invoke a Lambda Function.

Useful for developing serverless functions that handle asynchronous events (such as S3/Kinesis etc), or if you want to
compose a script of test cases. Event body can be passed in either by stdin (default), or by using the --event
parameter. Runtime output (logs etc) will be outputted to stderr, and the Lambda function result will be outputted to
stdout.
"""


@click.group("generate-event")
def cli():
    """
    Generate an event
    """
    pass  # pragma: no cover


# Add individual commands under this group
cli.add_command(s3_cli)
cli.add_command(api_cli)
cli.add_command(dynamodb_cli)
cli.add_command(kinesis_cli)
cli.add_command(schedule_cli)
cli.add_command(sns_cli)
