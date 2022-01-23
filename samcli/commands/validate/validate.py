"""
CLI Command for Validating a SAM Template
"""
import os

import boto3
from botocore.exceptions import NoCredentialsError
import click

from samtranslator.translator.arn_generator import NoRegionFound

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.options import template_option_without_build
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version


@click.command("validate", short_help="Validate an AWS SAM template.")
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@aws_creds_options
@cli_framework_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk doctor")
def cli(
    ctx,
    template_file,
    config_file,
    config_env,
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template_file)  # pragma: no cover


def do_cli(ctx, template):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader

    from samcli.commands.exceptions import UserException
    from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
    from .lib.exceptions import InvalidSamDocumentException
    from .lib.sam_template_validator import SamTemplateValidator

    sam_template = _read_sam_file(template)

    iam_client = boto3.client("iam")
    validator = SamTemplateValidator(
        sam_template, ManagedPolicyLoader(iam_client), profile=ctx.profile, region=ctx.region
    )

    try:
        validator.is_valid()
    except InvalidSamDocumentException as e:
        click.secho("Template provided at '{}' was invalid SAM Template.".format(template), bg="red")
        raise InvalidSamTemplateException(str(e)) from e
    except NoRegionFound as no_region_found_e:
        raise UserException(
            "AWS Region was not found. Please configure your region through a profile or --region option",
            wrapped_from=no_region_found_e.__class__.__name__,
        ) from no_region_found_e
    except NoCredentialsError as e:
        raise UserException(
            "AWS Credentials are required. Please configure your credentials.", wrapped_from=e.__class__.__name__
        ) from e

    click.secho("{} is a valid SAM Template".format(template), fg="green")


def _read_sam_file(template):
    """
    Reads the file (json and yaml supported) provided and returns the dictionary representation of the file.

    :param str template: Path to the template file
    :return dict: Dictionary representing the SAM Template
    :raises: SamTemplateNotFoundException when the template file does not exist
    """

    from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
    from samcli.yamlhelper import yaml_parse

    if not os.path.exists(template):
        click.secho("SAM Template Not Found", bg="red")
        raise SamTemplateNotFoundException("Template at {} is not found".format(template))

    with click.open_file(template, "r", encoding="utf-8") as sam_template:
        sam_template = yaml_parse(sam_template.read())

    return sam_template
