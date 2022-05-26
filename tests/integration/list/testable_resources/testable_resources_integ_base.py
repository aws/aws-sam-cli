import os
from unittest import TestCase
from pathlib import Path
import uuid
import shutil
import tempfile


class TestableResourcesIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()
        cls.testable_resources_test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "list")

    def setUp(self):
        super().setUp()
        self.scratch_dir = str(Path(__file__).resolve().parent.joinpath(str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.mkdir(self.scratch_dir)

        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)

    def tearDown(self):
        super().tearDown()

    @classmethod
    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_testable_resources_command_list(self, stack_name=None, output=None, help=False):
        command_list = [self.base_command(), "list", "testable-resources"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]

        if output:
            command_list += ["--output", str(output)]

        if help:
            command_list += ["--help"]

        return command_list
