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

    # serverless_rules 옵션이 사용되면 경고 표시 및 extra_lint_rules로 변환
    if serverless_rules and not extra_lint_rules:
        click.secho(
            "Warning: --serverless-rules is deprecated. Please use --extra-lint-rules=\"cfn_lint_serverless.rules\" instead.",
            fg="yellow"
        )
        # 이전 옵션을 새 옵션으로 변환
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

    # 디버그 정보 추가
    print(f"디버그 정보: serverless_rules 옵션 값 = {serverless_rules}")

    cfn_lint_logger = logging.getLogger(CNT_LINT_LOGGER_NAME)
    cfn_lint_logger.propagate = False

    EventTracker.track_event("UsedFeature", "CFNLint")

    linter_config = {}
    if ctx.region:
        linter_config["regions"] = [ctx.region]
    if ctx.debug:
        cfn_lint_logger.propagate = True
        cfn_lint_logger.setLevel(logging.DEBUG)

    print(f"디버그 정보: linter_config 초기값 = {linter_config}")

    # 두 옵션을 함께 처리하기 위한 변수 초기화
    rules_to_append = []
    
    # 이전 serverless_rules 옵션 지원 (deprecated)
    if serverless_rules:
        print("디버그 정보: serverless_rules 옵션이 활성화되었습니다.")
        # Track usage of Serverless Rules
        EventTracker.track_event("UsedFeature", "ServerlessRules")
        
        # Check if cfn-lint-serverless is installed
        import importlib.util
        serverless_spec = importlib.util.find_spec("cfn_lint_serverless")
        print(f"디버그 정보: cfn_lint_serverless 패키지 설치 여부 = {serverless_spec is not None}")
        
        if serverless_spec is None:
            print("디버그 정보: cfn_lint_serverless 패키지가 설치되어 있지 않습니다.")
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
            print("디버그 정보: cfn_lint_serverless 패키지 임포트 성공")
            
            # Serverless Rules를 규칙 목록에 추가
            rules_to_append.append("cfn_lint_serverless.rules")
            click.secho("Serverless Rules enabled for linting", fg="green")
        except ImportError as e:
            print(f"디버그 정보: cfn_lint_serverless 임포트 오류 = {e}")
            click.secho(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless",
                fg="red",
            )
            raise UserException(
                "Serverless Rules package (cfn-lint-serverless) is not installed. "
                "Please install it using: pip install cfn-lint-serverless"
            )
    
    # 새로운 extra_lint_rules 옵션 지원
    if extra_lint_rules:
        print(f"디버그 정보: extra_lint_rules 옵션이 활성화되었습니다. 값: {extra_lint_rules}")
        # Track usage of Extra Lint Rules
        EventTracker.track_event("UsedFeature", "ExtraLintRules")
        
        # 콤마로 구분된 여러 규칙 모듈을 파싱
        modules = [module.strip() for module in extra_lint_rules.split(',') if module.strip()]
        print(f"디버그 정보: 파싱된 규칙 모듈 목록 = {modules}")
        
        # 각 모듈을 규칙 목록에 추가
        rules_to_append.extend(modules)
        click.secho(f"Extra lint rules enabled: {extra_lint_rules}", fg="green")
    
    # 규칙이 있으면 linter_config에 추가
    if rules_to_append:
        print(f"디버그 정보: 추가할 규칙 목록 = {rules_to_append}")
        linter_config["append_rules"] = rules_to_append
        print(f"디버그 정보: linter_config 업데이트 = {linter_config}")

    config = ManualArgs(**linter_config)
    print(f"디버그 정보: config 생성 완료")

    try:
        print(f"디버그 정보: lint 함수 호출 시작")
        matches = lint(template, config=config)
        print(f"디버그 정보: lint 함수 호출 완료, matches = {matches}")
    except InvalidRegionException as ex:
        print(f"디버그 정보: InvalidRegionException 발생 = {ex}")
        raise UserException(
            f"AWS Region was not found. Please configure your region through the --region option.\n{ex}",
            wrapped_from=ex.__class__.__name__,
        ) from ex
    except Exception as e:
        print(f"디버그 정보: 예외 발생 = {e}")
        raise

    if not matches:
        print(f"디버그 정보: 템플릿 검증 성공")
        click.secho("{} is a valid SAM Template".format(template_path), fg="green")
        return

    print(f"디버그 정보: 템플릿 검증 실패, matches = {matches}")
    click.secho(matches)

    raise LinterRuleMatchedException("Linting failed. At least one linting rule was matched to the provided template.")
