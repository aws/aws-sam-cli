import os
import uuid
import json
import tempfile
import time
from pathlib import Path
from subprocess import Popen, PIPE
from unittest import TestCase

import boto3


class PackageRegressionBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        cls.bucket_name = str(uuid.uuid4())
        cls.test_data_path = Path(__file__).resolve().parents[2].joinpath("integration", "testdata", "package")

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

    def base_command(self, base):
        command = [base]
        if os.getenv("SAM_CLI_DEV") and base == "sam":
            command = ["samdev"]
        elif base == "aws":
            command = [base, "cloudformation"]

        return command

    def get_command_list(
        self,
        base="sam",
        s3_bucket=None,
        template_file=None,
        s3_prefix=None,
        output_template_file=None,
        use_json=False,
        force_upload=False,
        kms_key_id=None,
        metadata=None,
    ):
        command_list = self.base_command(base=base)

        command_list = command_list + ["package"]

        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]

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

    def regression_check(self, args):
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file_sam:
            sam_command_list = self.get_command_list(output_template_file=output_template_file_sam.name, **args)
            process = Popen(sam_command_list, stdout=PIPE)
            process.wait()
            self.assertEqual(process.returncode, 0)
            output_sam = output_template_file_sam.read()

        with tempfile.NamedTemporaryFile(delete=False) as output_template_file_aws:
            aws_command_list = self.get_command_list(
                base="aws", output_template_file=output_template_file_aws.name, **args
            )
            process = Popen(aws_command_list, stdout=PIPE)
            process.wait()
            self.assertEqual(process.returncode, 0)
            output_aws = output_template_file_aws.read()

        if "use_json" in args and args.get("use_json"):
            output_sam = json.loads(output_sam)
            output_aws = json.loads(output_aws)

        self.assertEqual(output_sam, output_aws)
