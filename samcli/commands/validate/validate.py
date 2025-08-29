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
    "--extra-lint-rules",
    help="Specify additional lint rules to be used with cfn-lint. "
         "Format: module.path (e.g. 'cfn_lint_serverless.rules'). "
         "Multiple rule modules can be specified by separating with commas or using this option multiple times.",
    default=None,
    multiple=True
)
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk doctor")
@command_exception_handler
def cli(ctx, template_file, config_file, config_env, lint, save_params, extra_lint_rules):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(ctx, template_file, lint, extra_lint_rules)  # pragma: no cover


def do_cli(ctx, template, lint, extra_lint_rules=None):
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
        _lint(ctx, sam_template.serialized, template, extra_lint_rules)
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


def _lint(ctx: Context, template: str, template_path: str, extra_lint_rules=None):
    """
    Parses provided SAM template and maps errors from CloudFormation template back to SAM template.

    Cfn-lint loggers are added to the SAM cli logging hierarchy which at the root logger
    formatter and handlers are defined. This ensures that logging is output correctly when used from SAM cli
    for CLI consumers.

    Parameters
    ----------
    ctx
        Click Context
    template
        SAM template contents
    template_path
        Path to the sam template
    extra_lint_rules
        List of additional rule modules to apply
    """
    import logging
    import importlib.util
    import cfnlint

    from cfnlint.api import lint, ManualArgs
    from cfnlint.runner import InvalidRegionException
    # Import only what is necessary

    # To track events, we need to enable telemetry
    from samcli.lib.telemetry.event import EventTracker

    LOG = logging.getLogger(__name__)
    LOG.debug("Starting template validation with linting")

    # Set up cfnlint logger verbosity using context provided
    cfnlint_logger = logging.getLogger(CNT_LINT_LOGGER_NAME)
    cfnlint_logger.propagate = False
    
    if ctx and ctx.debug:
        cfnlint_logger.propagate = True
        cfnlint_logger.setLevel(logging.DEBUG)
    else:
        cfnlint_logger.setLevel(logging.INFO)

    # Track linting in telemetry
    EventTracker.track_event("UsedFeature", "CFNLint")
    
    # Create linter configuration
    linter_config = {}
    if ctx.region:
        linter_config["regions"] = [ctx.region]
    
    # Process extra lint rules if provided
    rules_to_append = []
    if extra_lint_rules:
        # Track usage of Extra Lint Rules
        EventTracker.track_event("UsedFeature", "ExtraLintRules")
        
        # Process each rule option (multiple=True gives us a list)
        for rule_option in extra_lint_rules:
            # Handle comma-separated rule modules
            for module in rule_option.split(','):
                module = module.strip()
                if not module:
                    continue
                    
                LOG.debug("Processing lint rule module: %s", module)
                if _is_module_available(module):
                    rules_to_append.append(module)
                    LOG.debug("Module %s is available and will be used", module)
                else:
                    module_name = module.split('.')[0].replace('_', '-')
                    _handle_missing_module(module_name, 
                                        f"The rule module '{module}' was specified but is not available.",
                                        ctx.debug)
        
        if rules_to_append:
            module_names = ', '.join(rules_to_append)
            click.secho(f"Extra lint rules enabled: {module_names}", fg="green")
            linter_config["append_rules"] = rules_to_append
            LOG.debug("Linter configuration updated with rules: %s", rules_to_append)

    try:
        # Create linter configuration and execute linting
        config = ManualArgs(**linter_config)
        LOG.debug("Executing linting with configuration")
        matches = lint(template, config=config)
        
        if not matches:
            click.secho("{} is a valid SAM Template".format(template_path), fg="green")
            return

        # Display validation failures
        click.secho(matches)
        raise LinterRuleMatchedException("Linting failed. At least one linting rule was matched to the provided template.")
        
    except InvalidRegionException as ex:
        LOG.debug("Region validation failed: %s", ex)
        raise UserException(
            f"AWS Region was not found. Please configure your region through the --region option.\n{ex}",
            wrapped_from=ex.__class__.__name__,
        ) from ex
    except Exception as e:
        LOG.debug("Unexpected exception during linting: %s", e)
        raise


def _is_module_available(module_path: str) -> bool:
    """
    Check if a module is available for import.
    Works with both standard pip installations and installer-based SAM CLI.
    
    Parameters
    ----------
    module_path
        Full module path (e.g. 'cfn_lint_serverless.rules')
        
    Returns
    -------
    bool
        True if module can be imported, False otherwise
    """
    LOG = logging.getLogger(__name__)
    
    # Try using importlib.util which is safer
    try:
        root_module = module_path.split('.')[0]
        spec = importlib.util.find_spec(root_module)
        if spec is None:
            LOG.debug("Module %s not found with importlib.util.find_spec", root_module)
            return False
            
        # For deeper paths, try actually importing
        try:
            __import__(module_path)
            return True
        except (ImportError, ModuleNotFoundError) as e:
            LOG.debug("Could not import module %s: %s", module_path, e)
            return False
    except Exception as e:
        LOG.debug("Unexpected error checking for module %s: %s", module_path, e)
        # Fallback to direct import attempt
        try:
            __import__(module_path)
            return True
        except (ImportError, ModuleNotFoundError):
            return False


def _handle_missing_module(package_name: str, error_context: str, debug_mode: bool = False):
    """
    Handle missing module by providing appropriate error message that works
    in both pip and installer environments.
    
    Parameters
    ----------
    package_name
        Name of the package (for pip install instructions)
    error_context
        Contextual message describing what feature requires this package
    debug_mode
        Whether to include detailed instructions for different install methods
    
    Raises
    ------
    UserException
        With appropriate error message
    """
    LOG = logging.getLogger(__name__)
    LOG.debug("Module %s is missing: %s", package_name, error_context)
    
    base_message = error_context
    install_instruction = f"Please install it using: pip install {package_name}"
    
    if debug_mode:
        # In debug mode, provide more comprehensive instructions
        message = (
            f"{base_message}\n\n"
            f"The package '{package_name}' is not available. Installation options:\n"
            f"1. If using pip-installed SAM CLI: {install_instruction}\n"
            f"2. If using installer-based SAM CLI: You need to install the package in the same Python environment\n"
            f"   that SAM CLI uses. Check the SAM CLI installation documentation for details."
        )
    else:
        message = f"{base_message}\n\n{package_name} package is not installed. {install_instruction}"
    
    click.secho(message, fg="red")
    raise UserException(message)
