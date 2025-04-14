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
@click.option(
    "--serverless-rules",
    is_flag=True,
    help="[DEPRECATED] Enable Serverless Rules for linting validation. "
    "Requires the cfn-lint-serverless package to be installed. "
    "Use --extra-lint-rules=\"cfn_lint_serverless.rules\" instead. "
    "For more information, see: https://github.com/awslabs/serverless-rules",
)
@click.option(
    "--extra-lint-rules",
    help="Specify additional lint rules to be used with cfn-lint. "
         "Format: module.path (e.g. 'cfn_lint_serverless.rules')",
    default=None
)
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk doctor")
@command_exception_handler
def cli(ctx, template_file, config_file, config_env, lint, save_params, serverless_rules, extra_lint_rules):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    # Show warning and convert to extra_lint_rules if serverless_rules is used
    if serverless_rules and not extra_lint_rules:
        click.secho(
            "Warning: --serverless-rules is deprecated. Please use --extra-lint-rules=\"cfn_lint_serverless.rules\" instead.",
            fg="yellow"
        )
        # Convert old option to new option
        extra_lint_rules = "cfn_lint_serverless.rules"

    do_cli(ctx, template_file, lint, serverless_rules, extra_lint_rules)  # pragma: no cover


def do_cli(ctx, template, lint, serverless_rules, extra_lint_rules=None):
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
        _lint(ctx, sam_template.serialized, template, serverless_rules, extra_lint_rules)
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


def _lint(ctx: Context, template: str, template_path: str, serverless_rules: bool = False, extra_lint_rules: str = None) -> None:
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
    serverless_rules
        Flag to enable Serverless Rules for linting
    """

    from cfnlint.api import ManualArgs, lint
    from cfnlint.runner import InvalidRegionException
    from samcli.lib.telemetry.event import EventTracker

    # Add debug information
    print(f"Debug info: serverless_rules option value = {serverless_rules}")

    cfn_lint_logger = logging.getLogger(CNT_LINT_LOGGER_NAME)
    cfn_lint_logger.propagate = False

    EventTracker.track_event("UsedFeature", "CFNLint")

    linter_config = {}
    if ctx.region:
        linter_config["regions"] = [ctx.region]
    if ctx.debug:
        cfn_lint_logger.propagate = True
        cfn_lint_logger.setLevel(logging.DEBUG)

    print(f"Debug info: initial linter_config = {linter_config}")

    # Initialize variable to handle both options together
    rules_to_append = []
    
    # Support for previous serverless_rules option (deprecated)
    if serverless_rules:
        print("Debug info: serverless_rules option is activated.")
        # Track usage of Serverless Rules
        EventTracker.track_event("UsedFeature", "ServerlessRules")
        
        # Check if cfn-lint-serverless is installed
        import importlib.util
        serverless_spec = importlib.util.find_spec("cfn_lint_serverless")
        print(f"Debug info: cfn_lint_serverless package installed = {serverless_spec is not None}")
        
        if serverless_spec is None:
            print("Debug info: cfn_lint_serverless package is not installed.")
            click.secho(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless",
                fg="red",
            )
            raise UserException(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless"
            )
            
        try:
            # Try to import the package
            import cfn_lint_serverless
            print("Debug info: cfn_lint_serverless package import successful")
            
            # Add Serverless Rules to the rule list
            rules_to_append.append("cfn_lint_serverless.rules")
            click.secho("Serverless Rules enabled for linting", fg="green")
        except ImportError as e:
            print(f"Debug info: cfn_lint_serverless import error = {e}")
            click.secho(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless",
                fg="red",
            )
            raise UserException(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless"
            )
    
    # Support for the new extra_lint_rules option
    if extra_lint_rules:
        print(f"Debug info: extra_lint_rules option is activated. Value: {extra_lint_rules}")
        # Track usage of Extra Lint Rules
        EventTracker.track_event("UsedFeature", "ExtraLintRules")
        
        # Parse comma-separated rule modules
        modules = [module.strip() for module in extra_lint_rules.split(',') if module.strip()]
        print(f"Debug info: parsed rule modules list = {modules}")
        
        # Add each module to the rule list
        rules_to_append.extend(modules)
        click.secho(f"Extra lint rules enabled: {extra_lint_rules}", fg="green")
    
    # Add rules to linter_config if any exist
    if rules_to_append:
        print(f"Debug info: rules to append = {rules_to_append}")
        linter_config["append_rules"] = rules_to_append
        print(f"Debug info: updated linter_config = {linter_config}")

    config = ManualArgs(**linter_config)
    print(f"Debug info: config creation completed")

    try:
        print(f"Debug info: starting lint function call")
        matches = lint(template, config=config)
        print(f"Debug info: lint function call completed, matches = {matches}")
    except InvalidRegionException as ex:
        print(f"Debug info: InvalidRegionException occurred = {ex}")
        raise UserException(
            f"AWS Region was not found. Please configure your region through the --region option.\n{ex}",
            wrapped_from=ex.__class__.__name__,
        ) from ex
    except Exception as e:
        print(f"Debug info: exception occurred = {e}")
        raise

    if not matches:
        print(f"Debug info: template validation successful")
        click.secho("{} is a valid SAM Template".format(template_path), fg="green")
        return

    print(f"Debug info: template validation failed, matches = {matches}")
    click.secho(matches)

    raise LinterRuleMatchedException("Linting failed. At least one linting rule was matched to the provided template.")
