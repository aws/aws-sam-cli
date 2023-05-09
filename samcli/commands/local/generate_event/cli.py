"""
Sets up the cli for generate-event
"""

import click

from samcli.cli.main import pass_context
from samcli.commands.local.generate_event.core.command import CoreGenerateEventCommand

DESCRIPTION = """
  Generate sample payloads from different event sources
  such as S3, API Gateway, SNS etc. to be sent to Lambda functions.
"""


@click.command(
    "generate-event",
    cls=CoreGenerateEventCommand,
    help="Generate events for Lambda functions.",
    short_help="Generate events for Lambda functions.",
    description=DESCRIPTION,
    requires_credentials=False,
    context_settings={"max_content_width": 120},
)
@pass_context
def cli(self):
    """
    Generate an event for one of the services listed below:
    """
