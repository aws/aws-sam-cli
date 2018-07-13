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
You can use this command to generate sample payloads from different event sources
such as S3, API Gateway, and SNS. These payloads contain the information that the
event sources send to your Lambda functions.\n
\b
Generate the event that S3 sends to your Lambda function when a new object is uploaded
$ sam local generate-event s3 --bucket <bucket> --key <key>\n
\b
After you generate a sample event, you can use it to test your Lambda function locally
$ sam local generate-event s3 --bucket <bucket> --key <key> | sam local invoke <function logical id>
"""


@click.group("generate-event", help=HELP_TEXT)
def cli():
    pass  # pragma: no cover


# Add individual commands under this group
cli.add_command(s3_cli)
cli.add_command(api_cli)
cli.add_command(dynamodb_cli)
cli.add_command(kinesis_cli)
cli.add_command(schedule_cli)
cli.add_command(sns_cli)
