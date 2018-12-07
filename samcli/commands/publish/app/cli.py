"""CLI command for "publish app" command."""

import logging
import click

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_common_option

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Use this command to publish a packaged AWS SAM template to
the AWS Serverless Application Repository to share within your team,
across your organization, or with the community at large.\n
\b
This command expects the template's Metadata section to contain an
AWS::ServerlessRepo::Application section with application metadata
for publishing. For more details on this metadata section, see
https://docs.aws.amazon.com/serverlessrepo/latest/devguide/serverless-app-publishing-applications.html
\b
Examples
--------
To publish an application
$ sam publish app -t packaged.yaml --region <region>
"""
SHORT_HELP = "Publish a packaged AWS SAM template to the AWS Serverless Application Repository."


@click.command("app", help=HELP_TEXT, short_help=SHORT_HELP)
@template_common_option
@aws_creds_options
@cli_framework_options
@pass_context
def cli(ctx, template, account_ids):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template, account_ids)  # pragma: no cover


def do_cli(ctx, template, account_ids):
    click.echo('hello world')
