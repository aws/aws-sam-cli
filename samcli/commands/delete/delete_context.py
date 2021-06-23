"""
Delete a SAM stack
"""

import boto3
import docker
import click
from click import confirm
from click import prompt

from samcli.lib.utils.botoconfig import get_boto_config_with_user_agent
from samcli.lib.delete.cf_utils import CfUtils
from samcli.lib.delete.utils import get_cf_template_name
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.yamlhelper import yaml_parse

# Intentionally commented
# from samcli.lib.package.artifact_exporter import Template
# from samcli.lib.package.ecr_uploader import ECRUploader
# from samcli.lib.package.uploaders import Uploaders


class DeleteContext:
    def __init__(self, stack_name, region, s3_bucket, s3_prefix, profile):
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.cf_utils = None
        self.start_bold = "\033[1m"
        self.end_bold = "\033[0m"
        self.s3_uploader = None
        # self.uploaders = None
        self.cf_template_file_name = None
        self.delete_artifacts_folder = None
        self.delete_cf_template_file = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):
        """
        Delete the stack based on the argument provided by customers and samconfig.toml.
        """
        if not self.stack_name:
            self.stack_name = prompt(
                f"\t{self.start_bold}Enter stack name you want to delete{self.end_bold}", type=click.STRING
            )

        if not self.region:
            self.region = prompt(
                f"\t{self.start_bold}Enter region you want to delete from{self.end_bold}", type=click.STRING
            )
        delete_stack = confirm(
            f"\t{self.start_bold}Are you sure you want to delete the stack {self.stack_name}?{self.end_bold}",
            default=False,
        )
        # Fetch the template using the stack-name
        if delete_stack and self.region:
            boto_config = get_boto_config_with_user_agent()

            # Define cf_client based on the region as different regions can have same stack-names
            cloudformation_client = boto3.client(
                "cloudformation", region_name=self.region if self.region else None, config=boto_config
            )

            s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)
            ecr_client = boto3.client("ecr", region_name=self.region if self.region else None, config=boto_config)

            self.s3_uploader = S3Uploader(s3_client=s3_client, bucket_name=self.s3_bucket, prefix=self.s3_prefix)

            docker_client = docker.from_env()
            ecr_uploader = ECRUploader(docker_client, ecr_client, None, None)

            self.cf_utils = CfUtils(cloudformation_client)

            is_deployed = self.cf_utils.has_stack(self.stack_name)

            if is_deployed:
                template_str = self.cf_utils.get_stack_template(self.stack_name, "Original")

                template_dict = yaml_parse(template_str)

                if self.s3_bucket and self.s3_prefix:
                    self.delete_artifacts_folder = confirm(
                        f"\t{self.start_bold}Are you sure you want to delete the folder {self.s3_prefix} \
                          in S3 which contains the artifacts?{self.end_bold}",
                          default=False,
                    )
                    if not self.delete_artifacts_folder:
                        self.cf_template_file_name = get_cf_template_name(template_str, "template")
                        delete_cf_template_file = confirm(
                            f"\t{self.start_bold}Do you want to delete the template file \
                             {self.cf_template_file_name} in S3?{self.end_bold}",
                             default=False,
                        )

                click.echo("\n")
                # Delete the primary stack
                self.cf_utils.delete_stack(self.stack_name)

                click.echo("- deleting Cloudformation stack {0}".format(self.stack_name))

                # Delete the artifacts
                # Intentionally commented
                # self.uploaders = Uploaders(self.s3_uploader, ecr_uploader)
                # template = Template(None, None, self.uploaders, None)
                # template.delete(template_dict)

                # Delete the CF template file in S3
                if self.delete_cf_template_file:
                    self.s3_uploader.delete_artifact(self.cf_template_file_name)

                # Delete the folder of artifacts if s3_bucket and s3_prefix provided
                elif self.delete_artifacts_folder:
                    self.s3_uploader.delete_prefix_artifacts()

                # Delete the ECR companion stack

                if self.cf_template_file_name:
                    click.echo("- deleting template file {0}".format(self.cf_template_file))
                click.echo("\n")
                click.echo("delete complete")
            else:
                click.echo("Error: The input stack {0} does not exist on Cloudformation".format(self.stack_name))
