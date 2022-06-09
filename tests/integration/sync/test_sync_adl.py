import json
import shutil
import time
from unittest import skipIf

from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION
from tests.integration.sync.test_sync_code import TestSyncCodeBase, SKIP_SYNC_TESTS, TestSyncCode, LAMBDA_SLEEP
from tests.integration.sync.test_sync_watch import TestSyncWatchBase, TestSyncWatchCode
from tests.testing_utils import run_command_with_input, read_until_string


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncAdlCasesWithCodeParameter(TestSyncCodeBase):
    template = "template-python-no-dependencies.yaml"

    def test_sync_code_function_without_dependencies(self):
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)

        # first assert that lambda returns initial response
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello world")

        shutil.rmtree(TestSyncCode.temp_dir.joinpath("python_function_no_deps"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("python_function_no_deps"),
            TestSyncCode.temp_dir.joinpath("python_function_no_deps"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource_id="HelloWorldFunction",
            dependency_layer=True,
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello mars")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncAdlCasesWithCodeParameterWithDependencyChange(TestSyncCodeBase):
    template = "template-python-no-dependencies.yaml"

    def test_sync_code_function_with_dependencies_should_prompt_to_run_sync_infra(self):
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)

        # first assert that lambda returns initial response without additional field that we are adding
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertNotIn("extra_message", lambda_response)

        shutil.rmtree(TestSyncCode.temp_dir.joinpath("python_function_no_deps"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("python_function_with_deps"),
            TestSyncCode.temp_dir.joinpath("python_function_no_deps"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource_id="HelloWorldFunction",
            dependency_layer=True,
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())

        # assert that sync execution exit with a text to suggest running infra sync
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Try sam sync without --code or sam deploy", sync_process_execute.stderr.decode('utf-8'))


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncAdlWithWatchStartWithNoDependencies(TestSyncWatchBase):
    @classmethod
    def setUpClass(cls):
        cls.template_before = f"code/before/template-python-no-dependencies.yaml"
        cls.dependency_layer = True
        super().setUpClass()

    def should_run_initial_infra_validation(self):
        return False

    def test_sync_watch_code(self):
        self.stack_resources = self._get_stacks(self.stack_name)

        # first confirm initial response
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello world")
        self.assertNotIn("extra_message", lambda_response)

        # change lambda with another output
        self.update_file(
            self.test_dir.joinpath("code/after/python_function_no_deps/app.py"),
            self.test_dir.joinpath("code/before/python_function_no_deps/app.py"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing Lambda Function HelloWorldFunction.\x1b[0m\n", timeout=30
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        self._confirm_lambda_error(lambda_functions[0])

        # change lambda with a dependency
        self.update_file(
            self.test_dir.joinpath("code/after/python_function_with_deps/requirements.txt"),
            self.test_dir.joinpath("code/before/python_function_no_deps/requirements.txt"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=300
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello mars")
        self.assertIn("extra_message", lambda_response)
