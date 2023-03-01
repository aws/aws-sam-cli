from unittest import TestCase

import boto3
from pathlib import Path

import os

from tests.testing_utils import CommandResult, run_command, get_sam_command


class EndToEndBaseStage(TestCase):
    command_list = []

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
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list
        self.lambda_client = boto3.client("lambda")
        self.cfn_client = boto3.client("cloudformation")

    def run_stage(self) -> CommandResult:
        lambda_output = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        return CommandResult(lambda_output, "", "")

    def validate(self, command_result: CommandResult):
        self.assertEqual(command_result.process.get("StatusCode"), 200)
        self.assertEqual(command_result.process.get("FunctionError", ""), "")


class DefaultDeleteStage(EndToEndBaseStage):
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list

    def run_stage(self) -> CommandResult:
        pass

    def validate(self, command_result: CommandResult):
        pass
