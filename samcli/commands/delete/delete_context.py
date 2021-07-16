"""
Delete a SAM stack
"""
import logging
from typing import Dict
import json
import boto3


import click
from click import confirm
from click import prompt

from samcli.lib.utils.hash import str_checksum
from samcli.cli.cli_config_file import TomlProvider
from samcli.lib.utils.botoconfig import get_boto_config_with_user_agent
from samcli.lib.delete.cf_utils import CfUtils

from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.artifact_exporter import mktempfile, get_cf_template_name

from samcli.lib.schemas.schemas_aws_config import get_aws_configuration_choice
from samcli.cli.context import Context

from samcli.commands.delete.exceptions import CfDeleteFailedStatusError

from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.uploaders import Uploaders

CONFIG_COMMAND = "deploy"
CONFIG_SECTION = "parameters"
TEMPLATE_STAGE = "Original"

LOG = logging.getLogger(__name__)


class DeleteContext:

    ecr_repos: Dict[str, Dict[str, str]]

    def __init__(self, stack_name: str, region: str, profile: str, config_file: str, config_env: str, no_prompts: bool):
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        self.config_file = config_file
        self.config_env = config_env
        self.no_prompts = no_prompts
        self.s3_bucket = None
        self.s3_prefix = None
        self.cf_utils = None
        self.s3_uploader = None
        self.ecr_uploader = None
        self.uploaders = None
        self.cf_template_file_name = None
        self.delete_artifacts_folder = None
        self.delete_cf_template_file = None
        self.companion_stack_name = None
        self.delete_ecr_companion_stack_prompt = None
        self.ecr_repos = {}

    def __enter__(self):
        self.parse_config_file()
        if not self.stack_name:
            LOG.debug("No stack-name input found")
            self.stack_name = prompt(
                click.style("\tEnter stack name you want to delete:", bold=True), type=click.STRING
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
        if config_options:
            if not self.stack_name:
                self.stack_name = config_options.get("stack_name", None)
            # If the stack_name is same as the one present in samconfig file,
            # get the information about parameters if not specified by customer.
            if self.stack_name and self.stack_name == config_options.get("stack_name", None):
                LOG.debug("Local config present and using the defined options")
                if not self.region:
                    self.region = config_options.get("region", None)
                    Context.get_current_context().region = self.region
                if not self.profile:
                    self.profile = config_options.get("profile", None)
                    Context.get_current_context().profile = self.profile
                self.s3_bucket = config_options.get("s3_bucket", None)
                self.s3_prefix = config_options.get("s3_prefix", None)

    def init_clients(self):
        """
        Initialize all the clients being used by sam delete.
        """
        if not self.region:
            aws_config = get_aws_configuration_choice()
            self.region = aws_config["region"]
            self.profile = aws_config["profile"]
            Context.get_current_context().region = self.region
            Context.get_current_context().profile = self.profile

        boto_config = get_boto_config_with_user_agent()

        # Define cf_client based on the region as different regions can have same stack-names
        cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )
        cloudformation_resource_client = boto3.resource(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

        s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)
        ecr_client = boto3.client("ecr", region_name=self.region if self.region else None, config=boto_config)

        self.s3_uploader = S3Uploader(s3_client=s3_client, bucket_name=self.s3_bucket, prefix=self.s3_prefix)

        self.ecr_uploader = ECRUploader(docker_client=None, ecr_client=ecr_client, ecr_repo=None, ecr_repo_multi=None)

        self.uploaders = Uploaders(self.s3_uploader, self.ecr_uploader)
        self.cf_utils = CfUtils(cloudformation_client, cloudformation_resource_client)

    def guided_prompts(self):
        """
        Guided prompts asking customer to delete artifacts
        """
        # Note: s3_bucket and s3_prefix information is only
        # available if a local toml file is present or if
        # this information is obtained from the template resources and so if this
        # information is not found, warn the customer that S3 artifacts
        # will need to be manually deleted.

        if not self.no_prompts and self.s3_bucket:
            if self.s3_prefix:
                self.delete_artifacts_folder = confirm(
                    click.style(
                        "\tAre you sure you want to delete the folder"
                        + f" {self.s3_prefix} in S3 which contains the artifacts?",
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

        if not self.no_prompts:
            self.delete_ecr_companion_stack_prompt = confirm(
                click.style(
                    "\tDo you you want to delete the ECR companion stack"
                    + f" {self.companion_stack_name} in the region {self.region} ?",
                    bold=True,
                ),
                default=False,
            )

    def ecr_repos_prompts(self):
        """
        User prompts to delete the ECR repositories.
        """
        if self.no_prompts or self.delete_ecr_companion_stack_prompt:
            self.ecr_repos = self.cf_utils.get_deployed_repos(stack_name=self.companion_stack_name)
            if self.ecr_repos:
                click.echo("\t#Note: Empty repositories created by SAM CLI will be deleted automatically.")

            for logical_id in self.ecr_repos:
                # Get all the repos from the companion stack
                repo = self.ecr_repos[logical_id]
                repo_physical_id = repo["physical_id"]
                if self.delete_ecr_companion_stack_prompt:
                    delete_repo = confirm(
                        click.style(
                            f"\tECR repository {repo_physical_id}"
                            + " may not be empty. Do you want to delete the repository and all the images in it ?",
                            bold=True,
                        ),
                        default=False,
                    )
                    repo["delete_repo"] = delete_repo

    def delete_ecr_repos(self):
        """
        Delete the ECR repositories and return the repositories
        that the user wants to retain.
        """
        retain_repos = []
        for logical_id in self.ecr_repos:
            repo = self.ecr_repos[logical_id]
            physical_id = repo["physical_id"]
            is_delete = repo.get("delete_repo", None)
            if self.no_prompts or is_delete:
                click.echo(f"\t- Deleting ECR repository {physical_id}")
                self.ecr_uploader.delete_ecr_repository(physical_id=physical_id)
            else:
                retain_repos.append(logical_id)
        return retain_repos

    def delete(self):
        """
        Delete method calls for Cloudformation stacks and S3 and ECR artifacts
        """
        # Fetch the template using the stack-name
        cf_template = self.cf_utils.get_stack_template(self.stack_name, TEMPLATE_STAGE)
        template_str = cf_template.get("TemplateBody", None)

        ecr_companion_stack_exists = False
        if isinstance(template_str, dict):
            metadata_stack_name = template_str.get("Metadata", {}).get("CompanionStackname", None)
            # Check if the input stack is ecr companion stack
            if metadata_stack_name == self.stack_name:
                LOG.debug("Input stack name is ecr companion stack for an unknown stack")
                ecr_companion_stack_exists = True
                self.companion_stack_name = self.stack_name

                if not self.no_prompts:
                    self.delete_ecr_companion_stack_prompt = True

            template_str = json.dumps(template_str, indent=4, ensure_ascii=False)

        # Get the cloudformation template name using template_str
        with mktempfile() as temp_file:
            self.cf_template_file_name = get_cf_template_name(temp_file, template_str, "template")

        self.guided_prompts()

        # If the input stack name is ecr companion stack, skip the below steps
        if not ecr_companion_stack_exists:

            # ECR companion stack delete prompts, if it exists
            parent_stack_hash = str_checksum(self.stack_name)
            possible_companion_stack_name = f"{self.stack_name[:104]}-{parent_stack_hash[:8]}-CompanionStack"
            ecr_companion_stack_exists = self.cf_utils.has_stack(stack_name=possible_companion_stack_name)
            if ecr_companion_stack_exists:
                LOG.debug("ECR Companion stack found for the input stack")
                self.companion_stack_name = possible_companion_stack_name
                self.ecr_companion_stack_prompts()
                self.ecr_repos_prompts()

            # Delete the primary stack
            click.echo(f"\n\t- Deleting Cloudformation stack {self.stack_name}")
            self.cf_utils.delete_stack(stack_name=self.stack_name)
            self.cf_utils.wait_for_delete(self.stack_name)
            LOG.debug("Deleted Cloudformation stack: %s", self.stack_name)

            # Delete the artifacts
            template = Template(
                template_path=None,
                parent_dir=None,
                uploaders=self.uploaders,
                code_signer=None,
                template_str=template_str,
            )
            template.delete()

        else:
            self.ecr_repos_prompts()

        # Delete the CF template file in S3
        if self.delete_cf_template_file:
            self.s3_uploader.delete_artifact(remote_path=self.cf_template_file_name)

        # Delete the folder of artifacts if s3_bucket and s3_prefix provided
        elif self.delete_artifacts_folder:
            self.s3_uploader.delete_prefix_artifacts()

        # Delete the repos created by ECR companion stack and the stack if it exists
        if ecr_companion_stack_exists and (self.no_prompts or self.delete_ecr_companion_stack_prompt):
            retain_repos = self.delete_ecr_repos()

            click.echo(f"\t- Deleting ECR Companion Stack {self.companion_stack_name}")
            try:
                # If delete_stack fails and its status changes to DELETE_FAILED, retain
                # the user input repositories and delete the stack.
                self.cf_utils.delete_stack(stack_name=self.companion_stack_name)
                self.cf_utils.wait_for_delete(stack_name=self.companion_stack_name)
            except CfDeleteFailedStatusError:
                LOG.debug("delete_stack resulted failed and so re-try with retain_resources")
                self.cf_utils.delete_stack(stack_name=self.companion_stack_name, retain_repos=retain_repos)

        # If s3_bucket information is not available, warn the user
        if not self.s3_bucket:
            LOG.debug("Cannot delete s3 files as no s3_bucket found")
            click.secho(
                "\nWarning: s3_bucket and s3_prefix information could not be obtained from local config file"
                " or cloudformation template, delete the s3 files manually if required",
                fg="yellow",
            )

    def run(self):
        """
        Delete the stack based on the argument provided by customers and samconfig.toml.
        """
        if not self.no_prompts:
            delete_stack = confirm(
                click.style(
                    f"\tAre you sure you want to delete the stack {self.stack_name}"
                    + f" in the region {self.region} ?",
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
                    + f" not exist on Cloudformation in the region {self.region}"
                )
