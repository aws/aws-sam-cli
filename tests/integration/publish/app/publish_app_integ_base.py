import os
import uuid
from unittest import TestCase
import boto3

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class PublishAppIntegBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.region_name = "us-east-1"
        cls.bucket_name = str(uuid.uuid4())
        cls.bucket_name_placeholder = "<bucket-name>"
        cls.application_name_placeholder = "<application-name>"
        cls.test_data_path = Path(__file__).resolve().parents[2].joinpath("testdata", "publish")
        cls.sar_client = boto3.client('serverlessrepo', region_name=cls.region_name)

        # Create S3 bucket
        s3 = boto3.resource('s3')
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create()

        # Replace placeholder with the created S3 bucket name in test files
        cls.replace_text_in_file(cls.bucket_name_placeholder, cls.bucket_name)

        # Grant serverlessrepo read access to the bucket
        bucket_policy = cls.test_data_path.joinpath("s3_bucket_policy.json").read_text()
        cls.s3_bucket.Policy().put(Policy=bucket_policy)

        # Upload test files to S3
        license_body = Path(__file__).resolve().parents[4].joinpath("LICENSE").read_text()
        cls.s3_bucket.put_object(Key="LICENSE", Body=license_body)

        readme_body = Path(__file__).resolve().parents[4].joinpath("README.rst").read_text()
        cls.s3_bucket.put_object(Key="README.rst", Body=readme_body)
        cls.s3_bucket.put_object(Key="README_UPDATE.rst", Body=readme_body)

        code_body = cls.test_data_path.joinpath("main.py").read_text()
        cls.s3_bucket.put_object(Key="main.py", Body=code_body)

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.delete_objects(Delete={
            'Objects': [
                {'Key': 'LICENSE'}, {'Key': 'README.rst'},
                {'Key': 'README_UPDATE.rst'}, {'Key': 'main.py'}
            ]
        })
        cls.s3_bucket.delete()
        # Replace the S3 bucket name with placeholder in test files
        cls.replace_text_in_file(cls.bucket_name, cls.bucket_name_placeholder)

    @classmethod
    def replace_text_in_file(cls, text, replace_text):
        for f in cls.test_data_path.iterdir():
            if f.suffix == ".yaml" or f.suffix == ".json":
                content = f.read_text()
                f.write_text(content.replace(text, replace_text))

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(self, template_path=None, region=None, profile=None):
        command_list = [self.base_command(), "publish", "app"]

        if template_path:
            command_list = command_list + ["-t", template_path]

        if region:
            command_list = command_list + ["--region", region]

        if profile:
            command_list = command_list + ["--profile", profile]

        return command_list
