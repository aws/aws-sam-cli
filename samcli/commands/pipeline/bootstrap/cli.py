"""
CLI command for "pipeline bootstrap", which sets up the require pipeline infrastructure resources
"""
import os
from typing import Any, Dict, List, Optional

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.context import get_cmd_names
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.pipeline.bootstrap.stage import Stage
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version
from .guided_context import GuidedContext

SHORT_HELP = "Sets up infrastructure resources for AWS SAM CI/CD pipelines."

HELP_TEXT = """Sets up the following infrastructure resources for AWS SAM CI/CD pipelines:
\n\t - Pipeline IAM user with access key ID and secret access key credentials to be shared with the CI/CD provider
\n\t - Pipeline execution IAM role assumed by the pipeline user to obtain access to the AWS account
\n\t - CloudFormation execution IAM role assumed by CloudFormation to deploy the AWS SAM application
\n\t - Artifacts S3 bucket to hold the AWS SAM build artifacts
\n\t - Optionally, an ECR repository to hold container image Lambda deployment packages
"""

PIPELINE_CONFIG_DIR = os.path.join(".aws-sam", "pipeline")
PIPELINE_CONFIG_FILENAME = "pipelineconfig.toml"


@click.command("bootstrap", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Disable interactive prompting for bootstrap parameters, and fail if any required arguments are missing.",
)
@click.option(
    "--stage-name",
    help="The name of the corresponding pipeline stage. It is used as a suffix for the created resources.",
    required=False,
)
@click.option(
    "--pipeline-user",
    help="The ARN of the IAM user having its access key ID and secret access key shared with the CI/CD provider. "
    "It is used to grant this IAM user the permissions to access the corresponding AWS account. "
    "If not provided, the command will create one along with access key ID and secret access key credentials.",
    required=False,
)
@click.option(
    "--pipeline-execution-role",
    help="The ARN of an IAM role to be assumed by the pipeline user to operate on this stage. "
    "Provide it only if you want to user your own role, otherwise, the command will create one",
    required=False,
)
@click.option(
    "--cloudformation-execution-role",
    help="The ARN of an IAM role to be assumed by the CloudFormation service while deploying the application's stack. "
    "Provide it only if you want to user your own role, otherwise, the command will create one.",
    required=False,
)
@click.option(
    "--artifacts-bucket",
    help="The ARN of an S3 bucket to hold the AWS SAM build artifacts. "
    "Provide it only if you want to user your own S3 bucket, otherwise, the command will create one.",
    required=False,
)
@click.option(
    "--create-ecr-repo/--no-create-ecr-repo",
    is_flag=True,
    default=False,
    help="If set to true and no ECR repository is provided, this command will create an ECR repository to hold the"
    " container images of Lambda functions having an Image package type.",
)
@click.option(
    "--ecr-repo",
    help="The ARN of an ECR repository to hold the containers images of Lambda functions of Image package type. "
    "If provided, the --create-ecr-repo argument is ignored. If not provided and --create-ecr-repo is set to true, "
    "the command will create one.",
    required=False,
)
@click.option(
    "--pipeline-ip-range",
    help="If provided, all requests coming from outside of the given range are denied. Example: 10.24.34.0/24",
    required=False,
)
@click.option(
    "--confirm-changeset/--no-confirm-changeset",
    default=True,
    is_flag=True,
    help="Prompt to confirm if the resources is to be deployed by SAM CLI.",
)
@common_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx: Any,
    interactive: bool,
    stage_name: Optional[str],
    pipeline_user: Optional[str],
    pipeline_execution_role: Optional[str],
    cloudformation_execution_role: Optional[str],
    artifacts_bucket: Optional[str],
    create_ecr_repo: bool,
    ecr_repo: Optional[str],
    pipeline_ip_range: Optional[str],
    confirm_changeset: bool,
    config_file: Optional[str],
    config_env: Optional[str],
) -> None:
    """
    `sam pipeline bootstrap` command entry point
    """
    do_cli(
        region=ctx.region,
        profile=ctx.profile,
        interactive=interactive,
        stage_name=stage_name,
        pipeline_user_arn=pipeline_user,
        pipeline_execution_role_arn=pipeline_execution_role,
        cloudformation_execution_role_arn=cloudformation_execution_role,
        artifacts_bucket_arn=artifacts_bucket,
        create_ecr_repo=create_ecr_repo,
        ecr_repo_arn=ecr_repo,
        pipeline_ip_range=pipeline_ip_range,
        confirm_changeset=confirm_changeset,
        config_file=config_env,
        config_env=config_file,
    )  # pragma: no cover


