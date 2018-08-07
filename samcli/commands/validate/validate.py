"""
CLI Command for Validating a SAM Template
"""
import os

import boto3
from botocore.exceptions import NoCredentialsError
import click
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader

from samcli.commands.exceptions import UserException
from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options
from samcli.commands.local.cli_common.options import template_common_option as template_option
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException, SamTemplateNotFoundException
from samcli.yamlhelper import yaml_parse
from .lib.exceptions import InvalidSamDocumentException
from .lib.sam_template_validator import SamTemplateValidator


@click.command("validate",
               short_help="Validate an AWS SAM template.")
@template_option
@aws_creds_options
@cli_framework_options
@pass_context
def cli(ctx, template):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template)  # pragma: no cover


def do_cli(ctx, template):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """

    sam_template = _read_sam_file(template)

    iam_client = boto3.client('iam')
    validator = SamTemplateValidator(sam_template, ManagedPolicyLoader(iam_client))

    try:
        validator.is_valid()
    except InvalidSamDocumentException as e:
        click.secho("Template provided at '{}' was invalid SAM Template.".format(template), bg='red')
        raise InvalidSamTemplateException(str(e))
    except NoCredentialsError as e:
        raise UserException("AWS Credentials are required. Please configure your credentials.")

    click.secho("{} is a valid SAM Template".format(template), fg='green')


def _read_sam_file(template):
    """
    Reads the file (json and yaml supported) provided and returns the dictionary representation of the file.

    :param str template: Path to the template file
    :return dict: Dictionary representing the SAM Template
    :raises: SamTemplateNotFoundException when the template file does not exist
    """
    if not os.path.exists(template):
        click.secho("SAM Template Not Found", bg='red')
        raise SamTemplateNotFoundException("Template at {} is not found".format(template))

    with click.open_file(template, 'r') as sam_template:
        sam_template = yaml_parse(sam_template.read())

    return sam_template
