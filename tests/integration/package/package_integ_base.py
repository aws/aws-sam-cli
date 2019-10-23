import os
import uuid
import tempfile
import time
from pathlib import Path
from unittest import TestCase

import boto3


class PackageIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        cls.bucket_name = str(uuid.uuid4())
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "package")

        # Create S3 bucket
        s3 = boto3.resource("s3")
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create()

        # Given 3 seconds for all the bucket creation to complete
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.objects.all().delete()
        cls.s3_bucket.delete()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(self, s3_bucket=None, template_file=None):
        command_list = [self.base_command(), "package"]

        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]

        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]

        return command_list
