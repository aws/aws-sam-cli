import os
from pathlib import Path
from unittest import TestCase


class DeleteIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delete_test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "delete")

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_delete_command_list(
        self, stack_name=None, region=None, config_file=None, config_env=None, profile=None, no_prompts=None
    ):
        command_list = [self.base_command(), "delete"]

        if stack_name:
            command_list += ["--stack-name", str(stack_name)]
        if region:
            command_list += ["--region", str(region)]
        if config_file:
            command_list += ["--config-file", str(config_file)]
        if config_env:
            command_list += ["--config-env", str(config_env)]
        if profile:
            command_list += ["--profile", str(profile)]
        if no_prompts:
            command_list += ["--no-prompts"]

        return command_list
