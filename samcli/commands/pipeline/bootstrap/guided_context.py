"""
An interactive flow that prompt the user for required information to bootstrap the AWS account of an environment
with the required infrastructure
"""
from typing import Optional

import click


class GuidedContext:
    def __init__(
        self,
        environment_name: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_ecr_repo: bool = False,
        ecr_repo_arn: Optional[str] = None,
        pipeline_ip_range: Optional[str] = None,
    ) -> None:
        self.environment_name = environment_name
        self.pipeline_user_arn = pipeline_user_arn
        self.pipeline_execution_role_arn = pipeline_execution_role_arn
        self.cloudformation_execution_role_arn = cloudformation_execution_role_arn
        self.artifacts_bucket_arn = artifacts_bucket_arn
        self.create_ecr_repo = create_ecr_repo
        self.ecr_repo_arn = ecr_repo_arn
        self.pipeline_ip_range = pipeline_ip_range

    def run(self) -> None:
        """
        Runs an interactive questionnaire to prompt the user for the ARNs of the AWS resources(infrastructure) required
        for the pipeline to work. Users can provide all, none or some resources' ARNs and leave the remaining empty
        and it will be created by the bootstrap command
        """
        if not self.environment_name:
            self.environment_name = click.prompt("Environment Name", type=click.STRING)

        if not self.pipeline_user_arn:
            click.echo(
                "\nThere must be exactly one pipeline user across all of the environments. "
                "If you have ran this command before to bootstrap a previous environment, please "
                "provide the ARN of the created pipeline user, otherwise, we will create a new user for you. "
                "Please make sure to store the credentials safely with the CI/CD provider."
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
        if not self.ecr_repo_arn:
            click.echo(
                "\nIf your SAM template includes (or going to include) Lambda functions of Image package type, "
                "then an ECR repository is required. Should we create one?"
            )
            click.echo("\t1 - No, My SAM template won't include Lambda functions of Image package type")
            click.echo("\t2 - Yes, I need help creating one")
            click.echo("\t3 - I already have an ECR repository")
            choice = click.prompt(text="Choice", show_choices=False, type=click.Choice(["1", "2", "3"]))
            if choice == "1":
                self.create_ecr_repo = False
            elif choice == "2":
                self.create_ecr_repo = True
            else:  # choice == "3"
                self.create_ecr_repo = False
                self.ecr_repo_arn = click.prompt("ECR repo", type=click.STRING)

        if not self.pipeline_ip_range:
            click.echo("\nWe can deny requests not coming from a recognized IP address range.")
            self.pipeline_ip_range = click.prompt(
                "Pipeline IP address range (using CIDR notation) [leave blank if you don't know]",
                default="",
                type=click.STRING,
            )
