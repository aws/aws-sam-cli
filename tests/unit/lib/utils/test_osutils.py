"""
Tests OSUtils file
"""

import os
import sys

from unittest import TestCase
import samcli.lib.utils.osutils as osutils


class Test_mkdir_temp(TestCase):

    def test_must_return_temp_dir(self):

        with osutils.mkdir_temp() as tempdir:
            self.assertTrue(os.path.exists(tempdir))

    def test_must_delete_temp_dir_after_use(self):

        dir_name = None
        with osutils.mkdir_temp() as tempdir:
            dir_name = tempdir
            self.assertTrue(os.path.exists(tempdir))

        self.assertFalse(os.path.exists(dir_name))


class Test_stderr(TestCase):

    def test_must_return_sys_stderr(self):

        expected_stderr = sys.stderr

        if sys.version_info.major > 2:
            expected_stderr = sys.stderr.buffer

        self.assertEquals(expected_stderr, osutils.stderr())


class Test_stdout(TestCase):

    def test_must_return_sys_stdout(self):

        expected_stdout = sys.stdout

        if sys.version_info.major > 2:
            expected_stdout = sys.stdout.buffer

        self.assertEquals(expected_stdout, osutils.stdout())
