"""
CLI command for "pipeline bootstrap", which sets up the require pipeline infrastructure resources
"""
import os
from textwrap import dedent
from typing import Any, Dict, List, Optional

import logging
import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.commands.pipeline.bootstrap.pipeline_provider import GitHubOidcProvider, PipelineOidcProvider
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.pipeline.bootstrap.stage import (
    DEPLOYMENT_BRANCH,
    GITHUB_ORG,
    GITHUB_REPO,
    OIDC_CLIENT_ID,
    OIDC_PROVIDER,
    OIDC_PROVIDER_URL,
    Stage,
)
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.version_checker import check_newer_version
from .guided_context import GITHUB_ACTIONS, IAM, OPEN_ID_CONNECT, GuidedContext
from ..external_links import CONFIG_AWS_CRED_ON_CICD_URL

SHORT_HELP = "Generates the required AWS resources to connect your CI/CD system."

HELP_TEXT = """
This command generates the required AWS infrastructure resources to connect to your CI/CD system.
This step must be run for each deployment stage in your pipeline, prior to running the sam pipline init command.
"""

PIPELINE_CONFIG_DIR = os.path.join(".aws-sam", "pipeline")
PIPELINE_CONFIG_FILENAME = "pipelineconfig.toml"
PERMISSIONS_PROVIDERS = [OPEN_ID_CONNECT, IAM]
LOG = logging.getLogger(__name__)


@click.command("bootstrap", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Disable interactive prompting for bootstrap parameters, and fail if any required arguments are missing.",
)
@click.option(
    "--stage",
    help="The name of the corresponding deployment stage. "
    "It is used as a suffix for the created AWS infrastructure resources.",
    required=False,
)
@click.option(
    "--pipeline-user",
    help="The Amazon Resource Name (ARN) of the IAM user having its access key ID and secret access key "
    "shared with the CI/CD system. It is used to grant this IAM user permission to access the "
    "corresponding AWS account. If not provided, the command will create one along with the access "
    "key ID and secret access key credentials.",
    required=False,
)
@click.option(
    "--pipeline-execution-role",
    help="The ARN of the IAM role to be assumed by the pipeline user to operate on this stage. "
    "Provide it only if you want to use your own role, otherwise this command will create one.",
    required=False,
)
@click.option(
    "--cloudformation-execution-role",
    help="The ARN of the IAM role to be assumed by the AWS CloudFormation service while deploying the "
    "application's stack. Provide only if you want to use your own role, otherwise the command will create one.",
    required=False,
)
@click.option(
    "--bucket",
    help="The ARN of the Amazon S3 bucket to hold the AWS SAM artifacts.",
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
    help="The ARN of an Amazon ECR image repository to hold the container images of Lambda functions or "
    "layers that have a package type of Image. If provided, the --create-image-repository options is ignored. "
    "If not provided and --create-image-repository is specified, the command will create one.",
    required=False,
)
@click.option(
    "--confirm-changeset/--no-confirm-changeset",
    default=True,
    is_flag=True,
    help="Prompt to confirm if the resources are to be deployed.",
)
@click.option(
    "--permissions-provider",
    default=IAM,
    required=False,
    type=click.Choice(PERMISSIONS_PROVIDERS),
    help="Choose a permissions provider to assume the pipeline execution role. Default is to use an IAM User.",
)
@click.option(
    "--oidc-provider-url", help="The URL of the OIDC provider. Example: https://server.example.com", required=False
)
@click.option("--oidc-client-id", help="The client ID configured to use with the OIDC provider.", required=False)
@click.option(
    "--github-org",
    help="The GitHub organization that the repository belongs to. "
    "If there is no organization enter the Username of the repository owner instead "
    "Only used if using GitHub Actions OIDC for user permissions",
    required=False,
)
@click.option(
    "--github-repo",
    help="The name of the GitHub Repository that deployments will occur from. "
    "Only used if using GitHub Actions OIDC for permissions",
    required=False,
)
@click.option(
    "--deployment-branch",
    help="The name of the branch that deployments will occur from. "
    "Only used if using GitHub Actions OIDC for permissions",
    required=False,
)
@click.option(
    "--oidc-provider",
    help="The name of the CI/CD system that will be used for OIDC permissions",
    type=click.Choice([GITHUB_ACTIONS]),
    required=False,
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
    stage: Optional[str],
    pipeline_user: Optional[str],
    pipeline_execution_role: Optional[str],
    cloudformation_execution_role: Optional[str],
    bucket: Optional[str],
    create_image_repository: bool,
    image_repository: Optional[str],
    confirm_changeset: bool,
    config_file: Optional[str],
    config_env: Optional[str],
    permissions_provider: Optional[str],
    oidc_provider_url: Optional[str],
    oidc_client_id: Optional[str],
    github_org: Optional[str],
    github_repo: Optional[str],
    deployment_branch: Optional[str],
    oidc_provider: Optional[str],
) -> None:
    """
    `sam pipeline bootstrap` command entry point
    """
    do_cli(
        region=ctx.region,
        profile=ctx.profile,
        interactive=interactive,
        stage_configuration_name=stage,
        pipeline_user_arn=pipeline_user,
        pipeline_execution_role_arn=pipeline_execution_role,
        cloudformation_execution_role_arn=cloudformation_execution_role,
        artifacts_bucket_arn=bucket,
        create_image_repository=create_image_repository,
        image_repository_arn=image_repository,
        confirm_changeset=confirm_changeset,
        config_file=config_env,
        config_env=config_file,
        permissions_provider=permissions_provider,
        oidc_provider_url=oidc_provider_url,
        oidc_client_id=oidc_client_id,
        github_org=github_org,
        github_repo=github_repo,
        deployment_branch=deployment_branch,
        oidc_provider=oidc_provider,
    )  # pragma: no cover


