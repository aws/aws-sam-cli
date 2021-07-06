"""
An interactive flow that prompt the user for required information to bootstrap the AWS account of an environment
with the required infrastructure
"""
from textwrap import dedent
from typing import Optional

import click

from samcli.commands.pipeline.external_links import CONFIG_AWS_CRED_DOC_URL
from samcli.lib.bootstrap.bootstrap import get_current_account_id

from samcli.lib.utils.defaults import get_default_aws_region


class GuidedContext:
    def __init__(
        self,
        environment_name: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_image_repository: bool = False,
        image_repository_arn: Optional[str] = None,
        pipeline_ip_range: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        self.environment_name = environment_name
        self.pipeline_user_arn = pipeline_user_arn
        self.pipeline_execution_role_arn = pipeline_execution_role_arn
        self.cloudformation_execution_role_arn = cloudformation_execution_role_arn
        self.artifacts_bucket_arn = artifacts_bucket_arn
        self.create_image_repository = create_image_repository
        self.image_repository_arn = image_repository_arn
        self.pipeline_ip_range = pipeline_ip_range
        self.region = region

    def run(self) -> None:
        """
        Runs an interactive questionnaire to prompt the user for the ARNs of the AWS resources(infrastructure) required
        for the pipeline to work. Users can provide all, none or some resources' ARNs and leave the remaining empty
        and it will be created by the bootstrap command
        """
        click.secho(
            dedent(
                """\
                SAM Pipeline Bootstrap generates the necessary AWS resources to connect your
                CI/CD pipeline tool. We will ask for [1] account details, [2] stage definition, 
                and [3] references to existing resources in order to bootstrap these pipeline 
                resources. You can also add optional security parameters.
                """
            ),
            fg="cyan",
        )

        account_id = get_current_account_id()
        click.secho("[1] Account details", bold=True)
        if click.confirm(f"You are bootstrapping resources in Account {account_id}. Do you want to switch accounts?"):
            click.echo(f"Please refer to this page about configuring credentials: {CONFIG_AWS_CRED_DOC_URL}.")
            exit(0)

        if not self.environment_name:
            self.environment_name = click.prompt(
                f"Environment name (a descriptive name for the environment which will be deployed"
                f" to AWS account {account_id})",
                type=click.STRING,
            )

        if not self.region:
            self.region = click.prompt(
                "\nAWS region (the AWS region where the environment infrastructure resources will be deployed to)",
                type=click.STRING,
                default=get_default_aws_region(),
            )

        if not self.pipeline_user_arn:
            click.echo(
                "\nThere must be exactly one pipeline user across all of the environments. "
                "If you have ran this command before to bootstrap a previous environment, please "
                "provide the ARN of the created pipeline user, otherwise, we will create a new user for you. "
                "Please make sure to store the credentials safely with the CI/CD system."
            )
            self.pipeline_user_arn = click.prompt(
                "Pipeline user [leave blank to create one]", default="", type=click.STRING
            )

        if not self.pipeline_execution_role_arn:
            self.pipeline_execution_role_arn = click.prompt(
                "\nPipeline execution role (an IAM role assumed by the pipeline user to operate on this environment) "
                "[leave blank to create one]",
                default="",
                type=click.STRING,
            )

        if not self.cloudformation_execution_role_arn:
            self.cloudformation_execution_role_arn = click.prompt(
                "\nCloudFormation execution role (an IAM role assumed by CloudFormation to deploy "
                "the application's stack) [leave blank to create one]",
                default="",
                type=click.STRING,
            )

        if not self.artifacts_bucket_arn:
            self.artifacts_bucket_arn = click.prompt(
                "\nArtifacts bucket (S3 bucket to hold the AWS SAM build artifacts) [leave blank to create one]",
                default="",
                type=click.STRING,
            )
        if not self.image_repository_arn:
            click.echo(
                "\nIf your SAM template includes (or going to include) Lambda functions of Image package type, "
                "then an ECR image repository is required. Should we create one?"
            )
            click.echo("\t1 - No, My SAM template won't include Lambda functions of Image package type")
            click.echo("\t2 - Yes, I need help creating one")
            click.echo("\t3 - I already have an ECR image repository")
            choice = click.prompt(text="Choice", show_choices=False, type=click.Choice(["1", "2", "3"]))
            if choice == "1":
                self.create_image_repository = False
            elif choice == "2":
                self.create_image_repository = True
            else:  # choice == "3"
                self.create_image_repository = False
                self.image_repository_arn = click.prompt("ECR image repository", type=click.STRING)

        if not self.pipeline_ip_range:
            click.echo("\nWe can deny requests not coming from a recognized IP address range.")
            self.pipeline_ip_range = click.prompt(
                "Pipeline IP address range (using CIDR notation) [leave blank if you don't know]",
                default="",
                type=click.STRING,
            )
