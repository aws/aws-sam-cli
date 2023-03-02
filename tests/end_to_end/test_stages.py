from typing import List

import json
from unittest import TestCase

import boto3
from botocore.exceptions import ClientError
from pathlib import Path

import os

from tests.testing_utils import CommandResult, run_command, run_command_with_input


class EndToEndBaseStage(TestCase):
    command_list: List[str] = []

    def run_stage(self) -> CommandResult:
        return run_command(self.command_list)

    def validate(self, command_result: CommandResult):
        raise NotImplementedError()


class DefaultInitStage(EndToEndBaseStage):
    def __init__(self, command_list, app_name):
        super().__init__()
        self.command_list = command_list
        self.app_name = app_name

    def run_stage(self) -> CommandResult:
        command_result = run_command(self.command_list)
        self._delete_default_samconfig()
        os.chdir(Path(os.getcwd()) / self.app_name)
        return command_result

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        working_directory = Path(os.getcwd())
        self.assertTrue(Path.is_dir(working_directory))

    def _delete_default_samconfig(self):
        # The default samconfig.toml has some properties that clash with the test parameters
        default_samconfig = Path(os.getcwd()) / self.app_name / "samconfig.toml"
        try:
            os.remove(default_samconfig)
        except Exception:
            pass


class DefaultBuildStage(EndToEndBaseStage):
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        build_dir = Path(os.getcwd()) / ".aws-sam"
        self.assertTrue(build_dir.is_dir())


class DefaultDeployStage(EndToEndBaseStage):
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)


class DefaultRemoteInvokeStage(EndToEndBaseStage):
    def __init__(self, stack_name):
        super().__init__()
        self.stack_name = stack_name
        self.lambda_client = boto3.client("lambda")
        self.resource = boto3.resource("cloudformation")

    def run_stage(self) -> CommandResult:
        lambda_output = self.lambda_client.invoke(FunctionName=self._get_lambda_physical_id())
        return CommandResult(lambda_output, "", "")

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.get("StatusCode"), 200)
        self.assertEqual(command_result.process.get("FunctionError", ""), "")

    def _get_lambda_physical_id(self):
        return self.resource.StackResource(self.stack_name, "HelloWorldFunction").physical_resource_id


class DefaultStackOutputsStage(EndToEndBaseStage):
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        stack_outputs = json.loads(command_result.stdout.decode())
        self.assertEqual(len(stack_outputs), 3)
        for output in stack_outputs:
            self.assertIn("OutputKey", output)
            self.assertIn("OutputValue", output)
            self.assertIn("Description", output)


class DefaultDeleteStage(EndToEndBaseStage):
    def __init__(self, command_list, stack_name):
        super().__init__()
        self.command_list = command_list
        self.stack_name = stack_name
        self.cfn_client = boto3.client("cloudformation")

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
        self.assertFalse(self._check_cfn_stack_exists())

    def _check_cfn_stack_exists(self):
        try:
            self.cfn_client.describe_stacks(StackName=self.stack_name)
        except ClientError as ex:
            if "does not exist" in ex.args[0]:
                return False
        return True


class DefaultSyncStage(EndToEndBaseStage):
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list

    def run_stage(self) -> CommandResult:
        return run_command_with_input(self.command_list, "y\n".encode())

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.returncode, 0)
