import json
import os.path
from unittest import skipIf

from samcli.commands._utils.experimental import set_experimental, ExperimentalFlag
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION, AWS_LAMBDA_LAYERVERSION
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.sync.test_sync_code import TestSyncCodeBase, SKIP_SYNC_TESTS, TestSyncCode
from tests.integration.sync.test_sync_watch import TestSyncWatchBase
from tests.testing_utils import run_command_with_input, read_until_string, IS_WINDOWS


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncAdlCasesWithCodeParameter(TestSyncCodeBase):
    template = "template-python-no-dependencies.yaml"
    folder = "code"
    dependency_layer = True

    def test_sync_code_function_without_dependencies(self):
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)

        # first assert that lambda returns initial response
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello world")

        # update app.py with updated response
        self.update_file(
            self.test_data_path.joinpath("code", "after", "python_function_no_deps", "app_without_numpy.py"),
            TestSyncCode.temp_dir.joinpath("python_function_no_deps", "app.py"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource_id_list=["HelloWorldFunction"],
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

        # Confirm lambda returns updated response
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello mars")

        # update app.py with some dependency which is missing in requirements.txt
        self.update_file(
            self.test_data_path.joinpath("code", "after", "python_function_no_deps", "app_with_numpy.py"),
            TestSyncCode.temp_dir.joinpath("python_function_no_deps", "app.py"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource_id_list=["HelloWorldFunction"],
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

        # confirm that lambda execution will fail
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        self._confirm_lambda_error(lambda_functions[0])

        # finally, update requirements.txt with missing dependency
        self.update_file(
            self.test_data_path.joinpath("code", "after", "python_function_no_deps", "requirements.txt"),
            TestSyncCode.temp_dir.joinpath("python_function_no_deps", "requirements.txt"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource_id_list=["HelloWorldFunction"],
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
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)

        # confirm that updated lambda returns expected result
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello mars")
        self.assertIn("extra_message", lambda_response)


@skipIf(SKIP_SYNC_TESTS or IS_WINDOWS, "Skip sync tests in CI/CD only")
class TestSyncAdlWithWatchStartWithNoDependencies(TestSyncWatchBase):
    @classmethod
    def setUpClass(cls):
        cls.template_before = os.path.join("code", "before", "template-python-no-dependencies.yaml")
        cls.dependency_layer = True
        super().setUpClass()

    def run_initial_infra_validation(self):
        self.stack_resources = self._get_stacks(self.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello world")
        self.assertNotIn("extra_message", lambda_response)

    def test_sync_watch_code(self):
        self.stack_resources = self._get_stacks(self.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)

        # change lambda with another output
        self.update_file(
            self.test_dir.joinpath("code", "after", "python_function_no_deps", "app_without_numpy.py"),
            self.test_dir.joinpath("code", "before", "python_function_no_deps", "app.py"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Layer HelloWorldFunction",
            timeout=60,
        )
        lambda_response = json.loads(self._get_lambda_response(lambda_functions[0]))
        self.assertEqual(lambda_response.get("message"), "hello mars")
        self.assertNotIn("extra_message", lambda_response)

        # change lambda with import with missing dependency
        self.update_file(
            self.test_dir.joinpath("code", "after", "python_function_no_deps", "app_with_numpy.py"),
            self.test_dir.joinpath("code", "before", "python_function_no_deps", "app.py"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Layer HelloWorldFunction",
            timeout=60,
        )
        self._confirm_lambda_error(lambda_functions[0])

        # add dependency and confirm it executes as expected
        self.update_file(
            self.test_dir.joinpath("code", "after", "python_function_no_deps", "requirements.txt"),
            self.test_dir.joinpath("code", "before", "python_function_no_deps", "requirements.txt"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Function Layer Reference Sync HelloWorldFunction.\x1b[0m\n",
            timeout=60,
        )

        def _verify_lambda_response(_lambda_response):
            self.assertEqual(lambda_response.get("message"), "hello mars")
            self.assertIn("extra_message", lambda_response)

        self._confirm_lambda_response(self._get_lambda_response(lambda_functions[0]), _verify_lambda_response)


@skipIf(SKIP_SYNC_TESTS or IS_WINDOWS, "Skip sync tests in CI/CD only")
class TestDisableAdlForEsbuildFunctions(SyncIntegBase):
    template_file = "code/before/template-esbuild.yaml"
    dependency_layer = True

    def test_sync_esbuild(self):
        template_path = str(self.test_data_path.joinpath(self.template_file))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        self.stack_resources = self._get_stacks(stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")

        layers = self.stack_resources.get(AWS_LAMBDA_LAYERVERSION)
        self.assertIsNone(layers)
