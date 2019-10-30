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

import os
import logging
import boto3
import click

from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)


class DeployContext(object):

    MSG_NO_EXECUTE_CHANGESET = "Changeset created successfully. \n"

    MSG_EXECUTE_SUCCESS = "Successfully created/updated stack - {stack_name}\n"

    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        force_upload,
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
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.force_upload = force_upload
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):

        session = boto3.Session(profile_name=self.profile if self.profile else None)
        cloudformation_client = session.client("cloudformation", region_name=self.region if self.region else None)

        # Parse parameters
        with open(self.template_file, "r") as handle:
            template_str = handle.read()

        template_dict = yaml_parse(template_str)

        parameters = self.merge_parameters(template_dict, self.parameter_overrides)

        template_size = os.path.getsize(self.template_file)
        if template_size > 51200 and not self.s3_bucket:
            raise deploy_exceptions.DeployBucketRequiredError()

        if self.s3_bucket:
            s3_client = session.client("s3", region_name=self.region if self.region else None)

            self.s3_uploader = S3Uploader(s3_client, self.s3_bucket, self.s3_prefix, self.kms_key_id, self.force_upload)

        deployer = Deployer(cloudformation_client)

        return self.deploy(
            deployer,
            self.stack_name,
            template_str,
            parameters,
            self.capabilities,
            self.no_execute_changeset,
            self.role_arn,
            self.notification_arns,
            self.s3_uploader,
            [{"Key": key, "Value": value} for key, value in self.tags.items()],
            self.fail_on_empty_changeset,
        )

    def deploy(
        self,
        deployer,
        stack_name,
        template_str,
        parameters,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        s3_uploader,
        tags,
        fail_on_empty_changeset=True,
    ):
        try:
            result, changeset_type = deployer.create_and_wait_for_changeset(
                stack_name=stack_name,
                cfn_template=template_str,
                parameter_values=parameters,
                capabilities=capabilities,
                role_arn=role_arn,
                notification_arns=notification_arns,
                s3_uploader=s3_uploader,
                tags=tags,
            )

            if not no_execute_changeset:
                deployer.execute_changeset(result["Id"], stack_name)
                deployer.wait_for_execute(stack_name, changeset_type)
                click.echo(self.MSG_EXECUTE_SUCCESS.format(stack_name=stack_name))
            else:
                click.echo(self.MSG_NO_EXECUTE_CHANGESET.format(changeset_id=result["Id"]))

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

        for key, value in template_dict["Parameters"].items():

            obj = {"ParameterKey": key}

            if key in parameter_overrides:
                obj["ParameterValue"] = parameter_overrides[key]
            else:
                obj["UsePreviousValue"] = True

            parameter_values.append(obj)

        return parameter_values
