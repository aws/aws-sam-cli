"""
CLI Command for Validating a SAM Template
"""
import os

import boto3
from botocore.exceptions import NoCredentialsError
import click
import cfnlint.core
import logging

from samtranslator.translator.arn_generator import NoRegionFound

from samcli.cli.main import pass_context, common_options as cli_framework_options, aws_creds_options, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.options import template_option_without_build
from samcli.lib.telemetry.metric import track_command
from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.lib.utils.version_checker import check_newer_version
from samcli.commands._utils.click_mutex import ClickMutex

LOGGER = logging.getLogger("cfnlint")

@click.command("validate", short_help="Validate an AWS SAM template.")
@configuration_option(provider=TomlProvider(section="parameters"))
@template_option_without_build
@aws_creds_options
@cli_framework_options
@click.option(
    "--lint",
    is_flag=True,
    is_eager=True,
    help="Run linting validation on template through cfn-lint. For more information, see: https://github.com/aws-cloudformation/cfn-lint",
    cls=ClickMutex,
    incompatible_params=["config-env", "config-file", "profile", "region"]
)
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
    lint
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template_file, lint)  # pragma: no cover


def do_cli(ctx, template, lint):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader

    from samcli.commands.exceptions import UserException
    from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
    from .lib.exceptions import InvalidSamDocumentException
    from .lib.sam_template_validator import SamTemplateValidator

    if lint:
        _lint(ctx, template)
    else:
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

        click.secho("{} can be transformed to a Cloudformation template. Please run \"sam validate --lint -t template.yaml\" for additional validation".format(template), fg="green")


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

def _lint(ctx, template):
    """
    Parses provided SAM template and maps errors from CloudFormation template back to SAM template.

    Parameters
    -----------
    ctx
        Click context object
    template
        Path to the template file

    """

    try:
        (args, filenames, formatter) = cfnlint.core.get_args_filenames([template, "--debug"]) if ctx.debug else cfnlint.core.get_args_filenames([template])
        LOGGER.setLevel(logging.WARNING)
        matches = list(cfnlint.core.get_matches(filenames, args))
        if not matches:
            click.secho("{} is a valid SAM Template".format(template), fg="green")
        rules = cfnlint.core.get_used_rules()
        matches_output = formatter.print_matches(matches, rules, filenames)

        if matches_output:
            if args.output_file:
                with open(args.output_file, 'w', encoding='utf-8') as output_file:
                    output_file.write(matches_output)
            else:
                print(matches_output)

        return cfnlint.core.get_exit_code(matches)
    except cfnlint.core.CfnLintExitException as e:
        LOGGER.error(str(e))
        return e.exit_code