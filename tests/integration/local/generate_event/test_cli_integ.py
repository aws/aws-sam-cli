from unittest import TestCase
from subprocess import Popen
import os

from tests.testing_utils import get_sam_command


class Test_EventGeneration_Integ(TestCase):
    def test_generate_event_substitution(self):
        process = Popen([get_sam_command(), "local", "generate-event", "s3", "put"])
        process.communicate()
        self.assertEqual(process.returncode, 0)
