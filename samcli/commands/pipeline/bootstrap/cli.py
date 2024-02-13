"""
CLI command for "pipeline bootstrap", which sets up the require pipeline infrastructure resources
"""

import os
from textwrap import dedent
from typing import Any, Dict, List, Optional

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import aws_creds_options, common_options, pass_context, print_cmdline_args
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.pipeline.bootstrap.oidc_config import (
    BitbucketOidcConfig,
    GitHubOidcConfig,
    GitLabOidcConfig,
    OidcConfig,
)
from samcli.commands.pipeline.bootstrap.pipeline_oidc_provider import PipelineOidcProvider
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

from .guided_context import BITBUCKET, GITHUB_ACTIONS, GITLAB, IAM, OPEN_ID_CONNECT

SHORT_HELP = "Generates the required AWS resources to connect your CI/CD system."

HELP_TEXT = """
This command generates the required AWS infrastructure resources to connect to your CI/CD system.
This step must be run for each deployment stage in your pipeline, prior to running the sam pipeline init command.
"""

PIPELINE_CONFIG_DIR = os.path.join(".aws-sam", "pipeline")
PIPELINE_CONFIG_FILENAME = "pipelineconfig.toml"
PERMISSIONS_PROVIDERS = [OPEN_ID_CONNECT, IAM]
OPENID_CONNECT = "OpenID Connect (OIDC)"


@click.command("bootstrap", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@configuration_option(provider=ConfigProvider(section="parameters"))
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
    "--oidc-provider-url",
    help="The URL of the OIDC provider.",
    required=False,
)
@click.option("--oidc-client-id", help="The client ID configured to use with the OIDC provider.", required=False)
@click.option(
    "--github-org",
    help="The GitHub organization that the repository belongs to. "
    "If there is no organization enter the Username of the repository owner instead "
    "Only used if using GitHub Actions OIDC for user permissions",
    required=False,
    cls=ClickMutex,
    incompatible_params=["bitbucket_repo_uuid", "gitlab_group", "gitlab_project"],
)
@click.option(
    "--github-repo",
    help="The name of the GitHub Repository that deployments will occur from. "
    "Only used if using GitHub Actions OIDC for permissions",
    required=False,
    cls=ClickMutex,
    incompatible_params=["bitbucket_repo_uuid", "gitlab_group", "gitlab_project"],
)
@click.option(
    "--deployment-branch",
    help="The name of the branch that deployments will occur from. "
    "Only used if using GitHub Actions OIDC for permissions",
    required=False,
)
@click.option(
    "--oidc-provider",
    help="The name of the CI/CD system that will be used for OIDC permissions "
    "Currently supported CI/CD systems are : GitLab, GitHub and Bitbucket",
    type=click.Choice([GITHUB_ACTIONS, GITLAB, BITBUCKET]),
    required=False,
    cls=ClickMutex,
    required_param_lists=[
        ["gitlab_group", "gitlab_project"],
        ["github_org", "github_repo"],
        ["bitbucket_repo_uuid"],
    ],
)
@click.option(
    "--gitlab-group",
    help="The GitLab group that the repository belongs to. Only used if using GitLab OIDC for permissions",
    required=False,
    cls=ClickMutex,
    incompatible_params=["bitbucket_repo_uuid", "github_org", "github_repo"],
)
@click.option(
    "--gitlab-project",
    help="The GitLab project name. Only used if using GitLab OIDC for permissions",
    required=False,
    cls=ClickMutex,
    incompatible_params=["bitbucket_repo_uuid", "github_org", "github_repo"],
)
@click.option(
    "--bitbucket-repo-uuid",
    help="The UUID of the Bitbucket repository. Only used if using Bitbucket OIDC for permissions. "
    "Found at https://bitbucket.org/<WORKSPACE>/<REPOSITORY>/admin/addon/admin/pipelines/openid-connect",
    required=False,
    cls=ClickMutex,
    incompatible_params=["gitlab_group", "gitlab_project", "github_org", "github_repo"],
)
@click.option(
    "--cicd-provider",
    help="The CICD platform for the SAM Pipeline",
    required=False,
)
@common_options
@aws_creds_options
@save_params_option
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
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
    gitlab_group: Optional[str],
    gitlab_project: Optional[str],
    bitbucket_repo_uuid: Optional[str],
    cicd_provider: Optional[str],
    save_params: bool,
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
        gitlab_group=gitlab_group,
        gitlab_project=gitlab_project,
        bitbucket_repo_uuid=bitbucket_repo_uuid,
        cicd_provider=cicd_provider,
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
    gitlab_group: Optional[str],
    gitlab_project: Optional[str],
    bitbucket_repo_uuid: Optional[str],
    cicd_provider: Optional[str],
    standalone: bool = True,
) -> None:
    """
    implementation of `sam pipeline bootstrap` command
    """
    from samcli.commands.pipeline.bootstrap.guided_context import GuidedContext
    from samcli.commands.pipeline.external_links import CONFIG_AWS_CRED_ON_CICD_URL
    from samcli.lib.pipeline.bootstrap.stage import (
        BITBUCKET_REPO_UUID,
        DEPLOYMENT_BRANCH,
        GITHUB_ORG,
        GITHUB_REPO,
        GITLAB_GROUP,
        GITLAB_PROJECT,
        OIDC_CLIENT_ID,
        OIDC_PROVIDER,
        OIDC_PROVIDER_URL,
        OIDC_SUPPORTED_PROVIDER,
        PERMISSIONS_PROVIDER,
        Stage,
    )
    from samcli.lib.utils.colors import Colored

    config_parameters = _load_config_values()
    if not pipeline_user_arn and not permissions_provider == OPEN_ID_CONNECT:
        pipeline_user_arn = config_parameters.get("pipeline_user")

    enable_oidc_option = False
    if not cicd_provider or cicd_provider in OIDC_SUPPORTED_PROVIDER:
        enable_oidc_option = True
        oidc_provider = cicd_provider

    oidc_config = OidcConfig(
        oidc_client_id=oidc_client_id, oidc_provider=oidc_provider, oidc_provider_url=oidc_provider_url
    )
    gitlab_config = GitLabOidcConfig(
        gitlab_group=gitlab_group, gitlab_project=gitlab_project, deployment_branch=deployment_branch
    )
    github_config = GitHubOidcConfig(
        github_org=github_org, github_repo=github_repo, deployment_branch=deployment_branch
    )
    bitbucket_config = BitbucketOidcConfig(bitbucket_repo_uuid=bitbucket_repo_uuid)
    if config_parameters:
        saved_provider = config_parameters.get(PERMISSIONS_PROVIDER)
        if saved_provider == OPENID_CONNECT:
            permissions_provider = OPEN_ID_CONNECT
            oidc_config.update_values(
                oidc_provider=config_parameters.get(OIDC_PROVIDER),
                oidc_provider_url=config_parameters.get(OIDC_PROVIDER_URL),
                oidc_client_id=config_parameters.get(OIDC_CLIENT_ID),
            )
            github_config.update_values(
                github_org=config_parameters.get(GITHUB_ORG),
                github_repo=config_parameters.get(GITHUB_REPO),
                deployment_branch=config_parameters.get(DEPLOYMENT_BRANCH),
            )
            gitlab_config.update_values(
                gitlab_group=config_parameters.get(GITLAB_GROUP),
                gitlab_project=config_parameters.get(GITLAB_PROJECT),
                deployment_branch=config_parameters.get(DEPLOYMENT_BRANCH),
            )
            bitbucket_config.update_values(bitbucket_repo_uuid=config_parameters.get(BITBUCKET_REPO_UUID))
        elif saved_provider == "AWS IAM":
            permissions_provider = IAM
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
            oidc_config=oidc_config,
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            enable_oidc_option=enable_oidc_option,
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

    subject_claim = None
    pipeline_oidc_provider: Optional[PipelineOidcProvider] = None

    if permissions_provider == OPEN_ID_CONNECT:
        pipeline_oidc_provider = _get_pipeline_oidc_provider(
            oidc_config=oidc_config,
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
        )
        subject_claim = pipeline_oidc_provider.get_subject_claim()

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
        oidc_provider_url=oidc_config.oidc_provider_url,
        oidc_client_id=oidc_config.oidc_client_id,
        permissions_provider=permissions_provider,
        subject_claim=subject_claim,
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


