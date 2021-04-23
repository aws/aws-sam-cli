""" Pipeline stage"""
import os
import pathlib
import re
from typing import Dict, List, Optional

import click

from samcli.lib.config.samconfig import SamConfig
from samcli.lib.utils.managed_cloudformation_stack import manage_stack, StackOutput
from .resource import Resource, IAMUser, ECRRepo

CFN_TEMPLATE_PATH = str(pathlib.Path(os.path.dirname(__file__)))
STACK_NAME_PREFIX = "aws-sam-cli-managed"
STAGE_RESOURCES_STACK_NAME_SUFFIX = "pipeline-resources"
STAGE_RESOURCES_CFN_TEMPLATE = "stage_resources.yaml"
PIPELINE_USER = "pipeline_user"
PIPELINE_EXECUTION_ROLE = "pipeline_execution_role"
CLOUDFORMATION_EXECUTION_ROLE = "cloudformation_execution_role"
ARTIFACTS_BUCKET = "artifacts_bucket"
ECR_REPO = "ecr_repo"


class Stage:
    """
    Represents a pipeline stage

    Attributes
    ----------
    name: str
        The name of the stage
    aws_profile: Optional[str]
        The named AWS profile(in user's machine) of the AWS account to deploy this stage to.
    aws_region: Optional[str]
        The AWS region to deploy this stage to.
    pipeline_user: IAMUser
        The IAM User having its AccessKeyId and SecretAccessKey credentials shared with the CI/CD provider
    pipeline_execution_role: Resource
        The IAM role assumed by the pipeline-user to get access to the AWS account and executes the
        CloudFormation stack.
    pipeline_ip_range: Optional[str]
        The IP range (in CIDR format) of the machine running the pipeline instance. If provided, IAM will deny requests
        not coming from this IP range.
        https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_aws_deny-ip.html
    cloudformation_execution_role: Resource
        The IAM role assumed by the CloudFormation service to executes the CloudFormation stack.
    artifacts_bucket: Resource
        The S3 bucket to hold the SAM build artifacts of the application's CFN template.
    create_ecr_repo: bool
        A boolean flag that determins whether the user wants to create an ECR repository or not
    ecr_repo: ECRRepo
        The ECR repo to hold the image container of lambda functions with Image package-type

    Methods:
    --------
    did_user_provide_all_required_resources(self) -> bool:
        checks if all of the stage required resources(pipeline_user, pipeline_execution_role,
        cloudformation_execution_role, artifacts_bucket and ecr_repo) are provided by the user.
    bootstrap(self, confirm_changeset: bool = True) -> None:
        deploys the CFN template ./stage_resources.yaml to the AWS account identified by aws_profile and aws_region
        member fields. if aws_profile is not provided, it will fallback to  default boto3 credentials' resolving.
        Note that ./stage_resources.yaml template accepts the ARNs of already existing resources(if any) as parameters
        and it will skip the creation of those resources but will use the ARNs to set the proper permissions of other
        missing resources(resources created by the template)
    save_config(self, config_dir: str, filename: str, cmd_names: List[str]):
        save the Artifacts bucket name, ECR repo URI and ARNs of pipeline_user, pipeline_execution_role and
        cloudformation_execution_role to the "pipelineconfig.toml" file so that it can be auto-filled during
        the `sam pipeline init` command.
    print_resources_summary(self) -> None:
        prints to the screen(console) the ARNs of the created and provided resources.
    """

    def __init__(
        self,
        name: str,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        pipeline_ip_range: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_ecr_repo: bool = False,
        ecr_repo_arn: Optional[str] = None,
    ) -> None:
        self.name: str = name
        self.aws_profile: Optional[str] = aws_profile
        self.aws_region: Optional[str] = aws_region
        self.pipeline_user: IAMUser = IAMUser(arn=pipeline_user_arn)
        self.pipeline_execution_role: Resource = Resource(arn=pipeline_execution_role_arn)
        self.pipeline_ip_range: Optional[str] = pipeline_ip_range
        self.cloudformation_execution_role: Resource = Resource(arn=cloudformation_execution_role_arn)
        self.artifacts_bucket: Resource = Resource(arn=artifacts_bucket_arn)
        self.create_ecr_repo: bool = create_ecr_repo
        self.ecr_repo: ECRRepo = ECRRepo(arn=ecr_repo_arn)

    def did_user_provide_all_required_resources(self) -> bool:
        """Check if the user provided all of the stage resources or not"""
        return all(resource.is_user_provided for resource in self._get_resources())

    def _get_non_user_provided_resources_msg(self) -> str:
        missing_resources_msg = ""
        if not self.pipeline_user.is_user_provided:
            missing_resources_msg += "\n\tPipeline user"
        if not self.pipeline_execution_role.is_user_provided:
            missing_resources_msg += "\n\tPipeline execution role."
        if not self.cloudformation_execution_role.is_user_provided:
            missing_resources_msg += "\n\tCloudFormation execution role."
        if not self.artifacts_bucket.is_user_provided:
            missing_resources_msg += "\n\tArtifacts bucket."
        if self.create_ecr_repo and not self.ecr_repo.is_user_provided:
            missing_resources_msg += "\n\tECR repo."
        return missing_resources_msg

    def bootstrap(self, confirm_changeset: bool = True) -> bool:
        """
        Deploys the CFN template(./stage_resources.yaml) which deploys:
            * Pipeline IAM User
            * Pipeline execution IAM role
            * CloudFormation execution IAM role
            * Artifacts' S3 Bucket
            * ECR Repo
        to the AWS account associated with the given stage. It will not redeploy the stack if already exists.
        This CFN template accepts the ARNs of the resources as parameters and will not create a resource if already
        provided, this way we can conditionally create a resource only if the user didn't provide it

        THIS METHOD UPDATES THE STATE OF THE CALLING INSTANCE(self) IT WILL SET THE VALUES OF THE RESOURCES ATTRIBUTES

        Parameters
        ----------
        confirm_changeset: bool
            if set to false, the stage_resources.yaml CFN template will directly be deployed, otherwise, the user will
            be prompted for confirmation

        Returns True if bootstrapped, otherwise False
        """

        if self.did_user_provide_all_required_resources():
            click.secho(f"\nAll required resources for the {self.name} stage exist, skipping creation.", fg="yellow")
            return True

        missing_resources_msg: str = self._get_non_user_provided_resources_msg()
        click.echo(
            f"This will create the following required resources for the {self.name} stage: {missing_resources_msg}"
        )
        if confirm_changeset:
            confirmed: bool = click.confirm("Should we proceed with the creation?")
            if not confirmed:
                return False

        sanitized_stage_name: str = re.sub("[^0-9a-zA-Z]+", "-", self.name)
        stack_name: str = f"{STACK_NAME_PREFIX}-{sanitized_stage_name}-{STAGE_RESOURCES_STACK_NAME_SUFFIX}"
        stage_resources_template_body = Stage._read_template(STAGE_RESOURCES_CFN_TEMPLATE)
        output: StackOutput = manage_stack(
            stack_name=stack_name,
            region=self.aws_region,
            profile=self.aws_profile,
            template_body=stage_resources_template_body,
            parameter_overrides={
                "PipelineUserArn": self.pipeline_user.arn or "",
                "PipelineExecutionRoleArn": self.pipeline_execution_role.arn or "",
                "PipelineIpRange": self.pipeline_ip_range or "",
                "CloudFormationExecutionRoleArn": self.cloudformation_execution_role.arn or "",
                "ArtifactsBucketArn": self.artifacts_bucket.arn or "",
                "CreateECRRepo": "true" if self.create_ecr_repo else "false",
                "ECRRepoArn": self.ecr_repo.arn or "",
            },
        )

        self.pipeline_user.arn = output.get("PipelineUser")
        self.pipeline_user.access_key_id = output.get("PipelineUserAccessKeyId")
        self.pipeline_user.secret_access_key = output.get("PipelineUserSecretAccessKey")
        self.pipeline_execution_role.arn = output.get("PipelineExecutionRole")
        self.cloudformation_execution_role.arn = output.get("CloudFormationExecutionRole")
        self.artifacts_bucket.arn = output.get("ArtifactsBucket")
        self.ecr_repo.arn = output.get("ECRRepo")
        return True

    @staticmethod
    def _read_template(template_file_name: str) -> str:
        template_path: str = os.path.join(CFN_TEMPLATE_PATH, template_file_name)
        with open(template_path, "r", encoding="utf-8") as fp:
            template_body = fp.read()
        return template_body

    def save_config(self, config_dir: str, filename: str, cmd_names: List[str]) -> None:
        """
        save the Artifacts bucket name, ECR repo URI and ARNs of pipeline_user, pipeline_execution_role and
        cloudformation_execution_role to the given filename and directory.

        Parameters
        ----------
        config_dir: str
            the directory of the toml file to save to
        filename: str
            the name of the toml file to save to
        cmd_names: List[str]
            nested command name to scope the saved configs to inside the toml file

        Raises
        ------
        ValueError: if the artifacts_bucket or ecr_repo ARNs are invalid
        """

        samconfig: SamConfig = SamConfig(config_dir=config_dir, filename=filename)

        if self.pipeline_user.arn:
            samconfig.put(cmd_names=cmd_names, section="parameters", key=PIPELINE_USER, value=self.pipeline_user.arn)

        # Computing Artifacts bucket name and ECR repo URL may through an exception if the ARNs are wrong
        # Let's swallow such an exception to be able to save the remaining resources
        try:
            artifacts_bucket_name: Optional[str] = self.artifacts_bucket.name()
        except ValueError:
            artifacts_bucket_name = ""
        try:
            ecr_repo_uri: Optional[str] = self.ecr_repo.get_uri()
        except ValueError:
            ecr_repo_uri = ""

        stage_specific_configs: Dict[str, Optional[str]] = {
            PIPELINE_EXECUTION_ROLE: self.pipeline_execution_role.arn,
            CLOUDFORMATION_EXECUTION_ROLE: self.cloudformation_execution_role.arn,
            ARTIFACTS_BUCKET: artifacts_bucket_name,
            ECR_REPO: ecr_repo_uri,
        }

        for key, value in stage_specific_configs.items():
            if value:
                samconfig.put(
                    cmd_names=cmd_names,
                    section="parameters",
                    key=key,
                    value=value,
                    env=self.name,
                )

        samconfig.flush()

    def save_config_safe(self, config_dir: str, filename: str, cmd_names: List[str]) -> None:
        """
        A safe version of save_config method that doesn't raise any exception
        """
        try:
            self.save_config(config_dir, filename, cmd_names)
        except Exception:
            pass

    def _get_resources(self) -> List[Resource]:
        resources = [
            self.pipeline_user,
            self.pipeline_execution_role,
            self.cloudformation_execution_role,
            self.artifacts_bucket,
        ]
        if self.create_ecr_repo:  # ECR Repo is optional
            resources.append(self.ecr_repo)
        return resources

    def print_resources_summary(self) -> None:
        """prints to the screen(console) the ARNs of the created and provided resources."""

        provided_resources = []
        created_resources = []
        for resource in self._get_resources():
            if resource.is_user_provided:
                provided_resources.append(resource)
            else:
                created_resources.append(resource)

        if created_resources:
            click.secho("\nWe have created the following resources:", fg="green")
            for resource in created_resources:
                click.secho(f"\t{resource.arn}", fg="green")

        if provided_resources:
            click.secho(
                "\nYou provided the following resources. Please make sure it has the required permissions as shown at "
                "https://github.com/aws/aws-sam-cli/blob/develop/samcli/lib/pipeline/bootstrap/stage_resources.yaml",
                fg="green",
            )
            for resource in provided_resources:
                click.secho(f"\t{resource.arn}", fg="green")

        if not self.pipeline_user.is_user_provided:
            click.secho(
                "Please configure your CI/CD project with the following pipeline user credentials and "
                "make sure to periodically rotate it:",
                fg="green",
            )
            click.secho(f"\tACCESS_KEY_ID: {self.pipeline_user.access_key_id}", fg="green")
            click.secho(f"\tSECRET_ACCESS_KEY: {self.pipeline_user.secret_access_key}", fg="green")
