"""CLI command for "publish" command."""

import json

import click
import boto3
from botocore.exceptions import ClientError
from serverlessrepo import publish_application
from serverlessrepo.publish import CREATE_APPLICATION
from serverlessrepo.exceptions import ServerlessRepoError

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands._utils.options import template_common_option
from samcli.commands._utils.template import get_template_data
from samcli.commands.exceptions import UserException

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
$ sam publish -t packaged.yaml --region <region>
"""
SHORT_HELP = "Publish a packaged AWS SAM template to the AWS Serverless Application Repository."
SERVERLESSREPO_CONSOLE_URL = "https://console.aws.amazon.com/serverlessrepo/home?region={}#/published-applications/{}"


@click.command("publish", help=HELP_TEXT, short_help=SHORT_HELP)
@template_common_option
@aws_creds_options
@cli_framework_options
@pass_context
def cli(ctx, template):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template)  # pragma: no cover


def do_cli(ctx, template):
    """Publish the application based on command line inputs."""
    try:
        template_data = get_template_data(template)
    except ValueError as ex:
        click.secho("Publish Failed", fg='red')
        raise UserException(str(ex))

    try:
        publish_output = publish_application(template_data)
        click.secho("Publish Succeeded", fg="green")
        click.secho(_gen_success_message(publish_output), fg="yellow")
    except ServerlessRepoError as ex:
        click.secho("Publish Failed", fg='red')
        raise UserException(str(ex))
    except ClientError as ex:
        click.secho("Publish Failed", fg='red')
        raise _wrap_s3_uri_exception(ex)

    application_id = publish_output.get('application_id')
    _print_console_link(ctx.region, application_id)


def _gen_success_message(publish_output):
    """
    Generate detailed success message for published applications.

    Parameters
    ----------
    publish_output : dict
        Output from serverlessrepo publish_application

    Returns
    -------
    str
        Detailed success message
    """
    application_id = publish_output.get('application_id')
    details = json.dumps(publish_output.get('details'), indent=2)

    if CREATE_APPLICATION in publish_output.get('actions'):
        return "Created new application with the following metadata:\n{}".format(details)

    return 'The following metadata of application "{}" has been updated:\n{}'.format(application_id, details)


def _print_console_link(region, application_id):
    """
    Print link for the application in AWS Serverless Application Repository console.

    Parameters
    ----------
    region : str
        AWS region name
    application_id : str
        The Amazon Resource Name (ARN) of the application

    """
    if not region:
        region = boto3.Session().region_name

    console_link = SERVERLESSREPO_CONSOLE_URL.format(region, application_id.replace('/', '~'))
    msg = "Click the link below to view your application in AWS console:\n{}".format(console_link)
    click.secho(msg, fg="yellow")


def _wrap_s3_uri_exception(ex):
    """
    Wrap invalid S3 URI exception with a better error message.

    Parameters
    ----------
    ex : ClientError
        boto3 exception

    Returns
    -------
    Exception
        UserException if found invalid S3 URI or ClientError
    """
    error_code = ex.response.get('Error').get('Code')
    message = ex.response.get('Error').get('Message')

    if error_code == 'BadRequestException' and "Invalid S3 URI" in message:
        return UserException(
            "Your SAM template contains invalid S3 URIs. Please make sure that you have uploaded application "
            "artifacts to S3 by packaging the template: 'sam package --template-file <file-path>'.")

    return ex
