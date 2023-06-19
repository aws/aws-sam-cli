from unittest import skipIf

import json
from pathlib import Path

from parameterized import parameterized_class

from tests.end_to_end.end_to_end_base import EndToEndBase
from tests.end_to_end.end_to_end_context import EndToEndTestContext
from tests.end_to_end.test_stages import (
    DefaultInitStage,
    PackageDownloadZipFunctionStage,
    DefaultDeleteStage,
    EndToEndBaseStage,
    DefaultSyncStage,
    BaseValidator,
)
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_E2E_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
from tests.testing_utils import CommandResult


class InitValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(Path(self.test_context.working_directory).is_dir())
        self.assertTrue(Path(self.test_context.project_directory).is_dir())


class BuildValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        build_dir = Path(self.test_context.project_directory) / ".aws-sam"
        self.assertTrue(build_dir.is_dir())


class LocalInvokeValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        response = json.loads(command_result.stdout.decode("utf-8").split("\n")[-1])
        self.assertEqual(command_result.process.returncode, 0)
        self.assertEqual(response["statusCode"], 200)


class RemoteInvokeValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        response = json.loads(command_result.stdout.decode("utf-8"))
        self.assertEqual(command_result.process.returncode, 0)
        self.assertEqual(response["StatusCode"], 200)
        self.assertEqual(response.get("FunctionError", ""), "")


class StackOutputsValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        stack_outputs = json.loads(command_result.stdout.decode())
        self.assertEqual(len(stack_outputs), 3)
        for output in stack_outputs:
            self.assertIn("OutputKey", output)
            self.assertIn("OutputValue", output)
            self.assertIn("Description", output)


@skipIf(SKIP_E2E_TESTS, "Skip E2E tests in CI/CD only")
@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.7", "pip"),
    ],
)
class TestHelloWorldDefaultEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_hello_world_default_workflow(self):
        stack_name = self._method_to_stack_name(self.id())
        function_name = "HelloWorldFunction"
        event = '{"hello": "world"}'
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_directory)
            build_command_list = self.get_command_list()
            deploy_command_list = self._get_deploy_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            remote_invoke_command_list = self._get_remote_invoke_command(stack_name, function_name, event, "json")
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(InitValidator(e2e_context), e2e_context, init_command_list, self.app_name),
                EndToEndBaseStage(BuildValidator(e2e_context), e2e_context, build_command_list),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, deploy_command_list),
                EndToEndBaseStage(RemoteInvokeValidator(e2e_context), e2e_context, remote_invoke_command_list),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, stack_outputs_command_list),
                DefaultDeleteStage(BaseValidator(e2e_context), e2e_context, delete_command_list, stack_name),
            ]
            self._run_tests(stages)


@skipIf(SKIP_E2E_TESTS, "Skip E2E tests in CI/CD only")
@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.7", "pip"),
    ],
)
class TestHelloWorldZipPackagePermissionsEndToEnd(EndToEndBase):
    """This end to end test is to ensure the zip file created using sam package
    has the required permissions to invoke the Function.
    """

    app_template = "hello-world"

    def test_hello_world_workflow(self):
        function_name = "HelloWorldFunction"
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_directory)
            build_command_list = self.get_command_list()
            package_command_list = self._get_package_command(
                s3_prefix="end-to-end-package-test", use_json=True, output_template_file="packaged_template.json"
            )
            local_command_list = self._get_local_command(function_name)
            stages = [
                DefaultInitStage(InitValidator(e2e_context), e2e_context, init_command_list, self.app_name),
                EndToEndBaseStage(BuildValidator(e2e_context), e2e_context, build_command_list),
                PackageDownloadZipFunctionStage(
                    BaseValidator(e2e_context), e2e_context, package_command_list, function_name
                ),
                EndToEndBaseStage(LocalInvokeValidator(e2e_context), e2e_context, local_command_list),
            ]
            self._run_tests(stages)


@skipIf(SKIP_E2E_TESTS, "Skip E2E tests in CI/CD only")
@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.7", "pip"),
    ],
)
class TestHelloWorldDefaultSyncEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        function_name = "HelloWorldFunction"
        event = '{"hello": "world"}'
        stack_name = self._method_to_stack_name(self.id())
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_directory)
            sync_command_list = self._get_sync_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            remote_invoke_command_list = self._get_remote_invoke_command(stack_name, function_name, event, "json")
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(InitValidator(e2e_context), e2e_context, init_command_list, self.app_name),
                DefaultSyncStage(BaseValidator(e2e_context), e2e_context, sync_command_list),
                EndToEndBaseStage(RemoteInvokeValidator(e2e_context), e2e_context, remote_invoke_command_list),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, stack_outputs_command_list),
                DefaultDeleteStage(BaseValidator(e2e_context), e2e_context, delete_command_list, stack_name),
            ]
            self._run_tests(stages)
