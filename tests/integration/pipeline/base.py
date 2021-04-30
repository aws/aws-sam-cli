import os
import re
import shutil
from pathlib import Path
from typing import List
from unittest import TestCase

import boto3

from tests.testing_utils import run_command_with_input


class PipelineBase(TestCase):
    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def run_command_with_inputs(self, command_list, inputs: List[str]):
        return run_command_with_input(command_list, ("\n".join(inputs) + "\n").encode())


class InitIntegBase(PipelineBase):
    generated_files: List[Path] = []

    @classmethod
    def setUpClass(cls) -> None:
        # we need to compare the whole generated template, which is
        # larger than normal diff size limit
        cls.maxDiff = None

    def setUp(self) -> None:
        super().setUp()
        self.generated_files = []

    def tearDown(self) -> None:
        for generated_file in self.generated_files:
            if generated_file.is_dir():
                shutil.rmtree(generated_file)
            else:
                generated_file.unlink()
        super().tearDown()

    def get_init_command_list(
        self,
    ):
        command_list = [self.base_command(), "pipeline", "init"]
        return command_list


class BootstrapIntegBase(PipelineBase):
    stack_names: List[str]

    @classmethod
    def setUpClass(cls):
        cls.cf_client = boto3.client("cloudformation")
        pass

    def setUp(self):
        self.stack_names = []
        super().setUp()

    def tearDown(self):
        if self.stack_names:
            for stack_name in self.stack_names:
                self.cf_client.delete_stack(StackName=stack_name)
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "pipeline"), ignore_errors=True)
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_bootstrap_command_list(
        self,
        # right now we only support interactive mode
        interactive=True,
    ):
        command_list = [self.base_command(), "pipeline", "bootstrap"]

        if interactive:
            command_list = command_list + ["--interactive"]
        return command_list

    @staticmethod
    def _method_to_stage_name(method_name: str) -> str:
        """
        Method expects method name which can be a full path. Eg: test.integration.test_bootstrap_command.method_name
        """
        method_name = method_name.split(".")[-1]
        return method_name.replace("_", "-")

    @staticmethod
    def _extract_created_resources(stdout: str) -> List[str]:
        created_start = r"We have created the following resources.+"
        provided_start = r"You provided the following resources.+"
        configure_start = r"Please configure your.+"
        tokens = re.split(created_start, stdout)
        if len(tokens) == 1:
            # no resources created
            return []

        created_resources_section = tokens[1]
        # after created resource section, it might be provided resource section,
        # or configure credential section.
        # we use two split to find where it ends.
        created_resources_section = re.split(configure_start, created_resources_section)[0]
        created_resources_section = re.split(provided_start, created_resources_section)[0]
        # clean up and return the lines
        return [line.strip() for line in created_resources_section.split("\n") if line.strip()]

    @staticmethod
    def _count_created_resources(stdout: str) -> int:
        return len(BootstrapIntegBase._extract_created_resources(stdout))
