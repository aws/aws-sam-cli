import logging
import os
import json
import subprocess
import uuid
import shutil
import tempfile
from unittest import TestCase

import boto3

from samcli.lib.samlib.cloudformation_command import execute_command
from tests.integration.buildcmd.build_integ_base import BuildIntegBase

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

LOG = logging.getLogger(__name__)


class DestroyIntegBase(BuildIntegBase):

    @classmethod
    def setUpClass(cls):
        cls.cmd = BuildIntegBase.base_command()

        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "destroy")
        cls.scratch_dir = str(Path(__file__).resolve().parent.joinpath("scratch"))
        cls.template_path = str(Path(cls.test_data_path, cls.template))

        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        cls.bucket_name = str(uuid.uuid4())
        cls.temp_dir = Path(tempfile.mkdtemp())

        cls.template_path = str(Path(cls.test_data_path, cls.template))
        cls.s3_client = boto3.client('s3')
        # Create S3 bucket
        s3 = boto3.resource('s3')
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create(CreateBucketConfiguration={'LocationConstraint': 'us-west-1'})

    def tearDown(self):
        super().tearDown()
        self.reset_s3()
        self.s3_bucket.delete()

    def build_package_deploy(self, build_parameter_overrides, stack_name):
        if not build_parameter_overrides:
            build_parameter_overrides = {"CodeUri": "Node", "Handler": "ignored"}
        cmdlist = self.get_build_command_list(use_container=True,
                                              parameter_overrides=build_parameter_overrides)

        LOG.info("Running Build Command: {}".format(cmdlist))
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        packaged_template_file = self.default_build_dir.joinpath('packaged.yaml')

        cmdlist = self.get_package_command_list(self.bucket_name, output_template=packaged_template_file)

        LOG.info("Running Package Command: {}".format(cmdlist))
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

        cmdlist = self.get_deploy_command_list(template_file=packaged_template_file, stack_name=stack_name)

        LOG.info("Running Deploy Command: {}".format(cmdlist))
        process = subprocess.Popen(cmdlist, cwd=self.working_dir)
        process.wait()

    def get_all_files(self, prefix=None, delimiter=None, encoding_type=None):
        """
        Lists all objects within S3. The arguments prefix, delimiter, encoding_type are filtered out if there isn't a
        default as list_objects_v2 doesn't except None as a default argument

        :param prefix: the prefix of the key to list
        :param delimiter: the delimiter used in the file to list
        :param encoding_type: the encoding type for the file to list
        :return: The list of files from the s3 bucket
        """
        args = {"Prefix": prefix, "Delimiter": delimiter, "EncodingType": encoding_type}
        args = {k: v for k, v in args.items() if v is not None}
        return (
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, **args).get("Contents"),
        )

    def reset_s3(self):
        """
        Deletes all keys and files within S3
        :return:
        """
        all_files_set = self.get_all_files()
        if not all_files_set:
            return
        for files in all_files_set:
            if not files:
                break
            for s3_file in files:
                key = s3_file.get("Key")
                self.s3_client.delete_object(Bucket=self.s3_bucket, Key=key)

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_deploy_command_list(self, template_file, stack_name, parameter_overrides=None):
        command_list = [self.base_command(), "deploy", '--template-file', template_file, '--stack-name', stack_name]

        if parameter_overrides:
            command_list = command_list + ["--parameter-overrides", parameter_overrides]

        return command_list

    def get_package_command_list(self, s3_bucket, output_template=None):
        command_list = [self.base_command(), "package", '--s3-bucket', s3_bucket]
        if output_template:
            command_list += ['--output-template-file', output_template]
        return command_list

    def get_destroy_command_list(self, stack_name=None, retain_resources=None, role_arn=None,
                                 client_request_token=None,
                                 wait=None,
                                 wait_time=None):
        command_list = [self.base_command(), "destroy", "-f"]

        if stack_name:
            command_list = command_list + ["--stack-name", str(stack_name)]

        if retain_resources:
            command_list = command_list + ["--retain-resources", retain_resources]

        if role_arn:
            command_list = command_list + ["--role-arn", role_arn]

        if client_request_token:
            command_list = command_list + ["--semantic-version", client_request_token]

        if wait:
            command_list = command_list + ["--wait"]

        if wait_time:
            command_list = command_list + ["--wait-time", wait_time]

        return command_list

    def enable_stack_termination_protection(self, stack_name):
        args = ('--stack-name', stack_name, '--enable-termination-protection')
        execute_command('update-termination-protection', *args)
