import os
from pathlib import Path
from unittest import TestCase


class CheckIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "check")

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_minimal_check_command_list(self, template=None, config_file=None, load=False):
        command_list = [self.base_command(), "check"]

        if template:
            command_list = command_list + ["--template-file", str(template)]
        if config_file:
            command_list = command_list + ["--config-file", str(config_file)]
        if load:
            command_list = command_list + ["--load", str(load)]

        return command_list
