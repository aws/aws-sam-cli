"""CLI command for "publish app" command."""

import os
import json
import logging
import click

from serverlessrepo import publish_application
from serverlessrepo.publish import CREATE_APPLICATION
from serverlessrepo.exceptions import ServerlessRepoError

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_common_option
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands.exceptions import UserException

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
def cli(ctx, template):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template)  # pragma: no cover


def do_cli(ctx, template):
    """Publish the application based on command line inputs."""
    if not os.path.exists(template):
        click.secho("Publish Failed", fg='red')
        raise SamTemplateNotFoundException("Template at {} is not found".format(template))

    with click.open_file(template, 'r') as template_file:
        try:
            output = publish_application(template_file.read())
            click.secho("Publish Succeeded", fg="green")
            click.secho(_gen_publish_message(output), fg="yellow")
        except ServerlessRepoError as ex:
            click.secho("Publish Failed", fg='red')
            raise UserException(str(ex))

        application_id = output['application_id']
        _print_console_link(ctx.region, application_id)


def _gen_publish_message(publish_output):
    application_id = publish_output['application_id']
    details = json.dumps(publish_output['details'], indent=2)

    if CREATE_APPLICATION in publish_output['actions']:
        return "Created new application with the following metadata:\n{}".format(details)

    return 'The following metadata of application "{}" has been updated:\n{}'.format(application_id, details)


def _print_console_link(region, application_id):
    url = "https://console.aws.amazon.com/serverlessrepo/home?region={}#/published-applications/{}"
    console_link = url.format(region, application_id.replace('/', '~'))
    msg = "Click the link below to view your application in AWS console:\n{}".format(console_link)
    click.secho(msg, fg="yellow")
