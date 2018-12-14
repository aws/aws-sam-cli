import os
import uuid
import time
import json
from subprocess import Popen, PIPE
from unittest import TestCase
import boto3

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class TestPublishApp(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.region_name = "us-east-1"
        cls.bucket_name = str(uuid.uuid4())
        cls.bucket_name_placeholder = "<bucket-name>"
        cls.test_data_path = Path(__file__).resolve().parents[2].joinpath("testdata", "publish")
        cls.sar_client = boto3.client('serverlessrepo', region_name=cls.region_name)

        # Create S3 bucket
        s3 = boto3.resource('s3')
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create()

        # Replace placeholder with the created S3 bucket name in test files
        cls.replace_s3_bucket_in_file(cls.bucket_name_placeholder, cls.bucket_name)

        # Grant serverlessrepo read access to the bucket
        bucket_policy = cls.test_data_path.joinpath("s3_bucket_policy.json").read_text()
        cls.s3_bucket.Policy().put(Policy=bucket_policy)

        # Upload test files to S3
        license_body = Path(__file__).resolve().parents[4].joinpath("LICENSE").read_text()
        cls.s3_bucket.put_object(Key="LICENSE", Body=license_body)

        readme_body = Path(__file__).resolve().parents[4].joinpath("README.rst").read_text()
        cls.s3_bucket.put_object(Key="README.rst", Body=readme_body)
        cls.s3_bucket.put_object(Key="README_UPDATE.rst", Body=readme_body)
        cls.s3_bucket.put_object(Key="README_NO_PERMISSION.rst", Body=readme_body)

        code_body = cls.test_data_path.joinpath("main.py").read_text()
        cls.s3_bucket.put_object(Key="main.py", Body=code_body)

    @classmethod
    def tearDownClass(cls):
        cls.s3_bucket.delete_objects(Delete={
            'Objects': [
                {'Key': 'LICENSE'}, {'Key': 'README.rst'}, {'Key': 'main.py'},
                {'Key': 'README_UPDATE.rst'}, {'Key': 'README_NO_PERMISSION.rst'}
            ]
        })
        cls.s3_bucket.delete()
        # Replace the S3 bucket name with placeholder in test files
        cls.replace_s3_bucket_in_file(cls.bucket_name, cls.bucket_name_placeholder)

    @classmethod
    def replace_s3_bucket_in_file(cls, bucket_name, replace_name):
        for f in cls.test_data_path.iterdir():
            if f.suffix == ".yaml" or f.suffix == ".json":
                content = f.read_text()
                f.write_text(content.replace(bucket_name, replace_name))

    def setUp(self):
        # Create application for each test
        app_metadata_text = self.test_data_path.joinpath("metadata_create_app.json").read_text()
        app_metadata = json.loads(app_metadata_text)
        app_metadata['TemplateBody'] = self.test_data_path.joinpath("template_create_app.yaml").read_text()
        response = self.sar_client.create_application(**app_metadata)
        self.application_id = response['ApplicationId']

        # Avoid race conditions
        time.sleep(1)

    def tearDown(self):
        # Delete application for each test
        self.sar_client.delete_application(ApplicationId=self.application_id)
        # Avoid race conditions
        time.sleep(1)

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

    def test_create_application(self):
        # Delete the app first before creating
        self.sar_client.delete_application(ApplicationId=self.application_id)
        # Avoid race conditions
        time.sleep(1)

        template_path = self.test_data_path.joinpath("template_create_app.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        app_metadata = self.test_data_path.joinpath("metadata_create_app.json").read_text()
        expected_msg = "Created new application with the following metadata:\n{}".format(app_metadata)
        self.assertIn(expected_msg, process_stdout.decode('utf-8'))

    def test_update_application(self):
        template_path = self.test_data_path.joinpath("template_update_app.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        app_metadata = self.test_data_path.joinpath("metadata_update_app.json").read_text()
        expected_msg = 'The following metadata of application "{}" has been updated:\n{}'.format(
            self.application_id, app_metadata)
        self.assertIn(expected_msg, process_stdout.decode('utf-8'))

    def test_create_application_version(self):
        template_path = self.test_data_path.joinpath("template_create_app_version.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        app_metadata = self.test_data_path.joinpath("metadata_create_app_version.json").read_text()
        expected_msg = 'The following metadata of application "{}" has been updated:\n{}'.format(
            self.application_id, app_metadata)
        self.assertIn(expected_msg, process_stdout.decode('utf-8'))

    def test_publish_without_s3_permission(self):
        template_path = self.test_data_path.joinpath("template_no_s3_permission.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stderr=PIPE)
        process.wait()
        process_stderr = b"".join(process.stderr.readlines()).strip()

        expected_msg = "AWS Serverless Application Repository doesn't have read permissions"
        self.assertIn(expected_msg, process_stderr.decode('utf-8'))
