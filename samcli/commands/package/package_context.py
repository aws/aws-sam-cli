"""
Logic for uploading to s3 based on supplied template file and s3 bucket
"""

# Copyright 2012-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import json
import logging
import os

import boto3
import click
from botocore.config import Config

from samcli.commands.package.exceptions import PackageFailedError
from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.botoconfig import get_boto_config_with_user_agent
from samcli.yamlhelper import yaml_dump

LOG = logging.getLogger(__name__)


class PackageContext:

    MSG_PACKAGED_TEMPLATE_WRITTEN = (
        "\nSuccessfully packaged artifacts and wrote output template "
        "to file {output_file_name}."
        "\n"
        "Execute the following command to deploy the packaged template"
        "\n"
        "sam deploy --template-file {output_file_path} "
        "--stack-name <YOUR STACK NAME>"
        "\n"
    )

    def __init__(
        self,
        template_file,
        s3_bucket,
        s3_prefix,
        kms_key_id,
        output_template_file,
        use_json,
        force_upload,
        no_progressbar,
        metadata,
        region,
        profile,
        on_deploy=False,
    ):
        self.template_file = template_file
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.kms_key_id = kms_key_id
        self.output_template_file = output_template_file
        self.use_json = use_json
        self.force_upload = force_upload
        self.no_progressbar = no_progressbar
        self.metadata = metadata
        self.region = region
        self.profile = profile
        self.on_deploy = on_deploy
        self.s3_uploader = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):

        s3_client = boto3.client(
            "s3",
            config=get_boto_config_with_user_agent(
                signature_version="s3v4", region_name=self.region if self.region else None
            ),
        )

        self.s3_uploader = S3Uploader(
            s3_client, self.s3_bucket, self.s3_prefix, self.kms_key_id, self.force_upload, self.no_progressbar
        )
        # attach the given metadata to the artifacts to be uploaded
        self.s3_uploader.artifact_metadata = self.metadata

        try:
            exported_str = self._export(self.template_file, self.use_json)

            self.write_output(self.output_template_file, exported_str)

            if self.output_template_file and not self.on_deploy:
                msg = self.MSG_PACKAGED_TEMPLATE_WRITTEN.format(
                    output_file_name=self.output_template_file,
                    output_file_path=os.path.abspath(self.output_template_file),
                )
                click.echo(msg)
        except OSError as ex:
            raise PackageFailedError(template_file=self.template_file, ex=str(ex)) from ex

    def _export(self, template_path, use_json):
        template = Template(template_path, os.getcwd(), self.s3_uploader)
        exported_template = template.export()

        if use_json:
            exported_str = json.dumps(exported_template, indent=4, ensure_ascii=False)
        else:
            exported_str = yaml_dump(exported_template)

        return exported_str

    def write_output(self, output_file_name, data):
        if output_file_name is None:
            click.echo(data)
            return

        with open(output_file_name, "w") as fp:
            fp.write(data)
