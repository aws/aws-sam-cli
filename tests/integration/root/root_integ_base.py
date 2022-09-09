import os
from unittest import TestCase


class RootIntegBase(TestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    @staticmethod
    def base_command():
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def root_command_list(
        self,
        info=False,
        debug=False,
        version=False,
        _help=False,
    ):
        command_list = [RootIntegBase.base_command()]

        if info:
            command_list += ["--info"]
        if debug:
            command_list += ["--debug"]
        if _help:
            command_list += ["--help"]
        if version:
            command_list += ["--version"]

        return command_list
