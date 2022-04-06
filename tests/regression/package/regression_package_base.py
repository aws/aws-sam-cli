import os
import json
import time
import tempfile
import uuid
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from unittest import TestCase

import boto3

from samcli.yamlhelper import yaml_parse

S3_SLEEP = 3
TIMEOUT = 300


class PackageRegressionBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        """Please read comments in package_integ_base.py for more details around this."""
        cls.pre_created_bucket = os.environ.get(os.environ.get("AWS_S3"), False)
        cls.bucket_name = cls.pre_created_bucket if cls.pre_created_bucket else str(uuid.uuid4())
        cls.test_data_path = Path(__file__).resolve().parents[2].joinpath("integration", "testdata", "package")

        # Intialize S3 client
        s3 = boto3.resource("s3")
        # Use a pre-created S3 Bucket if present else create a new one
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        if not cls.pre_created_bucket:
            cls.s3_bucket.create()
            time.sleep(S3_SLEEP)

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.objects.all().delete()
        if not cls.pre_created_bucket:
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

    def regression_check(self, args, skip_sam_metadata=True):
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file_sam:
            sam_command_list = self.get_command_list(output_template_file=output_template_file_sam.name, **args)
            process = Popen(sam_command_list, stdout=PIPE)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            self.assertEqual(process.returncode, 0)
            output_sam = output_template_file_sam.read()

        with tempfile.NamedTemporaryFile(delete=False) as output_template_file_aws:
            aws_command_list = self.get_command_list(
                base="aws", output_template_file=output_template_file_aws.name, **args
            )
            process = Popen(aws_command_list, stdout=PIPE)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            self.assertEqual(process.returncode, 0)
            output_aws = output_template_file_aws.read()

        # remove the region name from the template url in cases like nested stacks
        output_aws = output_aws.replace(b"s3.us-east-1.", b"s3.")

        if "use_json" in args and args.get("use_json"):
            output_sam = json.loads(output_sam)
            output_aws = json.loads(output_aws)
        else:
            output_sam = yaml_parse(output_sam)
            output_aws = yaml_parse(output_aws)
        if skip_sam_metadata:
            self._remove_sam_related_metadata(output_sam)

        self.assertEqual(output_sam, output_aws)

    def _remove_sam_related_metadata(self, output_sam):
        if "Resources" not in output_sam:
            return
        for _, resource in output_sam.get("Resources", {}).items():
            if "Metadata" not in resource:
                continue
            resource.get("Metadata", {}).pop("SamResourceId", None)
            resource.get("Metadata", {}).pop("SamNormalize", None)
            if not resource.get("Metadata", {}):
                resource.pop("Metadata")
