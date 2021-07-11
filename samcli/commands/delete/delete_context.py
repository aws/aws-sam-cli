"""
Delete a SAM stack
"""
import logging
import boto3


import click
from click import confirm
from click import prompt
from samcli.cli.cli_config_file import TomlProvider
from samcli.lib.utils.botoconfig import get_boto_config_with_user_agent
from samcli.lib.delete.cf_utils import CfUtils
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.artifact_exporter import mktempfile, get_cf_template_name


from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.uploaders import Uploaders

CONFIG_COMMAND = "deploy"
CONFIG_SECTION = "parameters"
TEMPLATE_STAGE = "Original"

LOG = logging.getLogger(__name__)


class DeleteContext:
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
        self.uploaders = None
        self.cf_template_file_name = None
        self.delete_artifacts_folder = None
        self.delete_cf_template_file = None

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
                    click.get_current_context().region = self.region
                if not self.profile:
                    self.profile = config_options.get("profile", None)
                    click.get_current_context().profile = self.profile
                self.s3_bucket = config_options.get("s3_bucket", None)
                self.s3_prefix = config_options.get("s3_prefix", None)

    def init_clients(self):
        """
        Initialize all the clients being used by sam delete.
        """
        boto_config = get_boto_config_with_user_agent()

        # Define cf_client based on the region as different regions can have same stack-names
        cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

        s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)
        ecr_client = boto3.client("ecr", region_name=self.region if self.region else None, config=boto_config)

        self.region = s3_client._client_config.region_name if s3_client else self.region  # pylint: disable=W0212
        self.s3_uploader = S3Uploader(s3_client=s3_client, bucket_name=self.s3_bucket, prefix=self.s3_prefix)

        ecr_uploader = ECRUploader(docker_client=None, ecr_client=ecr_client, ecr_repo=None, ecr_repo_multi=None)

        self.uploaders = Uploaders(self.s3_uploader, ecr_uploader)
        self.cf_utils = CfUtils(cloudformation_client)

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

    def delete(self):
        """
        Delete method calls for Cloudformation stacks and S3 and ECR artifacts
        """
        # Fetch the template using the stack-name
        cf_template = self.cf_utils.get_stack_template(self.stack_name, TEMPLATE_STAGE)
        template_str = cf_template.get("TemplateBody", None)

        # Get the cloudformation template name using template_str
        with mktempfile() as temp_file:
            self.cf_template_file_name = get_cf_template_name(temp_file, template_str, "template")

        template = Template(
            template_path=None, parent_dir=None, uploaders=self.uploaders, code_signer=None, template_str=template_str
        )

        # If s3 info is not available, try to obtain it from CF
        # template resources.
        if not self.s3_bucket:
            s3_info = template.get_s3_info()
            self.s3_bucket = s3_info["s3_bucket"]
            self.s3_uploader.bucket_name = self.s3_bucket

            self.s3_prefix = s3_info["s3_prefix"]
            self.s3_uploader.prefix = self.s3_prefix

        self.guided_prompts()

        # Delete the primary stack
        click.echo(f"\n\t- Deleting Cloudformation stack {self.stack_name}")
        self.cf_utils.delete_stack(stack_name=self.stack_name)
        self.cf_utils.wait_for_delete(self.stack_name)
        LOG.debug("Deleted Cloudformation stack: %s", self.stack_name)

        # Delete the artifacts
        template.delete()

        # Delete the CF template file in S3
        if self.delete_cf_template_file:
            self.s3_uploader.delete_artifact(remote_path=self.cf_template_file_name)

        # Delete the folder of artifacts if s3_bucket and s3_prefix provided
        elif self.delete_artifacts_folder:
            self.s3_uploader.delete_prefix_artifacts()

        # If s3_bucket information is not available
        elif not self.s3_bucket:
            LOG.debug("Cannot delete s3 files as no s3_bucket found")
            click.secho(
                "\nWarning: s3_bucket and s3_prefix information cannot be obtained,"
                " delete the files manually if required",
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
                click.echo(f"Error: The input stack {self.stack_name} does not exist on Cloudformation")
