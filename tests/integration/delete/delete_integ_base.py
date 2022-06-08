import os
from pathlib import Path
from typing import Optional
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
        self,
        stack_name: Optional[str] = None,
        region: Optional[str] = None,
        config_file: Optional[str] = None,
        config_env: Optional[str] = None,
        profile: Optional[str] = None,
        no_prompts: Optional[bool] = None,
        s3_bucket: Optional[str] = None,
        s3_prefix: Optional[str] = None,
    ):
        command_list = [self.base_command(), "delete"]

        if stack_name:
            command_list += ["--stack-name", stack_name]
        if region:
            command_list += ["--region", region]
        if config_file:
            command_list += ["--config-file", config_file]
        if config_env:
            command_list += ["--config-env", config_env]
        if profile:
            command_list += ["--profile", profile]
        if no_prompts:
            command_list += ["--no-prompts"]
        if s3_bucket:
            command_list += ["--s3-bucket", s3_bucket]
        if s3_prefix:
            command_list += ["--s3-prefix", s3_prefix]

        return command_list
