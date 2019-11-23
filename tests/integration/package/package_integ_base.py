import os
import json
from pathlib import Path
from unittest import TestCase

import boto3


class PackageIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        cls.bucket_name = os.environ.get("AWS_S3")
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "package")

        # Intialize S3 client
        s3 = boto3.resource("s3")
        # Use a pre-created KMS Key
        cls.kms_key = os.environ.get("AWS_KMS_KEY")
        # Use a pre-created S3 Bucket
        cls.s3_bucket = s3.Bucket(cls.bucket_name)

    def setUp(self):
        super(PackageIntegBase, self).setUp()

    def tearDown(self):
        super(PackageIntegBase, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.objects.all().delete()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(
        self,
        s3_bucket=None,
        template=None,
        template_file=None,
        s3_prefix=None,
        output_template_file=None,
        use_json=False,
        force_upload=False,
        kms_key_id=None,
        metadata=None,
    ):
        command_list = [self.base_command(), "package"]

        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]
        if template:
            command_list = command_list + ["--template", str(template)]
        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]

        if s3_prefix:
            command_list = command_list + ["--s3-prefix", str(s3_prefix)]

        if output_template_file:
            command_list = command_list + ["--output-template-file", str(output_template_file)]
        if kms_key_id:
            command_list = command_list + ["--kms-key-id", str(kms_key_id)]
        if use_json:
            command_list = command_list + ["--use-json"]
        if force_upload:
            command_list = command_list + ["--force-upload"]
        if metadata:
            command_list = command_list + ["--metadata", json.dumps(metadata)]

        return command_list
