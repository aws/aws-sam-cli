import re
import uuid
import json
from subprocess import Popen, PIPE

from .publish_app_integ_base import PublishAppIntegBase


class TestPublishExistingApp(PublishAppIntegBase):

    def setUp(self):
        self.application_name = str(uuid.uuid4())
        # Replace placeholder with application name in test files
        self.replace_text_in_file(self.application_name_placeholder, self.application_name)

        # Create application for each test
        app_metadata_text = self.test_data_path.joinpath("metadata_create_app.json").read_text()
        app_metadata = json.loads(app_metadata_text)
        app_metadata['TemplateBody'] = self.test_data_path.joinpath("template_create_app.yaml").read_text()
        response = self.sar_client.create_application(**app_metadata)
        self.application_id = response['ApplicationId']

    def tearDown(self):
        # Delete application for each test
        self.sar_client.delete_application(ApplicationId=self.application_id)
        # Replace the application name with placeholder in test files
        self.replace_text_in_file(self.application_name, self.application_name_placeholder)

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


class TestPublishNewApp(PublishAppIntegBase):

    def setUp(self):
        self.application_name = str(uuid.uuid4())
        # Replace placeholder with application name in test files
        self.replace_text_in_file(self.application_name_placeholder, self.application_name)

    def tearDown(self):
        # Replace the application name with placeholder in test files
        self.replace_text_in_file(self.application_name, self.application_name_placeholder)

    def test_create_application(self):
        template_path = self.test_data_path.joinpath("template_create_app.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        app_metadata = self.test_data_path.joinpath("metadata_create_app.json").read_text()
        expected_msg = "Created new application with the following metadata:\n{}".format(app_metadata)
        self.assertIn(expected_msg, process_stdout.decode('utf-8'))

        # Get console link application id from stdout
        pattern = r'arn:[\w\-]+:serverlessrepo:[\w\-]+:[0-9]+:applications\~[\S]+'
        match = re.search(pattern, process_stdout.decode('utf-8'))
        application_id = match.group().replace('~', '/')
        self.sar_client.delete_application(ApplicationId=application_id)

    def test_publish_not_packaged_template(self):
        template_path = self.test_data_path.joinpath("template_not_packaged.yaml")
        command_list = self.get_command_list(template_path=template_path, region=self.region_name)

        process = Popen(command_list, stderr=PIPE)
        process.wait()
        process_stderr = b"".join(process.stderr.readlines()).strip()

        expected_msg = "Please make sure that you have uploaded application artifacts to S3"
        self.assertIn(expected_msg, process_stderr.decode('utf-8'))
