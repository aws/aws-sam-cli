import json
from unittest import TestCase

import os

from pathlib import Path

from parameterized import parameterized_class

from tests.end_to_end.end_to_end_base import EndToEndBase, EndToEndTestContext
from tests.end_to_end.test_stages import (
    DefaultInitStage,
    DefaultRemoteInvokeStage,
    DefaultDeleteStage,
    EndToEndBaseStage,
    DefaultSyncStage,
)
from tests.testing_utils import CommandResult


class HelloWorldValidators(TestCase):
    def default_command_output_validator(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)

    def validate_init(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        working_directory = Path(os.getcwd())
        self.assertTrue(Path.is_dir(working_directory))

    def validate_build(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        build_dir = Path(os.getcwd()) / ".aws-sam"
        self.assertTrue(build_dir.is_dir())

    def validate_remote_invoke(self, command_result: CommandResult):
        self.assertEqual(command_result.process.get("StatusCode"), 200)
        self.assertEqual(command_result.process.get("FunctionError", ""), "")

    def validate_stack_outputs(self, command_result: CommandResult):
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
        validators = HelloWorldValidators()
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_dir)
            build_command_list = self.get_command_list()
            deploy_command_list = self._get_deploy_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(validators.validate_init, init_command_list, self.app_name),
                EndToEndBaseStage(validators.validate_build, build_command_list),
                EndToEndBaseStage(validators.default_command_output_validator, deploy_command_list),
                DefaultRemoteInvokeStage(validators.validate_remote_invoke, stack_name),
                EndToEndBaseStage(validators.default_command_output_validator, stack_outputs_command_list),
                DefaultDeleteStage(validators.default_command_output_validator, delete_command_list, stack_name),
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
        validators = HelloWorldValidators()
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_dir)
            sync_command_list = self._get_sync_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stages = [
                DefaultInitStage(validators.validate_init, init_command_list, self.app_name),
                DefaultSyncStage(validators.default_command_output_validator, sync_command_list),
                DefaultRemoteInvokeStage(validators.validate_remote_invoke, stack_name),
                EndToEndBaseStage(validators.default_command_output_validator, stack_outputs_command_list),
                DefaultDeleteStage(validators.default_command_output_validator, delete_command_list, stack_name),
            ]
            self._run_tests(stages)
