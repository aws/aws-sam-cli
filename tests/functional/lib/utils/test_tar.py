import os
import tempfile
import shutil
import platform
from pathlib import Path
from tarfile import ExtractError

from unittest import TestCase

from samcli.lib.utils.tar import extract_tarfile


class TestExtractTarFile(TestCase):
    def test_extract_tarfile_arg_path_unpacks_a_tar(self):
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", "test.tgz")
        test_dir = tempfile.mkdtemp()
        extract_tarfile(tarfile_path=test_tar, unpack_dir=test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_raise_exception_for_unsafe_tarfile_with_path_arg(self):
        tar_filename = "path_reversal_win.tgz" if platform.system().lower() == "windows" else "path_reversal_uxix.tgz"
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", tar_filename)
        test_dir = tempfile.mkdtemp()
        self.assertRaisesRegex(
            ExtractError,
            "Attempted Path Traversal in Tar File",
            extract_tarfile,
            tarfile_path=test_tar,
            unpack_dir=test_dir,
        )
        shutil.rmtree(test_dir)

    def test_extract_tarfile_arg_fileobj_unpacks_a_tar(self):
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", "test.tgz")
        test_dir = tempfile.mkdtemp()
        with open(test_tar, mode="rb") as tar:
            before_extract_output_files = set(os.listdir(test_dir))
            self.assertEqual(set(), before_extract_output_files)
            extract_tarfile(file_obj=tar, unpack_dir=test_dir)
            after_extract_output_files = set(os.listdir(test_dir))
            self.assertEqual({"test_utils.py"}, after_extract_output_files)
        shutil.rmtree(test_dir)

    def test_raise_exception_for_unsafe_tarfile_with_flieobj_arg(self):
        tar_filename = "path_reversal_win.tgz" if platform.system().lower() == "windows" else "path_reversal_uxix.tgz"
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", tar_filename)
        test_dir = tempfile.mkdtemp()
        with open(test_tar, mode="rb") as tar:
            self.assertRaisesRegex(
                ExtractError,
                "Attempted Path Traversal in Tar File",
                extract_tarfile,
                file_obj=tar,
                unpack_dir=test_dir,
            )
        shutil.rmtree(test_dir)
