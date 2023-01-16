import os
from unittest import TestCase

from tests.testing_utils import get_sam_command


class RootIntegBase(TestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def root_command_list(
        self,
        info=False,
        debug=False,
        version=False,
        _help=False,
    ):
        command_list = [get_sam_command()]

        if info:
            command_list += ["--info"]
        if debug:
            command_list += ["--debug"]
        if _help:
            command_list += ["--help"]
        if version:
            command_list += ["--version"]

        return command_list
