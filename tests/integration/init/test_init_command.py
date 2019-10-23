from unittest import TestCase
from subprocess import Popen
import os
import tempfile


class TestBasicInitCommand(TestCase):
    def test_init_command_passes_and_dir_created(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen([TestBasicInitCommand._get_command(), "init", "-o", temp])
            return_code = process.wait()

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.isdir(temp + "/sam-app"))

    @staticmethod
    def _get_command():
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command
