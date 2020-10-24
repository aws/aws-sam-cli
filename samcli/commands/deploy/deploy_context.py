"""
Deploy a SAM stack
"""

# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import logging
import os

import boto3
import click

from samcli.commands._utils.template import get_template_data
from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.commands.deploy.auth_utils import auth_per_resource
from samcli.commands.deploy.utils import sanitize_parameter_overrides, print_deploy_args
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.botoconfig import get_boto_config_with_user_agent
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)


class DeployContext:

    MSG_SHOWCASE_CHANGESET = "\nChangeset created successfully. {changeset_id}\n"

    MSG_EXECUTE_SUCCESS = "\nSuccessfully created/updated stack - {stack_name} in {region}\n"

    MSG_CONFIRM_CHANGESET = "Deploy this changeset?"
    MSG_CONFIRM_CHANGESET_HEADER = "\nPreviewing CloudFormation changeset before deployment"

    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        force_upload,
        no_progressbar,
        s3_prefix,
        kms_key_id,
        parameter_overrides,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        fail_on_empty_changeset,
        tags,
        region,
        profile,
        confirm_changeset,
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.force_upload = force_upload
        self.no_progressbar = no_progressbar
        self.s3_prefix = s3_prefix
        self.kms_key_id = kms_key_id
        self.parameter_overrides = parameter_overrides
        self.capabilities = capabilities
        self.no_execute_changeset = no_execute_changeset
        self.role_arn = role_arn
        self.notification_arns = notification_arns
        self.fail_on_empty_changeset = fail_on_empty_changeset
        self.tags = tags
        self.region = region
        self.profile = profile
        self.s3_uploader = None
        self.deployer = None
        self.confirm_changeset = confirm_changeset

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):

        # Parse parameters
        with open(self.template_file, "r") as handle:
            template_str = handle.read()

        template_dict = yaml_parse(template_str)

        if not isinstance(template_dict, dict):
            raise deploy_exceptions.DeployFailedError(
                stack_name=self.stack_name, msg="{} not in required format".format(self.template_file)
            )

        parameters = self.merge_parameters(template_dict, self.parameter_overrides)

        template_size = os.path.getsize(self.template_file)
        if template_size > 51200 and not self.s3_bucket:
            raise deploy_exceptions.DeployBucketRequiredError()
        boto_config = get_boto_config_with_user_agent()
        cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

        s3_client = None
        if self.s3_bucket:
            s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)

            self.s3_uploader = S3Uploader(
                s3_client, self.s3_bucket, self.s3_prefix, self.kms_key_id, self.force_upload, self.no_progressbar
            )

        self.deployer = Deployer(cloudformation_client)

        region = s3_client._client_config.region_name if s3_client else self.region  # pylint: disable=W0212
        print_deploy_args(
            self.stack_name,
            self.s3_bucket,
            region,
            self.capabilities,
            self.parameter_overrides,
            self.confirm_changeset,
        )
        return self.deploy(
            self.stack_name,
            template_str,
            parameters,
            self.capabilities,
            self.no_execute_changeset,
            self.role_arn,
            self.notification_arns,
            self.s3_uploader,
            [{"Key": key, "Value": value} for key, value in self.tags.items()] if self.tags else [],
            region,
            self.fail_on_empty_changeset,
            self.confirm_changeset,
        )

    def deploy(
        self,
        stack_name,
        template_str,
        parameters,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        s3_uploader,
        tags,
        region,
        fail_on_empty_changeset=True,
        confirm_changeset=False,
    ):

        auth_required_per_resource = auth_per_resource(
            sanitize_parameter_overrides(self.parameter_overrides), get_template_data(self.template_file)
        )

        for resource, authorization_required in auth_required_per_resource:
            if not authorization_required:
                click.secho(f"{resource} may not have authorization defined.", fg="yellow")

        try:
            result, changeset_type = self.deployer.create_and_wait_for_changeset(
                stack_name=stack_name,
                cfn_template=template_str,
                parameter_values=parameters,
                capabilities=capabilities,
                role_arn=role_arn,
                notification_arns=notification_arns,
                s3_uploader=s3_uploader,
                tags=tags,
            )
            click.echo(self.MSG_SHOWCASE_CHANGESET.format(changeset_id=result["Id"]))

            if no_execute_changeset:
                return

            if confirm_changeset:
                click.secho(self.MSG_CONFIRM_CHANGESET_HEADER, fg="yellow")
                click.secho("=" * len(self.MSG_CONFIRM_CHANGESET_HEADER), fg="yellow")
                if not click.confirm(f"{self.MSG_CONFIRM_CHANGESET}", default=False):
                    return

            self.deployer.execute_changeset(result["Id"], stack_name)
            self.deployer.wait_for_execute(stack_name, changeset_type)
            click.echo(self.MSG_EXECUTE_SUCCESS.format(stack_name=stack_name, region=region))

        except deploy_exceptions.ChangeEmptyError as ex:
            if fail_on_empty_changeset:
                raise
            click.echo(str(ex))

    def merge_parameters(self, template_dict, parameter_overrides):
        """
        CloudFormation CreateChangeset requires a value for every parameter
        from the template, either specifying a new value or use previous value.
        For convenience, this method will accept new parameter values and
        generates a dict of all parameters in a format that ChangeSet API
        will accept

        :param parameter_overrides:
        :return:
        """
        parameter_values = []

        if not isinstance(template_dict.get("Parameters", None), dict):
            return parameter_values

        for key, _ in template_dict["Parameters"].items():

            obj = {"ParameterKey": key}

            if key in parameter_overrides:
                obj["ParameterValue"] = parameter_overrides[key]
            else:
                obj["UsePreviousValue"] = True

            parameter_values.append(obj)

        return parameter_values
