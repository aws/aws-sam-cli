"""
Tests OSUtils file
"""

import os
import shutil
import sys
import tempfile

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
    @patch("samcli.lib.utils.osutils.shutil.copytree")
    def test_must_copytree(self, patched_copytree):
        source_path = "mock-source/path"
        destination_path = "mock-destination/path"

        osutils.copytree(source_path, destination_path)

        patched_copytree.assert_called_once_with(
            source_path, destination_path, symlinks=True, ignore=None, dirs_exist_ok=True
        )

    @patch("samcli.lib.utils.osutils.shutil.copytree")
    def test_copytree_with_ignore(self, patched_copytree):
        source_path = "mock-source/path"
        destination_path = "mock-destination/path"
        mock_ignore = Mock()

        osutils.copytree(source_path, destination_path, ignore=mock_ignore)

        patched_copytree.assert_called_once_with(
            source_path, destination_path, symlinks=True, ignore=mock_ignore, dirs_exist_ok=True
        )

    @patch("samcli.lib.utils.osutils.shutil.copytree")
    def test_copytree_throws_oserror(self, patched_copytree):
        patched_copytree.side_effect = OSError("mock-os-error")

        with self.assertRaises(OSError):
            osutils.copytree("mock-source/path", "mock-destination/path")


class Test_copytree_symlinks(TestCase):
    """Integration-style tests verifying symlinks=True preserves symlinks on disk."""

    def setUp(self):
        self.src = tempfile.mkdtemp()
        self.dst = tempfile.mkdtemp()
        # clean dst so copytree creates it
        shutil.rmtree(self.dst)

    def tearDown(self):
        shutil.rmtree(self.src, ignore_errors=True)
        shutil.rmtree(self.dst, ignore_errors=True)

    def test_preserves_file_symlink(self):
        real_file = os.path.join(self.src, "real.txt")
        with open(real_file, "w") as f:
            f.write("content")
        os.symlink("real.txt", os.path.join(self.src, "link.txt"))

        osutils.copytree(self.src, self.dst)

        link = os.path.join(self.dst, "link.txt")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), "real.txt")

    def test_preserves_directory_symlink(self):
        subdir = os.path.join(self.src, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "file.txt"), "w") as f:
            f.write("content")
        os.symlink("subdir", os.path.join(self.src, "link_dir"))

        osutils.copytree(self.src, self.dst)

        link = os.path.join(self.dst, "link_dir")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), "subdir")


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
