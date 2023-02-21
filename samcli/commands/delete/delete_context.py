"""
Delete a SAM stack
"""
import json
import logging
from typing import Optional

import boto3
import click
from click import confirm, prompt

from samcli.cli.cli_config_file import TomlProvider
from samcli.cli.context import Context
from samcli.commands.delete.exceptions import CfDeleteFailedStatusError
from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStack
from samcli.lib.delete.cfn_utils import CfnUtils
from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.uploaders import Uploaders
from samcli.lib.utils.boto_utils import get_boto_config_with_user_agent

CONFIG_COMMAND = "deploy"
CONFIG_SECTION = "parameters"
TEMPLATE_STAGE = "Original"

LOG = logging.getLogger(__name__)


class DeleteContext:
    # TODO: Separate this context into 2 separate contexts guided and non-guided, just like deploy.
    def __init__(
        self,
        stack_name: str,
        region: str,
        profile: str,
        config_file: str,
        config_env: str,
        no_prompts: bool,
        s3_bucket: Optional[str],
        s3_prefix: Optional[str],
    ):
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        self.config_file = config_file
        self.config_env = config_env
        self.no_prompts = no_prompts
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.cf_utils = None
        self.s3_uploader = None
        self.ecr_uploader = None
        self.uploaders = None
        self.cf_template_file_name = None
        self.delete_artifacts_folder = None
        self.delete_cf_template_file = None
        self.companion_stack_name = None

    def __enter__(self):
        self.parse_config_file()
        if not self.stack_name:
            LOG.debug("No stack-name input found")
            if not self.no_prompts:
                self.stack_name = prompt(
                    click.style("\tEnter stack name you want to delete", bold=True), type=click.STRING
                )
            else:
                raise click.BadOptionUsage(
                    option_name="--stack-name",
                    message="Missing option '--stack-name', provide a stack name that needs to be deleted.",
                )

        self.init_clients()
        return self

    def __exit__(self, *args):
        pass

    def parse_config_file(self):
        """
        Read the provided config file if it exists and assign the options values.
        """
        toml_provider = TomlProvider(CONFIG_SECTION, [CONFIG_COMMAND])
        config_options = toml_provider(
            config_path=self.config_file, config_env=self.config_env, cmd_names=[CONFIG_COMMAND]
        )
        if not config_options:
            return

        if not self.stack_name:
            self.stack_name = config_options.get("stack_name", None)
        # If the stack_name is same as the one present in samconfig file,
        # get the information about parameters if not specified by user.
        if self.stack_name and self.stack_name == config_options.get("stack_name", None):
            LOG.debug("Local config present and using the defined options")
            if not self.region:
                self.region = config_options.get("region", None)
            if not self.profile:
                self.profile = config_options.get("profile", None)
            if not self.s3_bucket:
                self.s3_bucket = config_options.get("s3_bucket", None)
            if not self.s3_prefix:
                self.s3_prefix = config_options.get("s3_prefix", None)

    def init_clients(self):
        """
        Initialize all the clients being used by sam delete.
        """
        if not self.region:
            if not self.no_prompts:
                session = boto3.Session()
                region = session.region_name
                self.region = region if region else "us-east-1"
            else:
                # TODO: as part of the guided and non-guided context separation, we need also to move the options
                # validations to a validator similar to samcli/lib/cli_validation/image_repository_validation.py.
                raise click.BadOptionUsage(
                    option_name="--region",
                    message="Missing option '--region', region is required to run the non guided delete command.",
                )

        if self.profile:
            Context.get_current_context().profile = self.profile
        if self.region:
            Context.get_current_context().region = self.region

        boto_config = get_boto_config_with_user_agent()

        # Define cf_client based on the region as different regions can have same stack-names
        cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

        s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)
        ecr_client = boto3.client("ecr", region_name=self.region if self.region else None, config=boto_config)

        self.s3_uploader = S3Uploader(s3_client=s3_client, bucket_name=self.s3_bucket, prefix=self.s3_prefix)

        self.ecr_uploader = ECRUploader(docker_client=None, ecr_client=ecr_client, ecr_repo=None, ecr_repo_multi=None)

        self.uploaders = Uploaders(self.s3_uploader, self.ecr_uploader)
        self.cf_utils = CfnUtils(cloudformation_client)

    def s3_prompts(self):
        """
        Guided prompts asking user to delete s3 artifacts
        """
        # Note: s3_bucket and s3_prefix information is only
        # available if it is provided as an option flag, a
        # local toml file or if this information is obtained
        # from the template resources and so if this
        # information is not found, warn the user that S3 artifacts
        # will need to be manually deleted.

        if not self.no_prompts and self.s3_bucket:
            if self.s3_prefix:
                self.delete_artifacts_folder = confirm(
                    click.style(
                        "\tAre you sure you want to delete the folder"
                        f" {self.s3_prefix} in S3 which contains the artifacts?",
                        bold=True,
                    ),
                    default=False,
                )
            if not self.delete_artifacts_folder:
                LOG.debug("S3 prefix not present or user does not want to delete the prefix folder")
                self.delete_cf_template_file = confirm(
                    click.style(
                        "\tDo you want to delete the template file" + f" {self.cf_template_file_name} in S3?", bold=True
                    ),
                    default=False,
                )
        elif self.s3_bucket:
            if self.s3_prefix:
                self.delete_artifacts_folder = True
            else:
                self.delete_cf_template_file = True

    def ecr_companion_stack_prompts(self):
        """
        User prompt to delete the ECR companion stack.
        """
        click.echo(f"\tFound ECR Companion Stack {self.companion_stack_name}")
        if self.no_prompts:
            return True

        return confirm(
            click.style(
                "\tDo you you want to delete the ECR companion stack"
                f" {self.companion_stack_name} in the region {self.region} ?",
                bold=True,
            ),
            default=False,
        )

    def ecr_repos_prompts(self, template: Template):
        """
        User prompts to delete the ECR repositories for the given template.

        :param template: Template to get the ECR repositories.
        """
        retain_repos = []
        ecr_repos = template.get_ecr_repos()

        if not self.no_prompts:
            for logical_id in ecr_repos:
                # Get all the repos from the companion stack
                repo = ecr_repos[logical_id]
                repo_name = repo["Repository"]

                delete_repo = confirm(
                    click.style(
                        f"\tECR repository {repo_name}"
                        " may not be empty. Do you want to delete the repository and all the images in it ?",
                        bold=True,
                    ),
                    default=False,
                )
                if not delete_repo:
                    retain_repos.append(logical_id)
        return retain_repos

    def delete_ecr_companion_stack(self):
        """
        Delete the ECR companion stack and ECR repositories based
        on user input.
        """
        delete_ecr_companion_stack_prompt = self.ecr_companion_stack_prompts()
        if delete_ecr_companion_stack_prompt or self.no_prompts:
            cf_ecr_companion_stack = self.cf_utils.get_stack_template(self.companion_stack_name, TEMPLATE_STAGE)
            ecr_stack_template_str = cf_ecr_companion_stack.get("TemplateBody", None)
            ecr_stack_template_str = json.dumps(ecr_stack_template_str, indent=4, ensure_ascii=False)

            ecr_companion_stack_template = Template(
                template_path=None,
                parent_dir=None,
                uploaders=self.uploaders,
                code_signer=None,
                template_str=ecr_stack_template_str,
            )

            retain_repos = self.ecr_repos_prompts(ecr_companion_stack_template)
            # Delete the repos created by ECR companion stack if not retained
            ecr_companion_stack_template.delete(retain_resources=retain_repos)

            click.echo(f"\t- Deleting ECR Companion Stack {self.companion_stack_name}")
            try:
                # If delete_stack fails and its status changes to DELETE_FAILED, retain
                # the user input repositories and delete the stack.
                self.cf_utils.delete_stack(stack_name=self.companion_stack_name)
                self.cf_utils.wait_for_delete(stack_name=self.companion_stack_name)
                LOG.debug("Deleted ECR Companion Stack: %s", self.companion_stack_name)

            except CfDeleteFailedStatusError:
                LOG.debug("delete_stack resulted failed and so re-try with retain_resources")
                self.cf_utils.delete_stack(stack_name=self.companion_stack_name, retain_resources=retain_repos)
                self.cf_utils.wait_for_delete(stack_name=self.companion_stack_name)

    def delete(self):
        """
        Delete method calls for Cloudformation stacks and S3 and ECR artifacts
        """
        # Fetch the template using the stack-name
        cf_template = self.cf_utils.get_stack_template(self.stack_name, TEMPLATE_STAGE)
        template_str = cf_template.get("TemplateBody", None)

        if isinstance(template_str, dict):
            template_str = json.dumps(template_str, indent=4, ensure_ascii=False)

        # Get the cloudformation template name using template_str
        self.cf_template_file_name = get_uploaded_s3_object_name(file_content=template_str, extension="template")

        template = Template(
            template_path=None,
            parent_dir=None,
            uploaders=self.uploaders,
            code_signer=None,
            template_str=template_str,
        )

        # If s3 info is not available, try to obtain it from CF
        # template resources.
        if not self.s3_bucket:
            s3_info = template.get_s3_info()
            self.s3_bucket = s3_info["s3_bucket"]
            self.s3_uploader.bucket_name = self.s3_bucket

            self.s3_prefix = s3_info["s3_prefix"]
            self.s3_uploader.prefix = self.s3_prefix

        self.s3_prompts()

        retain_resources = self.ecr_repos_prompts(template)

        # ECR companion stack delete prompts, if it exists
        companion_stack = CompanionStack(self.stack_name)

        ecr_companion_stack_exists = self.cf_utils.has_stack(stack_name=companion_stack.stack_name)
        if ecr_companion_stack_exists:
            LOG.debug("ECR Companion stack found for the input stack")
            self.companion_stack_name = companion_stack.stack_name
            self.delete_ecr_companion_stack()

        # Delete the artifacts and retain resources user selected not to delete
        template.delete(retain_resources=retain_resources)

        # Delete the CF template file in S3
        if self.delete_cf_template_file:
            self.s3_uploader.delete_artifact(remote_path=self.cf_template_file_name)

        # Delete the folder of artifacts if s3_bucket and s3_prefix provided
        elif self.delete_artifacts_folder:
            self.s3_uploader.delete_prefix_artifacts()

        # Delete the primary input stack
        try:
            click.echo(f"\t- Deleting Cloudformation stack {self.stack_name}")
            self.cf_utils.delete_stack(stack_name=self.stack_name)
            self.cf_utils.wait_for_delete(self.stack_name)
            LOG.debug("Deleted Cloudformation stack: %s", self.stack_name)

        except CfDeleteFailedStatusError:
            LOG.debug("delete_stack resulted failed and so re-try with retain_resources")
            self.cf_utils.delete_stack(stack_name=self.stack_name, retain_resources=retain_resources)
            self.cf_utils.wait_for_delete(self.stack_name)

        # Warn the user that s3 information is missing and to use --s3 options
        if not self.s3_bucket:
            LOG.debug("Cannot delete s3 objects as bucket is missing")
            click.secho(
                "\nWarning: Cannot resolve s3 bucket information from command options"
                " , local config file or cloudformation template. Please use"
                " --s3-bucket next time and"
                " delete s3 files manually if required.",
                fg="yellow",
            )

    def run(self):
        """
        Delete the stack based on the argument provided by user and samconfig.toml.
        """
        if not self.no_prompts:
            delete_stack = confirm(
                click.style(
                    f"\tAre you sure you want to delete the stack {self.stack_name}" f" in the region {self.region} ?",
                    bold=True,
                ),
                default=False,
            )

        if self.no_prompts or delete_stack:
            is_deployed = self.cf_utils.has_stack(stack_name=self.stack_name)
            # Check if the provided stack-name exists
            if is_deployed:
                LOG.debug("Input stack is deployed, continue deleting")
                self.delete()
                click.echo("\nDeleted successfully")
            else:
                LOG.debug("Input stack does not exists on Cloudformation")
                click.echo(
                    f"Error: The input stack {self.stack_name} does"
                    f" not exist on Cloudformation in the region {self.region}"
                )
