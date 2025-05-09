"""
Tests OSUtils file
"""

import os
import sys

from unittest import TestCase
from unittest.mock import patch, Mock
from samcli.lib.utils import osutils
from samcli.lib.utils.osutils import rmtree_if_exists


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
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            self.assertTrue(os.path.exists(tempdir))


class Test_stderr(TestCase):
    def test_must_return_sys_stderr(self):
        expected_stderr = sys.stderr

        self.assertEqual(expected_stderr, osutils.stderr())


class Test_stdout(TestCase):
    def test_must_return_sys_stdout(self):
        expected_stdout = sys.stdout

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


class Test_rmtree_if_exists(TestCase):
    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.shutil.rmtree")
    def test_must_skip_if_path_doesnt_exist(self, patched_rmtree, patched_path):
        mock_path_obj = Mock()
        mock_path_obj.exists.return_value = False
        patched_path.return_value = mock_path_obj

        rmtree_if_exists(Mock())
        patched_rmtree.assert_not_called()

    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.shutil.rmtree")
    def test_must_delete_if_path_exist(self, patched_rmtree, patched_path):
        mock_path_obj = Mock()
        mock_path_obj.exists.return_value = True
        patched_path.return_value = mock_path_obj

        rmtree_if_exists(Mock())
        patched_rmtree.assert_called_with(mock_path_obj)


class Test_copytree(TestCase):
    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.utils.osutils.shutil.copy2")
    def test_must_copytree(self, patched_copy2, patched_os, patched_path):
        source_path = "mock-source/path"
        destination_path = "mock-destination/path"
        mock_path_obj = Mock()
        patched_path.exists.return_value = True
        patched_os.path.return_value = mock_path_obj

        patched_os.path.join.side_effect = [source_path, destination_path]
        patched_os.path.isdir.return_value = False
        patched_os.listdir.return_value = ["mock-source-file1"]
        osutils.copytree(source_path, destination_path)

        patched_os.path.join.assert_called()
        patched_copy2.assert_called_with(source_path, destination_path, follow_symlinks=False)

    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.utils.osutils.shutil.copy2")
    def test_copytree_throws_oserror_path_exists(self, patched_copy2, patched_os, patched_path):
        source_path = "mock-source/path"
        destination_path = "mock-destination/path"
        mock_path_obj = Mock()
        patched_path.exists.return_value = True
        patched_os.path.return_value = mock_path_obj
        patched_copy2.side_effect = OSError("mock-os-error")

        patched_os.path.join.side_effect = [source_path, destination_path]
        patched_os.path.isdir.return_value = False
        patched_os.listdir.return_value = ["mock-source-file1"]
        with self.assertRaises(OSError):
            osutils.copytree(source_path, destination_path)

        patched_os.path.join.assert_called()
        patched_copy2.assert_called_with(source_path, destination_path, follow_symlinks=False)

    @patch("samcli.lib.utils.osutils.create_symlink_or_copy")
    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.utils.osutils.shutil.copy2")
    def test_copytree_symlink_copy_error_handling(
        self, patched_copy2, patched_os, patched_path, patched_create_symlink_or_copy
    ):
        source_path = "mock-source/path"
        destination_path = "mock-destination/path"
        mock_path_obj = Mock()
        patched_path.exists.return_value = True
        patched_os.path.return_value = mock_path_obj
        patched_copy2.side_effect = OSError(22, "mock-os-error")

        patched_os.path.join.side_effect = [source_path, destination_path]
        patched_os.path.isdir.return_value = False
        patched_os.listdir.return_value = ["mock-source-file1"]
        osutils.copytree(source_path, destination_path)

        patched_os.path.join.assert_called()
        patched_copy2.assert_called_with(source_path, destination_path, follow_symlinks=False)
        patched_create_symlink_or_copy.assert_called_with(source_path, destination_path)


class Test_create_symlink_or_copy(TestCase):
    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.utils.osutils.copytree")
    def test_must_create_symlink_with_absolute_path(self, patched_copy_tree, pathced_os, patched_path):
        source_path = "source/path"
        destination_path = "destination/path"
        osutils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_called_with(
            patched_path(source_path).absolute(), patched_path(destination_path).absolute()
        )
        patched_copy_tree.assert_not_called()

    @patch("samcli.lib.utils.osutils.Path")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.utils.osutils.copytree")
    def test_must_copy_if_symlink_fails(self, patched_copy_tree, pathced_os, patched_path):
        pathced_os.symlink.side_effect = OSError("Unable to create symlink")

        source_path = "source/path"
        destination_path = "destination/path"
        osutils.create_symlink_or_copy(source_path, destination_path)

        pathced_os.symlink.assert_called_once()
        patched_copy_tree.assert_called_with(source_path, destination_path)
