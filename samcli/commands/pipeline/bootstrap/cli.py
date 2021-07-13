"""
CLI command for "pipeline bootstrap", which sets up the require pipeline infrastructure resources
"""
import os
from textwrap import dedent
from typing import Any, Dict, List, Optional

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.pipeline.bootstrap.environment import Environment
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.version_checker import check_newer_version
from .guided_context import GuidedContext

SHORT_HELP = "Generates the necessary AWS resources to connect your CI/CD system."

HELP_TEXT = """
SAM Pipeline Bootstrap generates the necessary AWS resources to connect your
CI/CD system. This step must be completed for each pipeline stage prior to
running sam pipeline init
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
    "--environment",
    help="The name of the corresponding environment. It is used as a suffix for the created resources.",
    required=False,
)
@click.option(
    "--pipeline-user",
    help="An IAM user generated or referenced by sam pipeline bootstrap in order to "
    "allow the connected CI/CD system to connect to the SAM CLI.",
    required=False,
)
@click.option(
    "--pipeline-execution-role",
    help="Execution role that the CI/CD system assumes in order to make changes to resources on your behalf.",
    required=False,
)
@click.option(
    "--cloudformation-execution-role",
    help="Execution role that CloudFormation assumes in order to make changes to resources on your behalf",
    required=False,
)
@click.option(
    "--bucket",
    help="The name of the S3 bucket where this command uploads your CloudFormation template. This is required for"
    "deployments of templates sized greater than 51,200 bytes.",
    required=False,
)
@click.option(
    "--create-image-repository/--no-create-image-repository",
    is_flag=True,
    default=False,
    help="If set to true and no ECR image repository is provided, this command will create an ECR image repository "
    "to hold the container images of Lambda functions having an Image package type.",
)
@click.option(
    "--image-repository",
    help="ECR repo uri where this command uploads the image artifacts that are referenced in your template.",
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
    environment: Optional[str],
    pipeline_user: Optional[str],
    pipeline_execution_role: Optional[str],
    cloudformation_execution_role: Optional[str],
    bucket: Optional[str],
    create_image_repository: bool,
    image_repository: Optional[str],
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
        environment_name=environment,
        pipeline_user_arn=pipeline_user,
        pipeline_execution_role_arn=pipeline_execution_role,
        cloudformation_execution_role_arn=cloudformation_execution_role,
        artifacts_bucket_arn=bucket,
        create_image_repository=create_image_repository,
        image_repository_arn=image_repository,
        confirm_changeset=confirm_changeset,
        config_file=config_env,
        config_env=config_file,
    )  # pragma: no cover


def do_cli(
    region: Optional[str],
    profile: Optional[str],
    interactive: bool,
    environment_name: Optional[str],
    pipeline_user_arn: Optional[str],
    pipeline_execution_role_arn: Optional[str],
    cloudformation_execution_role_arn: Optional[str],
    artifacts_bucket_arn: Optional[str],
    create_image_repository: bool,
    image_repository_arn: Optional[str],
    confirm_changeset: bool,
    config_file: Optional[str],
    config_env: Optional[str],
    standalone: bool = True,
) -> None:
    """
    implementation of `sam pipeline bootstrap` command
    """
    if not pipeline_user_arn:
        pipeline_user_arn = _load_saved_pipeline_user_arn()

    if interactive:
        if standalone:
            click.echo(
                dedent(
                    """\

                    sam pipeline bootstrap generates the necessary AWS resources to connect a stage in
                    your CI/CD system. We will ask for [1] stage definition, [2] account details, and
                    [3] references to existing resources in order to bootstrap these pipeline
                    resources. You can also add optional security parameters.
                    """
                ),
            )

        guided_context = GuidedContext(
            profile=profile,
            environment_name=environment_name,
            pipeline_user_arn=pipeline_user_arn,
            pipeline_execution_role_arn=pipeline_execution_role_arn,
            cloudformation_execution_role_arn=cloudformation_execution_role_arn,
            artifacts_bucket_arn=artifacts_bucket_arn,
            create_image_repository=create_image_repository,
            image_repository_arn=image_repository_arn,
            region=region,
        )
        guided_context.run()
        environment_name = guided_context.environment_name
        pipeline_user_arn = guided_context.pipeline_user_arn
        pipeline_execution_role_arn = guided_context.pipeline_execution_role_arn
        cloudformation_execution_role_arn = guided_context.cloudformation_execution_role_arn
        artifacts_bucket_arn = guided_context.artifacts_bucket_arn
        create_image_repository = guided_context.create_image_repository
        image_repository_arn = guided_context.image_repository_arn
        region = guided_context.region
        profile = guided_context.profile

    if not environment_name:
        raise click.UsageError("Missing required parameter '--environment'")

    environment: Environment = Environment(
        name=environment_name,
        aws_profile=profile,
        aws_region=region,
        pipeline_user_arn=pipeline_user_arn,
        pipeline_execution_role_arn=pipeline_execution_role_arn,
        cloudformation_execution_role_arn=cloudformation_execution_role_arn,
        artifacts_bucket_arn=artifacts_bucket_arn,
        create_image_repository=create_image_repository,
        image_repository_arn=image_repository_arn,
    )

    bootstrapped: bool = environment.bootstrap(confirm_changeset=confirm_changeset)

    if bootstrapped:
        environment.print_resources_summary()

        environment.save_config_safe(
            config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME, cmd_names=_get_bootstrap_command_names()
        )

        click.secho(
            dedent(
                f"""\
                View the definition in {os.path.join(PIPELINE_CONFIG_DIR, PIPELINE_CONFIG_FILENAME)},
                run sam pipeline bootstrap to generate another set of resources, or proceed to
                sam pipeline init to create your pipeline configuration file.
                """
            )
        )

        if not environment.pipeline_user.is_user_provided:
            click.secho(
                dedent(
                    f"""\
                    Before running {Colored().bold("sam pipeline init")}, we recommend first setting up AWS credentials
                    in your CI/CD account. Read more about how to do so with your provider in
                    [DOCS-LINK].
                    """
                )
            )


def _load_saved_pipeline_user_arn() -> Optional[str]:
    samconfig: SamConfig = SamConfig(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)
    if not samconfig.exists():
        return None
    config: Dict[str, str] = samconfig.get_all(cmd_names=_get_bootstrap_command_names(), section="parameters")
    return config.get("pipeline_user")


def _get_bootstrap_command_names() -> List[str]:
    return ["pipeline", "bootstrap"]
