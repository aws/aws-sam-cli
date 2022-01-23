import tempfile
import os
from unittest import TestCase
from unittest.mock import call, patch, ANY, mock_open

import botocore
from botocore.exceptions import ClientError
from samcli.lib.schemas.schemas_code_manager import do_download_source_code_binding, do_extract_and_merge_schemas_code


class TestSchemaCodeManager(TestCase):
    def setUp(self):
        self.runtime = "java8"
        self.registry_name = "aws.events"
        self.schema_name = "EC2InstanceChangeNotification"
        self.schema_full_name = "aws.EC2InstanceChangeNotification"
        self.schema_version = 1
        self.schema_runtime = "Java8"

    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_generate_code_binding(self, schemas_api_caller_mock):
        temp_dir = tempfile.gettempdir()
        schemas_api_caller_mock.download_source_code_binding.return_value = "/usr/hello/something.zip"
        schema_template_details = {
            "registry_name": self.registry_name,
            "schema_full_name": self.schema_full_name,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "event_source": None,
            "event_source_detail_type": None,
        }
        result = do_download_source_code_binding(
            self.runtime, schema_template_details, schemas_api_caller_mock, temp_dir
        )
        self.assertEqual(result, "/usr/hello/something.zip")
        self.assertEqual(schemas_api_caller_mock.download_source_code_binding.call_count, 1)
        schemas_api_caller_mock.download_source_code_binding.assert_called_once_with(
            self.schema_runtime, self.registry_name, self.schema_full_name, self.schema_version, temp_dir
        )

    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_download_source_code_binding_when_exception_occurs(self, schemas_api_caller_mock):
        temp_dir = tempfile.gettempdir()
        schemas_api_caller_mock.download_source_code_binding.side_effect = [
            botocore.exceptions.ClientError(
                {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
            ),
            "result.zip",
        ]
        schemas_api_caller_mock.put_code_binding.return_result = None
        schemas_api_caller_mock.poll_for_code_binding_status.return_result = None
        schema_template_details = {
            "registry_name": self.registry_name,
            "schema_full_name": self.schema_full_name,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "event_source": None,
            "event_source_detail_type": None,
        }
        result = do_download_source_code_binding(
            self.runtime, schema_template_details, schemas_api_caller_mock, temp_dir
        )
        self.assertEqual(schemas_api_caller_mock.download_source_code_binding.call_count, 2)
        self.assertEqual(result, "result.zip")
        schemas_api_caller_mock.download_source_code_binding.assert_has_calls(
            [
                call(self.schema_runtime, self.registry_name, self.schema_full_name, self.schema_version, temp_dir),
                call(self.schema_runtime, self.registry_name, self.schema_full_name, self.schema_version, temp_dir),
            ]
        )
        self.assertEqual(schemas_api_caller_mock.put_code_binding.call_count, 1)
        self.assertEqual(schemas_api_caller_mock.poll_for_code_binding_status.call_count, 1)

    @patch("json.loads")
    @patch("samcli.lib.schemas.schemas_code_manager.unzip")
    def test_merge_generated_code(self, unzip_mock, json_loads_mock):
        json_loads_mock.return_value = {
            "project_name": "Your EventBridge Starter app",
            "runtime": "java8",
            "function_name": "HelloWorldFunction",
            "AWS_Schema_registry": "aws.events",
            "AWS_Schema_name": "EC2InstanceStateChangeNotification",
            "AWS_Schema_source": "aws.ec2",
            "AWS_Schema_detail_type": "EC2 Instance State-change Notification",
        }
        cookiecutter_json_path = os.path.join("template_location", "cookiecutter.json")
        project_path = os.path.join("download_location", "my_project", "HelloWorldFunction")
        with patch("builtins.open", mock_open(read_data='{function_name: "test"}')) as schemas_file_mock:
            do_extract_and_merge_schemas_code("result.zip", "download_location", "my_project", "template_location")
            schemas_file_mock.assert_called_with(cookiecutter_json_path, "r")
            unzip_mock.assert_called_once_with("result.zip", project_path)
