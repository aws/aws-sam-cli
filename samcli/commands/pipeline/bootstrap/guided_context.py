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

        click.secho("[2] Stage definition", bold=True)
        if self.environment_name:
            click.echo(f"Stage name: {self.environment_name}")
        else:
            click.echo(
                "Enter a name for the stage you want to bootstrap. This will be referenced later "
                "when generating a Pipeline Config File with Pipeline Init."
            )
            self.environment_name = click.prompt(
                "Stage name",
                type=click.STRING,
            )

        if not self.region:
            self.region = click.prompt(
                "Enter the region you want these resources to create",
                type=click.STRING,
                default=get_default_aws_region(),
            )

        click.secho("[3] Reference existing resources", bold=True)
        if self.pipeline_user_arn:
            click.echo(f"Pipeline IAM User ARN: {self.pipeline_user_arn}")
        else:
            self.pipeline_user_arn = click.prompt(
                "Enter the Pipeline IAM User ARN if you have previously created one, or we will create one for you",
                default="",
                type=click.STRING,
            )

        if self.pipeline_execution_role_arn:
            click.echo(f"Pipeline execution role ARN: {self.pipeline_execution_role_arn}")
        else:
            self.pipeline_execution_role_arn = click.prompt(
                "Enter the Pipeline execution role ARN if you have previously created one, "
                "or we will create one for you",
                default="",
                type=click.STRING,
            )

        if self.cloudformation_execution_role_arn:
            click.echo(f"CloudFormation execution role ARN: {self.cloudformation_execution_role_arn}")
        else:
            self.cloudformation_execution_role_arn = click.prompt(
                "Enter the CloudFormation execution role ARN if you have previously created one, "
                "or we will create one for you",
                default="",
                type=click.STRING,
            )

        if self.artifacts_bucket_arn:
            click.echo(f"Artifacts bucket ARN: {self.cloudformation_execution_role_arn}")
        else:
            self.artifacts_bucket_arn = click.prompt(
                "Please enter the bucket artifact ARN for your Lambda function. "
                "If you do not have a bucket, we will create one for you",
                default="",
                type=click.STRING,
            )

        if self.image_repository_arn:
            click.echo(f"ECR image repository ARN: {self.image_repository_arn}")
        else:
            if click.confirm("Does your application contain any IMAGE type Lambda functions?"):
                self.image_repository_arn = click.prompt(
                    "Please enter the ECR image repository ARN(s) for your IMAGE type function(s)."
                    "If you do not yet have a repostiory, we will create one for you",
                    default="",
                    type=click.STRING,
                )
                self.create_image_repository = not bool(self.image_repository_arn)
            else:
                self.create_image_repository = False

        click.secho("[4] Security definition - OPTIONAL", bold=True)
        if self.pipeline_ip_range:
            click.echo(f"Pipeline IP address range: {self.pipeline_ip_range}")
        else:
            self.pipeline_ip_range = click.prompt(
                "For added security, you can define the permitted Pipeline IP range. "
                "Enter the IP addresses to restrict access to",
                default="",
                type=click.STRING,
            )