def do_cli(
    region: Optional[str],
    profile: Optional[str],
    interactive: bool,
    stage_configuration_name: Optional[str],
    pipeline_user_arn: Optional[str],
    pipeline_execution_role_arn: Optional[str],
    cloudformation_execution_role_arn: Optional[str],
    artifacts_bucket_arn: Optional[str],
    create_image_repository: bool,
    image_repository_arn: Optional[str],
    confirm_changeset: bool,
    config_file: Optional[str],
    config_env: Optional[str],
    permissions_provider: Optional[str],
    oidc_provider_url: Optional[str],
    oidc_client_id: Optional[str],
    github_org: Optional[str],
    github_repo: Optional[str],
    deployment_branch: Optional[str],
    oidc_provider: Optional[str],
    standalone: bool = True,
) -> None:
    """
    implementation of `sam pipeline bootstrap` command
    """
    if not pipeline_user_arn and not permissions_provider == OPEN_ID_CONNECT:
        pipeline_user_arn = _load_saved_pipeline_user_arn()

    if not oidc_provider_url:
        oidc_parameters = _load_saved_oidc_values()
        if oidc_parameters:
            oidc_provider = oidc_parameters[OIDC_PROVIDER]
            oidc_provider_url = oidc_parameters[OIDC_PROVIDER_URL]
            oidc_client_id = oidc_parameters[OIDC_CLIENT_ID]
            github_org = oidc_parameters[GITHUB_ORG]
            github_repo = oidc_parameters[GITHUB_REPO]
            deployment_branch = oidc_parameters[DEPLOYMENT_BRANCH]

    if interactive:
        if standalone:
            click.echo(
                dedent(
                    """\

                    sam pipeline bootstrap generates the required AWS infrastructure resources to connect
                    to your CI/CD system. This step must be run for each deployment stage in your pipeline,
                    prior to running the sam pipeline init command.

                    We will ask for [1] stage definition, [2] account details, and
                    [3] references to existing resources in order to bootstrap these pipeline resources.
                    """
                ),
            )

        guided_context = GuidedContext(
            profile=profile,
            stage_configuration_name=stage_configuration_name,
            pipeline_user_arn=pipeline_user_arn,
            pipeline_execution_role_arn=pipeline_execution_role_arn,
            cloudformation_execution_role_arn=cloudformation_execution_role_arn,
            artifacts_bucket_arn=artifacts_bucket_arn,
            create_image_repository=create_image_repository,
            image_repository_arn=image_repository_arn,
            region=region,
            permissions_provider=permissions_provider,
            oidc_provider_url=oidc_provider_url,
            oidc_client_id=oidc_client_id,
            oidc_provider=oidc_provider,
            github_org=github_org,
            github_repo=github_repo,
            deployment_branch=deployment_branch,
        )
        guided_context.run()
        stage_configuration_name = guided_context.stage_configuration_name
        pipeline_user_arn = guided_context.pipeline_user_arn
        pipeline_execution_role_arn = guided_context.pipeline_execution_role_arn
        cloudformation_execution_role_arn = guided_context.cloudformation_execution_role_arn
        artifacts_bucket_arn = guided_context.artifacts_bucket_arn
        create_image_repository = guided_context.create_image_repository
        image_repository_arn = guided_context.image_repository_arn
        region = guided_context.region
        profile = guided_context.profile
        permissions_provider = guided_context.permissions_provider
        oidc_client_id = guided_context.oidc_client_id
        oidc_provider_url = guided_context.oidc_provider_url
        github_org = guided_context.github_org
        github_repo = guided_context.github_repo
        deployment_branch = guided_context.deployment_branch
        oidc_provider = guided_context.oidc_provider

    subject_claim = None
    pipeline_oidc_provider: Optional[PipelineOidcProvider] = None

    if permissions_provider == OPEN_ID_CONNECT:
        common_oidc_params = {"--oidc-provider-url": oidc_provider_url, "--oidc-client-id": oidc_client_id}
        if oidc_provider == GITHUB_ACTIONS:
            github_oidc_params: dict = {
                "--github-org": github_org,
                "--github-repo": github_repo,
                "--deployment-branch": deployment_branch,
            }
            pipeline_oidc_provider = GitHubOidcProvider(github_oidc_params, common_oidc_params)
        else:
            raise click.UsageError("Missing required parameter '--oidc-provider'")
        pipeline_oidc_provider.verify_all_parameters()

    if not stage_configuration_name:
        raise click.UsageError("Missing required parameter '--stage'")

    environment: Stage = Stage(
        name=stage_configuration_name,
        aws_profile=profile,
        aws_region=region,
        pipeline_user_arn=pipeline_user_arn,
        pipeline_execution_role_arn=pipeline_execution_role_arn,
        cloudformation_execution_role_arn=cloudformation_execution_role_arn,
        artifacts_bucket_arn=artifacts_bucket_arn,
        create_image_repository=create_image_repository,
        image_repository_arn=image_repository_arn,
        oidc_provider_url=oidc_provider_url,
        oidc_client_id=oidc_client_id,
        permissions_provider=permissions_provider,
        subject_claim=subject_claim,
        oidc_provider_name=oidc_provider,
        pipeline_oidc_provider=pipeline_oidc_provider,
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

        if not environment.pipeline_user.is_user_provided and not environment.use_oidc_provider:
            click.secho(
                dedent(
                    f"""\
                    Before running {Colored().bold("sam pipeline init")}, we recommend first setting up AWS credentials
                    in your CI/CD account. Read more about how to do so with your provider in
                    {CONFIG_AWS_CRED_ON_CICD_URL}.
                    """
                )
            )


def _load_saved_pipeline_user_arn() -> Optional[str]:
    samconfig: SamConfig = SamConfig(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)
    if not samconfig.exists():
        return None
    config: Dict[str, str] = samconfig.get_all(cmd_names=_get_bootstrap_command_names(), section="parameters")
    return config.get("pipeline_user")


def _load_saved_oidc_values() -> Dict[str, Optional[str]]:
    samconfig: SamConfig = SamConfig(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)
    if not samconfig.exists():
        return {}
    config: Dict[str, str] = samconfig.get_all(cmd_names=_get_bootstrap_command_names(), section="parameters")
    oidc_parameters: Dict[str, Optional[str]] = {}
    oidc_parameters[OIDC_PROVIDER] = config.get(OIDC_PROVIDER)
    oidc_parameters[OIDC_PROVIDER_URL] = config.get(OIDC_PROVIDER_URL)
    oidc_parameters[OIDC_CLIENT_ID] = config.get(OIDC_CLIENT_ID)
    oidc_parameters[GITHUB_ORG] = config.get(GITHUB_ORG)
    oidc_parameters[GITHUB_REPO] = config.get(GITHUB_REPO)
    oidc_parameters[DEPLOYMENT_BRANCH] = config.get(DEPLOYMENT_BRANCH)
    return oidc_parameters


def _get_bootstrap_command_names() -> List[str]:
    return ["pipeline", "bootstrap"]
