"""
An interactive flow that prompt the user for required information to bootstrap the AWS account of an environment
with the required infrastructure
"""
import sys
from textwrap import dedent
from typing import Optional, List, Tuple, Callable

import click

from samcli.commands.pipeline.external_links import CONFIG_AWS_CRED_DOC_URL
from samcli.lib.bootstrap.bootstrap import get_current_account_id
from samcli.lib.utils.colors import Colored

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
        self.color = Colored()

    def _prompt_stage_name(self) -> None:
        click.echo(
            "Enter a name for the stage you want to bootstrap. This will be referenced later "
            "when generating a Pipeline Config File with Pipeline Init."
        )
        self.environment_name = click.prompt(
            "Stage name",
            default=self.environment_name,
            type=click.STRING,
        )

    def _prompt_region_name(self) -> None:
        self.region = click.prompt(
            "Enter the region you want these resources to create",
            type=click.STRING,
            default=get_default_aws_region(),
        )

    def _prompt_pipeline_user(self) -> None:
        self.pipeline_user_arn = click.prompt(
            "Enter the Pipeline IAM User ARN if you have previously created one, or we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_pipeline_execution_role(self) -> None:
        self.pipeline_execution_role_arn = click.prompt(
            "Enter the Pipeline execution role ARN if you have previously created one, "
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
            "Please enter the bucket artifact ARN for your Lambda function. "
            "If you do not have a bucket, we will create one for you",
            default="",
            type=click.STRING,
        )

    def _prompt_image_repository(self) -> None:
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

    def _prompt_ip_range(self) -> None:
        self.pipeline_ip_range = click.prompt(
            "For added security, you can define the permitted Pipeline IP range. "
            "Enter the IP addresses to restrict access to",
            default="",
            type=click.STRING,
        )

    def _get_user_inputs(self) -> List[Tuple[str, Callable[[], None]]]:
        return [
            (f"Stage name: {self.environment_name}", self._prompt_stage_name),
            (f"Region: {self.region}", self._prompt_region_name),
            (
                f"Pipeline user ARN: {self.pipeline_user_arn}"
                if self.pipeline_user_arn
                else "Pipeline user: to be created",
                self._prompt_pipeline_user,
            ),
            (
                f"Pipeline execution role ARN: {self.pipeline_execution_role_arn}"
                if self.pipeline_execution_role_arn
                else "Pipeline execution role: to be created",
                self._prompt_pipeline_execution_role,
            ),
            (
                f"CloudFormation execution role ARN: {self.cloudformation_execution_role_arn}"
                if self.cloudformation_execution_role_arn
                else "CloudFormation execution role: to be created",
                self._prompt_cloudformation_execution_role,
            ),
            (
                f"Artifacts bucket ARN: {self.artifacts_bucket_arn}"
                if self.artifacts_bucket_arn
                else "Artifacts bucket: to be created",
                self._prompt_artifacts_bucket,
            ),
            (
                f"ECR image repository ARN: {self.image_repository_arn}"
                if self.image_repository_arn
                else f"ECR image repository: {'to be created' if self.create_image_repository else 'skipped'}",
                self._prompt_image_repository,
            ),
            (
                f"Pipeline IP address range: {self.pipeline_ip_range}"
                if self.pipeline_ip_range
                else "Pipeline IP address range: none",
                self._prompt_ip_range,
            ),
        ]

    def run(self) -> None:  # pylint: disable=too-many-branches
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
            sys.exit(0)

        click.secho("[2] Stage definition", bold=True)
        if self.environment_name:
            click.echo(f"Stage name: {self.environment_name}")
        else:
            self._prompt_stage_name()

        if not self.region:
            self._prompt_region_name()

        click.secho("[3] Reference existing resources", bold=True)
        if self.pipeline_user_arn:
            click.echo(f"Pipeline IAM User ARN: {self.pipeline_user_arn}")
        else:
            self._prompt_pipeline_user()

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

        click.secho("[4] Security definition - OPTIONAL", bold=True)
        if self.pipeline_ip_range:
            click.echo(f"Pipeline IP address range: {self.pipeline_ip_range}")
        else:
            self._prompt_ip_range()

        # Ask customers to confirm the inputs
        while True:
            inputs = self._get_user_inputs()
            click.secho(self.color.cyan("Below is the summary of the answers:"))
            for i, (text, _) in enumerate(inputs):
                click.secho(self.color.cyan(f"  {i + 1}. {text}"))
            edit_input = click.prompt(
                text="Press enter to confirm the values above, or select an item to edit the value",
                default="0",
                show_choices=False,
                show_default=False,
                type=click.Choice(["0"] + [str(i + 1) for i in range(len(inputs))]),
            )
            if int(edit_input):
                inputs[int(edit_input) - 1][1]()
            else:
                break
