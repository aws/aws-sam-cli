"""
An interactive flow that prompt the user for required information to bootstrap the AWS account of an environment
with the required infrastructure
"""
import os
import sys
from textwrap import dedent
from typing import Optional, List, Tuple, Callable

import click
from botocore.credentials import EnvProvider

from samcli.commands.exceptions import CredentialsError
from samcli.commands.pipeline.external_links import CONFIG_AWS_CRED_DOC_URL
from samcli.lib.bootstrap.bootstrap import get_current_account_id
from samcli.lib.utils.colors import Colored

from samcli.lib.utils.defaults import get_default_aws_region
from samcli.lib.utils.profile import list_available_profiles


class GuidedContext:

    SUPPORTED_OIDC_PROVIDERS = {"1": "GitHub Actions"}

    def __init__(
        self,
        profile: Optional[str] = None,
        stage_configuration_name: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_image_repository: bool = False,
        image_repository_arn: Optional[str] = None,
        region: Optional[str] = None,
        use_oidc_provider: Optional[bool] = None,
        oidc_client_id: Optional[str] = None,
        oidc_provider_url: Optional[str] = None,
    ) -> None:
        self.profile = profile
        self.stage_configuration_name = stage_configuration_name
        self.pipeline_user_arn = pipeline_user_arn
        self.pipeline_execution_role_arn = pipeline_execution_role_arn
        self.cloudformation_execution_role_arn = cloudformation_execution_role_arn
        self.artifacts_bucket_arn = artifacts_bucket_arn
        self.create_image_repository = create_image_repository
        self.image_repository_arn = image_repository_arn
        self.region = region
        self.use_oidc_provider = use_oidc_provider
        self.oidc_client_id = oidc_client_id
        self.oidc_provider_url = oidc_provider_url
        self.color = Colored()

    def _prompt_account_id(self) -> None:
        profiles = list_available_profiles()
        click.echo("The following AWS credential sources are available to use.")
        click.echo(
            dedent(
                f"""\
                To know more about configuration AWS credentials, visit the link below:
                {CONFIG_AWS_CRED_DOC_URL}\
                """
            )
        )
        has_env_creds = os.getenv(EnvProvider.ACCESS_KEY) and os.getenv(EnvProvider.SECRET_KEY)
        click.echo(f"\t1 - Environment variables{' (not available)' if not has_env_creds else ''}")
        for i, profile in enumerate(profiles):
            click.echo(f"\t{i + 2} - {profile} (named profile)")
        click.echo("\tq - Quit and configure AWS credentials")
        answer = click.prompt(
            "Select a credential source to associate with this stage",
            show_choices=False,
            show_default=False,
            type=click.Choice((["1"] if has_env_creds else []) + [str(i + 2) for i in range(len(profiles))] + ["q"]),
        )
        if answer == "q":
            sys.exit(0)
        elif answer == "1":
            # by default, env variable has higher precedence
            # https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html#envvars-list
            self.profile = None
        else:
            self.profile = profiles[int(answer) - 2]

        try:
            account_id = get_current_account_id(self.profile)
            click.echo(
                self.color.green(f"Associated account {account_id} with configuration {self.stage_configuration_name}.")
            )
        except CredentialsError as ex:
            click.echo(f"{self.color.red(ex.message)}\n")
            self._prompt_account_id()

    def _prompt_stage_configuration_name(self) -> None:
        click.echo(
            "Enter a configuration name for this stage. "
            "This will be referenced later when you use the sam pipeline init command:"
        )
        self.stage_configuration_name = click.prompt(
            "Stage configuration name",
            default=self.stage_configuration_name,
            type=click.STRING,
        )

    def _prompt_region_name(self) -> None:
        self.region = click.prompt(
            "Enter the region in which you want these resources to be created",
            type=click.STRING,
            default=get_default_aws_region(),
        )

    def _prompt_pipeline_user(self) -> None:
        self.pipeline_user_arn = click.prompt(
            "Enter the pipeline IAM user ARN if you have previously created one, or we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_pipeline_execution_role(self) -> None:
        self.pipeline_execution_role_arn = click.prompt(
            "Enter the pipeline execution role ARN if you have previously created one, "
            "or we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_cloudformation_execution_role(self) -> None:
        self.cloudformation_execution_role_arn = click.prompt(
            "Enter the CloudFormation execution role ARN if you have previously created one, "
            "or we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_artifacts_bucket(self) -> None:
        self.artifacts_bucket_arn = click.prompt(
            "Please enter the artifact bucket ARN for your Lambda function. "
            "If you do not have a bucket, we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_image_repository(self) -> None:
        if click.confirm("Does your application contain any IMAGE type Lambda functions?"):
            self.image_repository_arn = click.prompt(
                "Please enter the ECR image repository ARN(s) for your Image type function(s)."
                "If you do not yet have a repository, we will create one for you",
                default="",
                type=click.STRING,
            )
            self.create_image_repository = not bool(self.image_repository_arn)
        else:
            self.create_image_repository = False

    def _prompt_use_oidc_provider(self) -> None:
        click.echo("Select a user permissions provider:")
        click.echo("\t1 - IAM (default)")
        click.echo("\t2 - OpenID Connect")
        user_provider = click.prompt("",
            type=click.Choice((["1","2"])),
            show_choices=False,
            show_default=False,
            default="1",
            prompt_suffix=""
        )
        self.use_oidc_provider = True if user_provider == "2" else False

    def _prompt_oidc_provider(self) -> None:
        click.echo("Select an OIDC Provider:")
        for key in self.SUPPORTED_OIDC_PROVIDERS:
            click.echo("\t{key} - {provider}".format(key=key, provider=self.SUPPORTED_OIDC_PROVIDERS[key]))
        self.oidc_provider = click.prompt("",
            type=click.Choice((list(self.SUPPORTED_OIDC_PROVIDERS))),
            show_choices=False,
            show_default=False,
            prompt_suffix=""
        )

    def _prompt_oidc_provider_url(self) -> None:
        self.oidc_provider_url = click.prompt(
            "Enter the URL of the OIDC provider",
            type=click.STRING
        )
    
    def _prompt_oidc_client_id(self) -> None:
        self.oidc_client_id = click.prompt(
            "Enter the OIDC client ID (sometimes called audience)",
            type=click.STRING
        )

    def _prompt_subject_claim(self, oidc_provider):
        if self.oidc_provider == "1":
            github_org = self._prompt_github_org()
            github_repo = self._prompt_github_repo()
            branch = self._prompt_github_branch()
            self.subject_claim = "repo:{org}/{repo}:ref:refs/heads/{branch}".format(org=github_org, repo=github_repo, branch=branch)
    
    def _prompt_github_org(self) -> None:
        return click.prompt(
            "Enter the GitHub Organization that the code repository belongs to."
            " If there is no organization enter your username instead",
            type=click.STRING
        )
    
    def _prompt_github_repo(self) -> None:
        return click.prompt(
            "Enter the name of the GitHub repository",
            type=click.STRING
        )
    
    def _prompt_github_branch(self) -> None:
        return click.prompt(
            "Enter the name of the branch that deployments will occur from",
            type=click.STRING
        )
    
    def _validate_oidc_provider_url(self) -> None:
        while (self.oidc_provider_url.find('https://') == -1):
            click.echo("Please ensure the OIDC URL begins with 'https://'")
            self._prompt_oidc_provider_url()

    def _get_user_inputs(self) -> List[Tuple[str, Callable[[], None]]]:
        inputs = [
            (f"Account: {get_current_account_id(self.profile)}", self._prompt_account_id),
            (f"Stage configuration name: {self.stage_configuration_name}", self._prompt_stage_configuration_name),
            (f"Region: {self.region}", self._prompt_region_name)]

        if self.use_oidc_provider:
            inputs.extend([
                (f"OIDC Identity Provider URL: {self.oidc_provider_url}", self._prompt_oidc_provider_url),
                (f"OIDC Client ID: {self.oidc_client_id}", self._prompt_oidc_client_id)
            ])
        else:
            inputs.extend([
                (
                    f"Pipeline user ARN: {self.pipeline_user_arn}"
                    if self.pipeline_user_arn
                    else "Pipeline user: [to be created]",
                    self._prompt_pipeline_user,
                )
            ])

        inputs.extend([
            (
                f"Pipeline execution role ARN: {self.pipeline_execution_role_arn}"
                if self.pipeline_execution_role_arn
                else "Pipeline execution role: [to be created]",
                self._prompt_pipeline_execution_role,
            ),
            (
                f"CloudFormation execution role ARN: {self.cloudformation_execution_role_arn}"
                if self.cloudformation_execution_role_arn
                else "CloudFormation execution role: [to be created]",
                self._prompt_cloudformation_execution_role,
            ),
            (
                f"Artifacts bucket ARN: {self.artifacts_bucket_arn}"
                if self.artifacts_bucket_arn
                else "Artifacts bucket: [to be created]",
                self._prompt_artifacts_bucket,
            ),
            (
                f"ECR image repository ARN: {self.image_repository_arn}"
                if self.image_repository_arn
                else f"ECR image repository: [{'to be created' if self.create_image_repository else 'skipped'}]",
                self._prompt_image_repository,
            ),
        ])
        return inputs

    def run(self) -> None:  # pylint: disable=too-many-branches
        """
        Runs an interactive questionnaire to prompt the user for the ARNs of the AWS resources(infrastructure) required
        for the pipeline to work. Users can provide all, none or some resources' ARNs and leave the remaining empty
        and it will be created by the bootstrap command
        """
        click.secho(self.color.bold("[1] Stage definition"))
        if self.stage_configuration_name:
            click.echo(f"Stage configuration name: {self.stage_configuration_name}")
        else:
            self._prompt_stage_configuration_name()
        click.echo()

        click.secho(self.color.bold("[2] Account details"))
        self._prompt_account_id()
        click.echo()

        if not self.region:
            self._prompt_region_name()

        if not self.use_oidc_provider and not self.pipeline_user_arn:
            self._prompt_use_oidc_provider()

        if self.use_oidc_provider:
            self._prompt_oidc_provider()
            self._prompt_oidc_provider_url()
            self._validate_oidc_provider_url()
            self._prompt_oidc_client_id()
            self._prompt_subject_claim(self.oidc_provider)
        else:
            if self.pipeline_user_arn:
                click.echo(f"Pipeline IAM user ARN: {self.pipeline_user_arn}")
            else:
                self._prompt_pipeline_user()
        click.echo()

        click.secho(self.color.bold("[3] Reference application build resources"))

        if self.pipeline_execution_role_arn:
            click.echo(f"Pipeline execution role ARN: {self.pipeline_execution_role_arn}")
        else:
            self._prompt_pipeline_execution_role()

        if self.cloudformation_execution_role_arn:
            click.echo(f"CloudFormation execution role ARN: {self.cloudformation_execution_role_arn}")
        else:
            self._prompt_cloudformation_execution_role()

        if self.artifacts_bucket_arn:
            click.echo(f"Artifacts bucket ARN: {self.cloudformation_execution_role_arn}")
        else:
            self._prompt_artifacts_bucket()

        if self.image_repository_arn:
            click.echo(f"ECR image repository ARN: {self.image_repository_arn}")
        else:
            self._prompt_image_repository()
        click.echo()

        # Ask customers to confirm the inputs
        click.secho(self.color.bold("[4] Summary"))
        while True:
            inputs = self._get_user_inputs()
            click.secho("Below is the summary of the answers:")
            for i, (text, _) in enumerate(inputs):
                click.secho(f"\t{i + 1} - {text}")
            edit_input = click.prompt(
                text="Press enter to confirm the values above, or select an item to edit the value",
                default="0",
                show_choices=False,
                show_default=False,
                type=click.Choice(["0"] + [str(i + 1) for i in range(len(inputs))]),
            )
            click.echo()
            if int(edit_input):
                inputs[int(edit_input) - 1][1]()
                click.echo()
            else:
                break
