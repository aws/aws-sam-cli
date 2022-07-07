"""
CLI Command for Validating a SAM Template
"""
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
from samcli.commands.translate.translate_utils import read_sam_file


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
    from samcli.lib.translate.exceptions import InvalidSamDocumentException
    from samcli.lib.translate.sam_template_validator import SamTemplateValidator

    sam_template = read_sam_file(template)

    iam_client = boto3.client("iam")
    validator = SamTemplateValidator(
        sam_template, ManagedPolicyLoader(iam_client), profile=ctx.profile, region=ctx.region
    )

    try:
        validator.get_translated_template_if_valid()
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
