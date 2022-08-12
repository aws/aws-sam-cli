import os
import tarfile
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.deploy.exceptions import DeployFailedError
from samcli.commands.exceptions import InvalidTestRunnerTemplateException, MissingTestRunnerTemplateException
from samcli.lib.test_runner.fargate_testsuite_runner import FargateTestsuiteRunner


class MockDeployer:
    def __init__(
        self, has_stack_return_value=True, update_stack_ex=None, create_stack_ex=None, wait_for_execute_ex=None
    ):
        self.return_value = has_stack_return_value
        self.update_stack_ex = update_stack_ex
        self.create_stack_ex = create_stack_ex
        self.wait_for_execute_ex = wait_for_execute_ex

    def has_stack(self, **kwargs) -> bool:
        return self.return_value

    def update_stack(self, **kwargs):
        if self.update_stack_ex:
            raise self.update_stack_ex
        return

    def create_stack(self, **kwargs):
        if self.create_stack_ex:
            raise self.create_stack_ex
        return

    def wait_for_execute(self, **kwargs):
        if self.wait_for_execute_ex:
            raise self.wait_for_execute_ex
        return


class Test_InvokeTestsuite(TestCase):
    def setUp(self):
        boto_client_provider_mock = Mock()

        self.runner = FargateTestsuiteRunner(
            boto_client_provider=boto_client_provider_mock,
            runner_stack_name="TestStackName",
            tests_path="fake/path",
            requirements_file_path="fake/path",
            path_in_bucket="fake/path/in/bucket",
            other_env_vars={},
            bucket_override=None,
            ecs_cluster_override=None,
            subnets_override=None,
            runner_template_path="fake/path/template.yaml",
            test_command_options=None,
        )

    def test_create_stack_fails(self):
        mock_deployer = MockDeployer(create_stack_ex=DeployFailedError(stack_name="test", msg="error"))
        self.runner.deployer = mock_deployer
        with self.assertRaises(DeployFailedError):
            self.runner._create_new_test_runner_stack("test-template-body")

    def test_wait_fails_on_create(self):
        mock_deployer = MockDeployer(wait_for_execute_ex=DeployFailedError(stack_name="test", msg="error"))
        self.runner.deployer = mock_deployer
        with self.assertRaises(DeployFailedError):
            self.runner._create_new_test_runner_stack("test-template-body")

    def test_update_stack_fails(self):
        mock_deployer = MockDeployer(update_stack_ex=DeployFailedError(stack_name="test", msg="error"))
        self.runner.deployer = mock_deployer
        with self.assertRaises(DeployFailedError):
            self.runner._update_exisiting_test_runner_stack("test-template-body")

    def test_wait_fails_on_update(self):
        mock_deployer = MockDeployer(wait_for_execute_ex=DeployFailedError(stack_name="test", msg="error"))
        self.runner.deployer = mock_deployer
        with self.assertRaises(DeployFailedError):
            self.runner._update_exisiting_test_runner_stack("test-template-body")

    def test_no_fail_on_no_update(self):
        mock_deployer = MockDeployer(
            update_stack_ex=DeployFailedError(stack_name="No updates are to be performed", msg="error")
        )
        self.runner.deployer = mock_deployer
        try:
            self.runner._update_exisiting_test_runner_stack("test-template-body")
        except:
            self.fail("Update stack failed because of no updates. Should ignore if no updates.")

    def test_get_resource_list(self):
        boto_cloudformation_client_mock = Mock()
        boto_cloudformation_client_mock.describe_stack_resources.return_value = {
            "StackResources": [
                {"PhysicalResourceId": "my-stack-bucket-1vc62xmplgguf", "ResourceType": "AWS::S3::Bucket"}
            ]
        }
        self.runner.boto_cloudformation_client = boto_cloudformation_client_mock

        resource_list = self.runner._get_resource_list()
        self.assertEqual(
            resource_list, [{"PhysicalResourceId": "my-stack-bucket-1vc62xmplgguf", "ResourceType": "AWS::S3::Bucket"}]
        )

    def test_get_unique_resource_physical_id_success(self):
        resource_list = [
            {"PhysicalResourceId": "my-task-definition", "ResourceType": "AWS::ECS::TaskDefinition"},
            {"PhysicalResourceId": "my-test-s3-bucket", "ResourceType": "AWS::S3::Bucket"},
        ]
        physical_id = self.runner._get_unique_resource_physical_id(resource_list, "AWS::S3::Bucket")
        self.assertEqual(physical_id, "my-test-s3-bucket")

    def test_get_unique_resource_physical_id_duplicate(self):
        resource_list = [
            {"PhysicalResourceId": "my-test-s3-bucket", "ResourceType": "AWS::S3::Bucket"},
            {"PhysicalResourceId": "my-test-s3-bucket", "ResourceType": "AWS::S3::Bucket"},
        ]
        with self.assertRaises(InvalidTestRunnerTemplateException):
            self.runner._get_unique_resource_physical_id(resource_list, "AWS::S3::Bucket")

    def test_get_unique_resource_physical_id_missing(self):
        resource_list = [
            {"PhysicalResourceId": "my-task-definition", "ResourceType": "AWS::ECS::TaskDefinition"},
            {"PhysicalResourceId": "my-test-s3-bucket", "ResourceType": "AWS::S3::Bucket"},
        ]
        with self.assertRaises(InvalidTestRunnerTemplateException):
            self.runner._get_unique_resource_physical_id(resource_list, "AWS::ECS::Cluster")

    def test_get_container_name(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.describe_task_definition.return_value = {
            "taskDefinition": {
                "containerDefinitions": [
                    {
                        "name": "test-container-name",
                    }
                ]
            }
        }
        self.runner.boto_ecs_client = boto_ecs_client_mock
        container_name = self.runner._get_container_name("test-task-def-arn")
        self.assertEqual(container_name, "test-container-name")

    def test_get_container_name_multiple_def(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.describe_task_definition.return_value = {
            "taskDefinition": {
                "containerDefinitions": [
                    {"name": "A"},
                    {"name": "B"},
                ]
            }
        }
        self.runner.boto_ecs_client = boto_ecs_client_mock
        with self.assertRaises(InvalidTestRunnerTemplateException):
            self.runner._get_container_name("test-task-def-arn")

    def test_get_container_name_missing_def(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.describe_task_definition.return_value = {"taskDefinition": {"containerDefinitions": []}}
        self.runner.boto_ecs_client = boto_ecs_client_mock
        with self.assertRaises(InvalidTestRunnerTemplateException):
            self.runner._get_container_name("test-task-def-arn")

    def test_get_subnets(self):
        boto_ec2_client_mock = Mock()
        boto_ec2_client_mock.describe_subnets.return_value = {
            "Subnets": [
                {
                    "SubnetId": "subnet-0bb1c79de3EXAMPLE",
                },
                {
                    "SubnetId": "subnet-8EXAMPLE",
                },
            ]
        }
        self.runner.boto_ec2_client = boto_ec2_client_mock
        subnets = self.runner._get_subnets()
        self.assertEqual(subnets, ["subnet-0bb1c79de3EXAMPLE", "subnet-8EXAMPLE"])

    def test_upload_tests_and_reqs(self):
        test_dir_name = Path("fake-test-directory")
        os.mkdir(test_dir_name)

        fake_tests_path = Path.joinpath(test_dir_name, "fake_test.py")

        with open(fake_tests_path, "w") as fake_test_file:
            fake_test_file.write("Some fake test code")

        fake_reqs_path = "fake-reqs.txt"
        with open(fake_reqs_path, "w") as fake_reqs_file:
            fake_reqs_file.write("Some fake requirements")

        temp_tarfile_name = str(uuid.uuid4())

        boto_s3_client_mock = Mock()
        boto_s3_client_mock.put_object = Mock()

        boto_s3_waiter_mock = Mock()
        boto_s3_waiter_mock.wait = Mock()

        boto_s3_client_mock.get_waiter.return_value = boto_s3_waiter_mock

        self.runner.boto_s3_client = boto_s3_client_mock

        self.runner.tests_path = fake_tests_path
        self.runner.requirements_file_path = fake_reqs_path

        try:
            self.runner._upload_tests_and_reqs("test-bucket", temp_tarfile_name)
            # Ensure tarfile gets cleaned up
            self.assertFalse(os.path.exists(temp_tarfile_name))
            # Ensure both the tests tar and the requirements were uploaded
            self.assertEqual(boto_s3_client_mock.put_object.call_count, 2)
            # Ensure both the tests and requirements were waited for
            self.assertEqual(boto_s3_waiter_mock.wait.call_count, 2)
        except Exception as ex:
            self.fail(f"Failure due to unexpected exception {ex}")
        finally:
            # Although the _upload_tests_and_reqs function SHOULD delete the tarfile,
            # we don't want to leave artifacts in any case
            try:
                os.remove(temp_tarfile_name)
            except OSError:
                pass
            os.remove(fake_tests_path)
            os.rmdir(test_dir_name)
            os.remove(fake_reqs_path)

    def test_download_results(self):
        temp_tarfile_name = str(uuid.uuid4())
        # For clarity, the decompressed tarfile contents will be the basename of the path-in-bucket directory
        # E.g. Setting path-in-bucket to sample/path/run_01 => results will be in directory named run_01
        fake_results_dirname = Path(self.runner.path_in_bucket.stem)
        fake_test_stdout_file_name = "fake-results.log"

        os.mkdir(fake_results_dirname)
        fake_results_stdout_file_path = Path.joinpath(fake_results_dirname, fake_test_stdout_file_name)

        with open(fake_results_stdout_file_path, "w") as fake_stdout_file:
            fake_stdout_file.write("This is fake test command standard output.")

        # Instead of actually downloading the tar, simply create it to test the extraction and removal
        with tarfile.open(temp_tarfile_name, "w:gz") as tar:
            tar.add(fake_results_dirname)

        boto_s3_client_mock = Mock()
        boto_s3_client_mock.download_file = Mock()
        self.runner.boto_s3_client = boto_s3_client_mock

        # Set these constants to fake test constants so that it knows what to remove
        self.runner.COMPRESSED_RESULTS_FILE_NAME = temp_tarfile_name
        self.runner.RESULTS_STDOUT_FILE_NAME = fake_test_stdout_file_name

        try:
            self.runner._download_results("test-bucket")

            boto_s3_client_mock.download_file.assert_called_once()
            self.assertTrue(os.path.exists(fake_results_stdout_file_path))
            self.assertFalse(os.path.exists(temp_tarfile_name))
        except Exception as ex:
            self.fail(f"Failure due to unexpected exception {ex}")
        finally:
            # Although the _download_results function SHOULD delete the tarfile,
            # we don't want to leave artifacts in any case
            try:
                os.remove(temp_tarfile_name)
            except OSError:
                pass
            os.remove(fake_results_stdout_file_path)
            os.rmdir(fake_results_dirname)

    def test_no_other_vars(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.run_task = Mock()

        boto_s3_client_mock = Mock()
        boto_s3_waiter_mock = Mock()
        boto_s3_waiter_mock.wait = Mock()
        boto_s3_client_mock.get_waiter.return_value = boto_s3_waiter_mock

        self.runner.boto_ecs_client = boto_ecs_client_mock
        self.runner.boto_s3_client = boto_s3_client_mock

        self.runner.other_env_vars = {}
        self.runner._invoke_testsuite(
            bucket="test-bucket",
            ecs_cluster="test-cluster",
            container_name="test-container-name",
            task_definition_arn="test-task-def-arn",
            subnets=["subnet-x"],
        )
        boto_ecs_client_mock.run_task.assert_called_once_with(
            cluster="test-cluster",
            launchType="FARGATE",
            networkConfiguration={"awsvpcConfiguration": {"subnets": ["subnet-x"], "assignPublicIp": "ENABLED"}},
            overrides={
                "containerOverrides": [
                    {
                        "name": "test-container-name",
                        "environment": [
                            {"name": "TEST_RUNNER_BUCKET", "value": "test-bucket"},
                            {"name": "TEST_COMMAND_OPTIONS", "value": ""},
                            {"name": "TEST_RUN_DIR", "value": str(self.runner.path_in_bucket)},
                            {"name": "TEST_RUN_RESULTS_ID", "value": self.runner.COMPRESSED_RESULTS_FILE_NAME},
                        ],
                    }
                ]
            },
            taskDefinition="test-task-def-arn",
        )
        boto_s3_waiter_mock.wait.assert_called_once()

    def test_good_invoke(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.run_task = Mock()

        boto_s3_client_mock = Mock()
        boto_s3_waiter_mock = Mock()
        boto_s3_waiter_mock.wait = Mock()
        boto_s3_client_mock.get_waiter.return_value = boto_s3_waiter_mock

        self.runner.boto_ecs_client = boto_ecs_client_mock
        self.runner.boto_s3_client = boto_s3_client_mock

        self.runner.other_env_vars = {"SOLID": "VALUE"}
        self.runner._invoke_testsuite(
            bucket="test-bucket",
            ecs_cluster="test-cluster",
            container_name="test-container-name",
            task_definition_arn="test-task-def-arn",
            subnets=["subnet-x"],
        )
        boto_ecs_client_mock.run_task.assert_called_once_with(
            cluster="test-cluster",
            launchType="FARGATE",
            networkConfiguration={"awsvpcConfiguration": {"subnets": ["subnet-x"], "assignPublicIp": "ENABLED"}},
            overrides={
                "containerOverrides": [
                    {
                        "name": "test-container-name",
                        "environment": [
                            {"name": "TEST_RUNNER_BUCKET", "value": "test-bucket"},
                            {"name": "TEST_COMMAND_OPTIONS", "value": ""},
                            {"name": "TEST_RUN_DIR", "value": str(self.runner.path_in_bucket)},
                            {"name": "TEST_RUN_RESULTS_ID", "value": self.runner.COMPRESSED_RESULTS_FILE_NAME},
                            {"name": "SOLID", "value": "VALUE"},
                        ],
                    }
                ]
            },
            taskDefinition="test-task-def-arn",
        )
        boto_s3_waiter_mock.wait.assert_called_once()

    def test_stack_not_exists_and_no_template(self):
        self.runner.deployer = MockDeployer(has_stack_return_value=False)
        self.runner.runner_template_path = None

        with self.assertRaises(MissingTestRunnerTemplateException):
            self.runner._update_or_create_test_runner_stack()

    @patch('samcli.lib.test_runner.fargate_testsuite_runner.Path.read_text')
    def test_stack_not_exists_and_template(self, file_read_patch):
        self.runner.deployer = MockDeployer(has_stack_return_value=False)
        self.runner.runner_template_path = "path/that/is/defined"

        self.runner._create_new_test_runner_stack = Mock()
        self.runner._update_exisiting_test_runner_stack = Mock()
        file_read_patch.return_value = "test-template-contents"

        self.runner._update_or_create_test_runner_stack()
        file_read_patch.assert_called_once_with("path/that/is/defined")

        # Create but not update
        self.runner._create_new_test_runner_stack.assert_called_once_with(template_body="test-template-contents")
        self.runner._update_exisiting_test_runner_stack.assert_not_called()

    @patch('samcli.lib.test_runner.fargate_testsuite_runner.Path.read_text')
    def test_stack_exists_and_template(self, file_read_patch):
        self.runner.deployer = MockDeployer(has_stack_return_value=True)
        self.runner.runner_template_path = "path/that/is/defined"

        self.runner._update_exisiting_test_runner_stack = Mock()
        self.runner._create_new_test_runner_stack = Mock()
        file_read_patch.return_value = "test-template-contents"

        self.runner._update_or_create_test_runner_stack()
        file_read_patch.assert_called_once_with("path/that/is/defined")

        # Update but not create
        self.runner._update_exisiting_test_runner_stack.assert_called_once_with(template_body="test-template-contents")
        self.runner._create_new_test_runner_stack.assert_not_called()

    def test_stack_exists_and_no_template(self):
        self.runner.deployer = MockDeployer(has_stack_return_value=True)
        self.runner.runner_template_path = None

        self.runner._update_exisiting_test_runner_stack = Mock()
        self.runner._create_new_test_runner_stack = Mock()

        self.runner._update_or_create_test_runner_stack()

        # Neither update nor create
        self.runner._create_new_test_runner_stack.assert_not_called()
        self.runner._update_exisiting_test_runner_stack.assert_not_called()

    def test_do_testsuite(self):

        self.runner.deployer = MockDeployer(has_stack_return_value=True)
        self.runner.runner_template_path = None

        self.runner._update_or_create_test_runner_stack = Mock()
        self.runner._get_resource_list = Mock()
        self.runner._get_unique_resource_physical_id = Mock()
        self.runner._get_container_name = Mock()
        self.runner._upload_tests_and_reqs = Mock()
        self.runner._invoke_testsuite = Mock()
        self.runner._download_results = Mock()

        self.runner.bucket_override = "test-bucket"
        self.runner.ecs_cluster_override = "test-cluster"
        self.runner.subnets_override = ["subnet-x"]

        self.runner._get_container_name.return_value = "test-container"

        def fake_get_unique_resource_physical_id(resource_list, resource_type):
            if resource_type == "AWS::ECS::TaskDefinition":
                return "test-task-definition-arn"

        self.runner._get_unique_resource_physical_id.side_effect = fake_get_unique_resource_physical_id

        self.runner.do_testsuite()

        self.runner._update_or_create_test_runner_stack.assert_called_once()
        self.runner._get_resource_list.assert_called_once()
        self.runner._get_unique_resource_physical_id.assert_called_once()
        self.runner._get_container_name.assert_called_once()
        self.runner._upload_tests_and_reqs.assert_called_once()
        self.runner._invoke_testsuite.assert_called_once_with(
            bucket="test-bucket",
            ecs_cluster="test-cluster",
            subnets=["subnet-x"],
            container_name="test-container",
            task_definition_arn="test-task-definition-arn",
        )
        self.runner._download_results.assert_called_once()
