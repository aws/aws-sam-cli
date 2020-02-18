"""
Tests OSUtils file
"""

import os
import sys

from unittest import TestCase
from unittest.mock import patch
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

    @patch("os.rmdir")
    def test_raises_on_cleanup_failure(self, rmdir_mock):
        rmdir_mock.side_effect = OSError("fail")
        with self.assertRaises(OSError):
            with osutils.mkdir_temp() as tempdir:
                self.assertTrue(os.path.exists(tempdir))

    @patch("os.rmdir")
    def test_handles_ignore_error_case(self, rmdir_mock):
        rmdir_mock.side_effect = OSError("fail")
        dir_name = None
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            dir_name = tempdir
            self.assertTrue(os.path.exists(tempdir))


class Test_stderr(TestCase):
    def test_must_return_sys_stderr(self):

        expected_stderr = sys.stderr

        if sys.version_info.major > 2:
            expected_stderr = sys.stderr.buffer

        self.assertEqual(expected_stderr, osutils.stderr())


class Test_stdout(TestCase):
    def test_must_return_sys_stdout(self):

        expected_stdout = sys.stdout

        if sys.version_info.major > 2:
            expected_stdout = sys.stdout.buffer

        self.assertEqual(expected_stdout, osutils.stdout())
