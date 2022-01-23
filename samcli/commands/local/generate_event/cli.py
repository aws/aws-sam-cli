"""
Sets up the cli for generate-event
"""

import click

from samcli.cli.main import pass_context
from samcli.commands.local.generate_event.event_generation import GenerateEventCommand

HELP_TEXT = """
You can use this command to generate sample payloads from different event sources
such as S3, API Gateway, and SNS. These payloads contain the information that the
event sources send to your Lambda functions.\n
\b
Generate the event that S3 sends to your Lambda function when a new object is uploaded
$ sam local generate-event s3 [put/delete]\n
\b
You can even customize the event by adding parameter flags. To find which flags apply to your command,
run:\n
$ sam local generate-event s3 [put/delete] --help\n
Then you can add in those flags that you wish to customize using\n
$ sam local generate-event s3 [put/delete] --bucket <bucket> --key <key>\n
\b
After you generate a sample event, you can use it to test your Lambda function locally
$ sam local generate-event s3 [put/delete] --bucket <bucket> --key <key> | sam local invoke -e - <function logical id>
"""


@click.command(name="generate-event", cls=GenerateEventCommand, help=HELP_TEXT)
@pass_context
def cli(self):
    """
    Generate an event for one of the services listed below:
    """