def _get_pipeline_oidc_provider(
    oidc_config: OidcConfig,
    github_config: GitHubOidcConfig,
    gitlab_config: GitLabOidcConfig,
    bitbucket_config: BitbucketOidcConfig,
) -> PipelineOidcProvider:
    from samcli.commands.pipeline.bootstrap.pipeline_oidc_provider import (
        BitbucketOidcProvider,
        GitHubOidcProvider,
        GitLabOidcProvider,
    )

    if oidc_config.oidc_provider == GITHUB_ACTIONS:
        github_oidc_params: dict = {
            GitHubOidcProvider.GITHUB_ORG_PARAMETER_NAME: github_config.github_org,
            GitHubOidcProvider.GITHUB_REPO_PARAMETER_NAME: github_config.github_repo,
            GitHubOidcProvider.DEPLOYMENT_BRANCH_PARAMETER_NAME: github_config.deployment_branch,
        }
        return GitHubOidcProvider(github_oidc_params, oidc_config.get_oidc_parameters())
    if oidc_config.oidc_provider == GITLAB:
        gitlab_oidc_params: dict = {
            GitLabOidcProvider.GITLAB_PROJECT_PARAMETER_NAME: gitlab_config.gitlab_project,
            GitLabOidcProvider.GITLAB_GROUP_PARAMETER_NAME: gitlab_config.gitlab_group,
            GitLabOidcProvider.DEPLOYMENT_BRANCH_PARAMETER_NAME: gitlab_config.deployment_branch,
        }
        return GitLabOidcProvider(gitlab_oidc_params, oidc_config.get_oidc_parameters())
    if oidc_config.oidc_provider == BITBUCKET:
        bitbucket_oidc_params: dict = {
            BitbucketOidcProvider.BITBUCKET_REPO_UUID_PARAMETER_NAME: bitbucket_config.bitbucket_repo_uuid
        }
        return BitbucketOidcProvider(bitbucket_oidc_params, oidc_config.get_oidc_parameters())
    raise click.UsageError("Missing required parameter '--oidc-provider'")


def _load_config_values() -> Dict[str, str]:
    samconfig: SamConfig = SamConfig(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)
    if not samconfig.exists():
        return {}
    config: Dict[str, str] = samconfig.get_all(cmd_names=_get_bootstrap_command_names(), section="parameters")
    return config


def _get_bootstrap_command_names() -> List[str]:
    return ["pipeline", "bootstrap"]
