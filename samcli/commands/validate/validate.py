"""
CLI Command for Validating a SAM Template
"""

import logging
import os
from dataclasses import dataclass

import boto3
import click
from botocore.exceptions import NoCredentialsError
from samtranslator.translator.arn_generator import NoRegionFound

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.context import Context
from samcli.cli.main import aws_creds_options, pass_context, print_cmdline_args
from samcli.cli.main import common_options as cli_framework_options
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands._utils.options import template_option_without_build
from samcli.commands.exceptions import LinterRuleMatchedException, UserException
from samcli.commands.validate.core.command import ValidateCommand
from samcli.lib.telemetry.event import EventTracker
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

DESCRIPTION = """
  Verify and Lint an AWS SAM Template being valid.
"""

CNT_LINT_LOGGER_NAME = "cfnlint"


@dataclass
class SamTemplate:
    serialized: str
    deserialized: dict


@click.command(
    "validate",
    cls=ValidateCommand,
    help="Validate an AWS SAM Template.",
    short_help="Validate an AWS SAM Template.",
    description=DESCRIPTION,
    requires_credentials=False,
    context_settings={"max_content_width": 120},
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@template_option_without_build
@aws_creds_options
@cli_framework_options
@click.option(
    "--lint",
    is_flag=True,
    help="Run linting validation on template through cfn-lint. "
    "Create a cfnlintrc config file to specify additional parameters. "
    "For more information, see: https://github.com/aws-cloudformation/cfn-lint",
)
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk doctor")
@command_exception_handler
def cli(ctx, template_file, config_file, config_env, lint, save_params):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(ctx, template_file, lint)  # pragma: no cover


def do_cli(ctx, template, lint):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader

    from samcli.commands.exceptions import UserException
    from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
    from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
    from samcli.lib.translate.sam_template_validator import SamTemplateValidator

    sam_template = _read_sam_file(template)

    if lint:
        _lint(ctx, sam_template.serialized, template)
    else:
        iam_client = boto3.client("iam")
        validator = SamTemplateValidator(
            sam_template.deserialized, ManagedPolicyLoader(iam_client), profile=ctx.profile, region=ctx.region
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

        click.secho(
            "{} is a valid SAM Template. This is according to basic SAM Validation, "
            'for additional validation, please run with "--lint" option'.format(template),
            fg="green",
        )


def _read_sam_file(template) -> SamTemplate:
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

    with click.open_file(template, "r", encoding="utf-8") as sam_file:
        template_string = sam_file.read()
        sam_template = yaml_parse(template_string)

    return SamTemplate(serialized=template_string, deserialized=sam_template)


def _lint(ctx: Context, template: str, template_path: str) -> None:
    """
    Parses provided SAM template and maps errors from CloudFormation template back to SAM template.

    Cfn-lint loggers are added to the SAM cli logging hierarchy which at the root logger
    configures with INFO level logging and a different formatting. This exposes and duplicates
    some cfn-lint logs that are not typically shown to customers. Explicitly setting the level to
    WARNING and propagate to be False remediates these issues.

    Parameters
    -----------
    ctx
        Click context object
    template
        Contents of sam template as a string
    template_path
        Path to the sam template
    """

    from cfnlint.api import ManualArgs, lint
    from cfnlint.runner import InvalidRegionException

    cfn_lint_logger = logging.getLogger(CNT_LINT_LOGGER_NAME)
    cfn_lint_logger.propagate = False

    EventTracker.track_event("UsedFeature", "CFNLint")

    linter_config = {}
    if ctx.region:
        linter_config["regions"] = [ctx.region]
    if ctx.debug:
        cfn_lint_logger.propagate = True
        cfn_lint_logger.setLevel(logging.DEBUG)

    config = ManualArgs(**linter_config)

    try:
        matches = lint(template, config=config)
    except InvalidRegionException as ex:
        raise UserException(
            f"AWS Region was not found. Please configure your region through the --region option.\n{ex}",
            wrapped_from=ex.__class__.__name__,
        ) from ex

    if not matches:
        click.secho("{} is a valid SAM Template".format(template_path), fg="green")
        return

    click.secho(matches)

    raise LinterRuleMatchedException("Linting failed. At least one linting rule was matched to the provided template.")