def do_cli(
    region: Optional[str],
    profile: Optional[str],
    interactive: bool,
    stage_name: Optional[str],
    pipeline_user_arn: Optional[str],
    pipeline_execution_role_arn: Optional[str],
    cloudformation_execution_role_arn: Optional[str],
    artifacts_bucket_arn: Optional[str],
    create_ecr_repo: bool,
    ecr_repo_arn: Optional[str],
    pipeline_ip_range: Optional[str],
    confirm_changeset: bool,
    config_file: Optional[str],
    config_env: Optional[str],
) -> None:
    """
    implementation of `sam pipeline bootstrap` command
    """
    if not pipeline_user_arn:
        pipeline_user_arn = _load_saved_pipeline_user_arn()

    if interactive:
        guided_context = GuidedContext(
            stage_name=stage_name,
            pipeline_user_arn=pipeline_user_arn,
            pipeline_execution_role_arn=pipeline_execution_role_arn,
            cloudformation_execution_role_arn=cloudformation_execution_role_arn,
            artifacts_bucket_arn=artifacts_bucket_arn,
            create_ecr_repo=create_ecr_repo,
            ecr_repo_arn=ecr_repo_arn,
            pipeline_ip_range=pipeline_ip_range,
        )
        guided_context.run()
        stage_name = guided_context.stage_name
        pipeline_user_arn = guided_context.pipeline_user_arn
        pipeline_execution_role_arn = guided_context.pipeline_execution_role_arn
        pipeline_ip_range = guided_context.pipeline_ip_range
        cloudformation_execution_role_arn = guided_context.cloudformation_execution_role_arn
        artifacts_bucket_arn = guided_context.artifacts_bucket_arn
        create_ecr_repo = guided_context.create_ecr_repo
        ecr_repo_arn = guided_context.ecr_repo_arn

    if not stage_name:
        raise click.UsageError("Missing required parameter '--stage-name'")

    stage: Stage = Stage(
        name=stage_name,
        aws_profile=profile,
        aws_region=region,
        pipeline_user_arn=pipeline_user_arn,
        pipeline_execution_role_arn=pipeline_execution_role_arn,
        pipeline_ip_range=pipeline_ip_range,
        cloudformation_execution_role_arn=cloudformation_execution_role_arn,
        artifacts_bucket_arn=artifacts_bucket_arn,
        create_ecr_repo=create_ecr_repo,
        ecr_repo_arn=ecr_repo_arn,
    )

    bootstrapped: bool = stage.bootstrap(confirm_changeset=confirm_changeset)

    if bootstrapped:
        stage.print_resources_summary()

        stage.save_config_safe(
            config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME, cmd_names=_get_command_names()
        )


def _load_saved_pipeline_user_arn() -> Optional[str]:
    samconfig: SamConfig = SamConfig(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)
    if not samconfig.exists():
        return None
    config: Dict[str, str] = samconfig.get_all(cmd_names=_get_command_names(), section="parameters")
    return config.get("pipeline_user")


def _get_command_names() -> List[str]:
    ctx = click.get_current_context()
    return get_cmd_names(ctx.info_name, ctx)  # ["pipeline", "bootstrap"]
