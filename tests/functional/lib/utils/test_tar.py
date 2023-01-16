import os
import tempfile
import shutil
import platform
from pathlib import Path
from tarfile import ExtractError

from unittest import TestCase

from samcli.lib.utils.tar import extract_tarfile


class TestExtractTarFile(TestCase):
    def test_extract_tarfile_unpacks_a_tar(self):
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", "test.tgz")
        test_dir = tempfile.mkdtemp()
        extract_tarfile(test_tar, test_dir)
        output_files = set(os.listdir(test_dir))
        shutil.rmtree(test_dir)
        print(output_files)
        self.assertEqual({"test_utils.py"}, output_files)

    def test_raise_exception_for_unsafe_tarfile(self):
        tar_filename = "path_reversal_win.tgz" if platform.system().lower() == "windows" else "path_reversal_uxix.tgz"
        test_tar = Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "lib", "utils", tar_filename)
        test_dir = tempfile.mkdtemp()
        self.assertRaisesRegex(
            ExtractError, "Attempted Path Traversal in Tar File", extract_tarfile, test_tar, test_dir
        )
