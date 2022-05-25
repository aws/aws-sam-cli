import os
from typing import Optional
from unittest import TestCase, skipIf
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired

class ResourcesIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()
        cls.resources_test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "delete")

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_resources_command_list(self, stack_name=None, output=None):
        command_list = [self.base_command(), "list", "resources"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]

        if output:
            command_list += ["--output", str(output)]
