"""
An interactive flow that prompt the user for required information to bootstrap the AWS account of a pipeline stage
with the required infrastructure
"""
from typing import Optional

import click


class GuidedContext:
    def __init__(
        self,
        stage_name: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_ecr_repo: bool = False,
        ecr_repo_arn: Optional[str] = None,
        pipeline_ip_range: Optional[str] = None,
    ) -> None:
        self.stage_name = stage_name
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
        if not self.stage_name:
            self.stage_name = click.prompt("Stage Name", type=click.STRING)

        if not self.pipeline_user_arn:
            click.echo(
                "\nThere must be exactly one pipeline user across all of the pipeline stages. "
                "If you have ran this command before to bootstrap a previous pipeline stage, please "
                "provide the ARN of the created pipeline user, otherwise, we will create a new user for you, "
                "please make sure to configure user's AccessKeyId and SecretAccessKey for the CI/CD provider."
            )
            self.pipeline_user_arn = click.prompt(
                "Pipeline user [leave blank to create one]", default="", type=click.STRING
            )

        if not self.pipeline_execution_role_arn:
            self.pipeline_execution_role_arn = click.prompt(
                "\nPipeline execution role(an IAM Role to be assumed by the pipeline-user to operate on this stage.) "
                "[leave blank to create one]",
                default="",
                type=click.STRING,
            )

        if not self.cloudformation_execution_role_arn:
            self.cloudformation_execution_role_arn = click.prompt(
                "\nCloudFormation execution role(an IAM Role to be assumed by the CloudFormation service to deploy "
                "the application's stack) [leave blank to create one]",
                default="",
                type=click.STRING,
            )

        if not self.artifacts_bucket_arn:
            self.artifacts_bucket_arn = click.prompt(
                "\nArtifacts bucket(S3 bucket to hold the sam build artifacts) " "[leave blank to create one]",
                default="",
                type=click.STRING,
            )
        if not self.ecr_repo_arn:
            click.echo(
                "\nIf your SAM template will include lambda functions of Image package-type, "
                "then an ECR repo is required, should we create one?"
            )
            click.echo("\t1 - No, My SAM Template won't include lambda functions of Image package-type")
            click.echo("\t2 - Yes, I need a help creating one")
            click.echo("\t3 - I already have an ECR repo")
            choice = click.prompt(text="Choice", show_choices=False, type=click.Choice(["1", "2", "3"]))
            if choice == "1":
                self.create_ecr_repo = False
            elif choice == "2":
                self.create_ecr_repo = True
            else:  # choice == "3"
                self.create_ecr_repo = False
                self.ecr_repo_arn = click.prompt("ECR repo", type=click.STRING)

        if not self.pipeline_ip_range:
            click.echo("\nWe can deny requests if not coming from a recognized IP address.")
            self.pipeline_ip_range = click.prompt(
                "Pipeline IP address range [leave blank if you don't know]", default="", type=click.STRING
            )
