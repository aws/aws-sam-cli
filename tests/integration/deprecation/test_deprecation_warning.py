import os
import subprocess
import sys

from unittest import TestCase

from samcli.cli.command import DEPRECATION_NOTICE


class TestPy2DeprecationWarning(TestCase):
    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def run_cmd(self):
        # Checking with base command to see if warning is present if running in python2
        cmd_list = [self.base_command()]
        process = subprocess.Popen(cmd_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return process

    def test_print_deprecation_warning_if_py2(self):
        process = self.run_cmd()
        (stdoutdata, stderrdata) = process.communicate()

        # Deprecation notice should be part of the command output if running in python 2
        if sys.version_info.major == 2:
            self.assertIn(DEPRECATION_NOTICE, stderrdata.decode())
