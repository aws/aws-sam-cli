import os
import json
import uuid
import shutil
import tempfile
from unittest import TestCase

import boto3

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class PublishAppIntegBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        cls.bucket_name = str(uuid.uuid4())
        cls.bucket_name_placeholder = "<bucket-name>"
        cls.application_name_placeholder = "<application-name>"
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "publish")
        cls.sar_client = boto3.client('serverlessrepo', region_name=cls.region_name)

        # Create S3 bucket
        s3 = boto3.resource('s3')
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create()

        # Grant serverlessrepo read access to the bucket
        bucket_policy_template = cls.test_data_path.joinpath("s3_bucket_policy.json").read_text()
        bucket_policy = bucket_policy_template.replace(cls.bucket_name_placeholder, cls.bucket_name)
        cls.s3_bucket.Policy().put(Policy=bucket_policy)

        # Upload test files to S3
        root_path = Path(__file__).resolve().parents[3]
        license_body = root_path.joinpath("LICENSE").read_text()
        cls.s3_bucket.put_object(Key="LICENSE", Body=license_body)

        readme_body = root_path.joinpath("README.md").read_text()
        cls.s3_bucket.put_object(Key="README.md", Body=readme_body)
        cls.s3_bucket.put_object(Key="README_UPDATE.md", Body=readme_body)

        code_body = cls.test_data_path.joinpath("main.py").read_text()
        cls.s3_bucket.put_object(Key="main.py", Body=code_body)

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.delete_objects(Delete={
            'Objects': [
                {'Key': 'LICENSE'}, {'Key': 'README.md'},
                {'Key': 'README_UPDATE.md'}, {'Key': 'main.py'}
            ]
        })
        cls.s3_bucket.delete()

    @classmethod
    def replace_template_placeholder(cls, placeholder, replace_text):
        for f in cls.temp_dir.iterdir():
            if f.suffix == ".yaml" or f.suffix == ".json":
                content = f.read_text()
                f.write_text(content.replace(placeholder, replace_text))

    def setUp(self):
        shutil.rmtree(str(self.temp_dir), ignore_errors=True)
        shutil.copytree(str(self.test_data_path), str(self.temp_dir))

        # Replace placeholders with the created S3 bucket name and application name
        self.application_name = str(uuid.uuid4())
        self.replace_template_placeholder(self.bucket_name_placeholder, self.bucket_name)
        self.replace_template_placeholder(self.application_name_placeholder, self.application_name)

    def tearDown(self):
        shutil.rmtree(str(self.temp_dir), ignore_errors=True)

    def assert_metadata_details(self, app_metadata, std_output):
        # Strip newlines and spaces in the std output
        stripped_std_output = std_output.replace('\n', '').replace('\r', '').replace(' ', '')
        # Assert expected app metadata in the std output regardless of key order
        for key, value in app_metadata.items():
            self.assertIn('"{}":{}'.format(key, json.dumps(value)), stripped_std_output)

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(self, template_path=None, region=None, profile=None):
        command_list = [self.base_command(), "publish"]

        if template_path:
            command_list = command_list + ["-t", str(template_path)]

        if region:
            command_list = command_list + ["--region", region]

        if profile:
            command_list = command_list + ["--profile", profile]

        return command_list
