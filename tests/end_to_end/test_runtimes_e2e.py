import json

from pathlib import Path

from parameterized import parameterized_class

from tests.end_to_end.end_to_end_base import EndToEndBase
from tests.end_to_end.end_to_end_context import EndToEndTestContext
from tests.end_to_end.test_stages import (
    DefaultInitStage,
    DefaultRemoteInvokeStage,
    DefaultDeleteStage,
    EndToEndBaseStage,
    DefaultSyncStage,
    BaseValidator,
)
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


class RemoteInvokeValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.get("StatusCode"), 200)
        self.assertEqual(command_result.process.get("FunctionError", ""), "")


class StackOutputsValidator(BaseValidator):
    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        stack_outputs = json.loads(command_result.stdout.decode())
        self.assertEqual(len(stack_outputs), 3)
        for output in stack_outputs:
            self.assertIn("OutputKey", output)
            self.assertIn("OutputValue", output)
            self.assertIn("Description", output)


@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.9", "pip"),
    ],
)
class TestHelloWorldDefaultEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        stack_name = self._method_to_stack_name(self.id())
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_directory)
            build_command_list = self.get_command_list()
            deploy_command_list = self._get_deploy_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(InitValidator(e2e_context), e2e_context, init_command_list, self.app_name),
                EndToEndBaseStage(BuildValidator(e2e_context), e2e_context, build_command_list),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, deploy_command_list),
                DefaultRemoteInvokeStage(RemoteInvokeValidator(e2e_context), e2e_context, stack_name),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, stack_outputs_command_list),
                DefaultDeleteStage(BaseValidator(e2e_context), e2e_context, delete_command_list, stack_name),
            ]
            self._run_tests(stages)


@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.9", "pip"),
    ],
)
class TestHelloWorldDefaultSyncEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        stack_name = self._method_to_stack_name(self.id())
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_directory)
            sync_command_list = self._get_sync_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(InitValidator(e2e_context), e2e_context, init_command_list, self.app_name),
                DefaultSyncStage(BaseValidator(e2e_context), e2e_context, sync_command_list),
                DefaultRemoteInvokeStage(RemoteInvokeValidator(e2e_context), e2e_context, stack_name),
                EndToEndBaseStage(BaseValidator(e2e_context), e2e_context, stack_outputs_command_list),
                DefaultDeleteStage(BaseValidator(e2e_context), e2e_context, delete_command_list, stack_name),
            ]
            self._run_tests(stages)
