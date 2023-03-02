from typing import List, Callable

from unittest import TestCase

import boto3
from pathlib import Path

import os

from tests.testing_utils import CommandResult, run_command, run_command_with_input


class EndToEndBaseStage(TestCase):
    def __init__(self, validator: Callable[[CommandResult], None], command_list: List[str] = None):
        super().__init__()
        self.validator = validator
        self.command_list = command_list

    def run_stage(self) -> CommandResult:
        return run_command(self.command_list)

    def validate(self, command_result: CommandResult):
        self.validator(command_result)


class DefaultInitStage(EndToEndBaseStage):
    def __init__(self, validator, command_list, app_name):
        super().__init__(validator, command_list)
        self.app_name = app_name

    def run_stage(self) -> CommandResult:
        command_result = run_command(self.command_list)
        self._delete_default_samconfig()
        os.chdir(Path(os.getcwd()) / self.app_name)
        return command_result

    def _delete_default_samconfig(self):
        # The default samconfig.toml has some properties that clash with the test parameters
        default_samconfig = Path(os.getcwd()) / self.app_name / "samconfig.toml"
        try:
            os.remove(default_samconfig)
        except Exception:
            pass


class DefaultRemoteInvokeStage(EndToEndBaseStage):
    def __init__(self, validator, stack_name):
        super().__init__(validator)
        self.stack_name = stack_name
        self.lambda_client = boto3.client("lambda")
        self.resource = boto3.resource("cloudformation")

    def run_stage(self) -> CommandResult:
        lambda_output = self.lambda_client.invoke(FunctionName=self._get_lambda_physical_id())
        return CommandResult(lambda_output, "", "")

    def _get_lambda_physical_id(self):
        return self.resource.StackResource(self.stack_name, "HelloWorldFunction").physical_resource_id


class DefaultDeleteStage(EndToEndBaseStage):
    def __init__(self, validator, command_list, stack_name):
        super().__init__(validator, command_list)
        self.command_list = command_list
        self.stack_name = stack_name
        self.cfn_client = boto3.client("cloudformation")


class DefaultSyncStage(EndToEndBaseStage):
    def run_stage(self) -> CommandResult:
        return run_command_with_input(self.command_list, "y\n".encode())
