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

import os
import logging
import sys

import json

from .artifact_exporter import Template
from samcli.yamlhelper import yaml_dump
from samcli.commands.package import exceptions
from samcli.commands.package.s3_uploader import S3Uploader

import boto3

LOG = logging.getLogger(__name__)


class PackageCommand(object):

    MSG_PACKAGED_TEMPLATE_WRITTEN = (
        "Successfully packaged artifacts and wrote output template "
        "to file {output_file_name}."
        "\n"
        "Execute the following command to deploy the packaged template"
        "\n"
        "sam deploy --template-file {output_file_path} "
        "--stack-name <YOUR STACK NAME>"
        "\n"
    )

    NAME = "package"

    def run(
        self,
        template_file,
        s3_bucket,
        s3_prefix,
        kms_key_id,
        output_template_file,
        use_json,
        force_upload,
        metadata,
        region,
        profile,
    ):
        session = boto3.Session(profile_name=profile)
        s3_client = session.client("s3", region_name=region)

        template_path = template_file
        if not os.path.isfile(template_path):
            raise exceptions.InvalidTemplatePathError(template_path=template_path)

        bucket = s3_bucket

        self.s3_uploader = S3Uploader(s3_client, bucket, s3_prefix, kms_key_id, force_upload)
        # attach the given metadata to the artifacts to be uploaded
        self.s3_uploader.artifact_metadata = metadata

        output_file = output_template_file
        use_json = use_json
        exported_str = self._export(template_path, use_json)

        sys.stdout.write("\n")
        self.write_output(output_file, exported_str)

        if output_file:
            msg = self.MSG_PACKAGED_TEMPLATE_WRITTEN.format(
                output_file_name=output_file, output_file_path=os.path.abspath(output_file)
            )
            sys.stdout.write(msg)

        sys.stdout.flush()
        return 0

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
            sys.stdout.write(data)
            return

        with open(output_file_name, "w") as fp:
            fp.write(data)
