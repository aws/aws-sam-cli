import os
from unittest import TestCase
from pathlib import Path
import uuid
import shutil
import tempfile
from tests.integration.list.list_integ_base import ListIntegBase


class StackOutputsIntegBase(ListIntegBase, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def get_stack_outputs_command_list(self, stack_name=None, output=None, help=False):
        command_list = [self.base_command(), "list", "stack-outputs"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]

        if output:
            command_list += ["--output", str(output)]

        if help:
            command_list += ["--help"]

        return command_list
