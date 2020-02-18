from unittest import TestCase
from subprocess import Popen
import os


class Test_EventGeneration_Integ(TestCase):
    def test_generate_event_substitution(self):
        process = Popen([Test_EventGeneration_Integ._get_command(), "local", "generate-event", "s3", "put"])
        process.communicate()
        self.assertEqual(process.returncode, 0)

    @staticmethod
    def _get_command():
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command
