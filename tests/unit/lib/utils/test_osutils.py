"""
Tests OSUtils file
"""

import os
import sys

from unittest import TestCase
from unittest.mock import patch
from samcli.lib.utils import osutils


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


class Test_convert_files_to_unix_line_endings:
    @patch("os.walk")
    @patch("builtins.open")
    def test_must_return_sys_stdout(self, patched_open, os_walk):
        target_file = "target_file"
        os_walk.return_value = [
            ("a", "_", ("file_a_1", "file_a_2", target_file)),
            ("b", "_", ("file_b_1", target_file)),
        ]
        osutils.convert_files_to_unix_line_endings("path", [target_file])
        patched_open.assert_any_call(os.path.join("a", target_file), "rb")
        patched_open.assert_any_call(os.path.join("b", target_file), "rb")
        patched_open.assert_any_call(os.path.join("a", target_file), "wb")
        patched_open.assert_any_call(os.path.join("b", target_file), "wb")
