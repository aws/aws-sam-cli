import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import patch

from samcli.lib.utils.hash import dir_checksum, str_checksum


class TestHash(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dir_hash_independent_of_location(self):
        temp_dir1 = os.path.join(self.temp_dir, "temp-dir-1")
        os.mkdir(temp_dir1)
        with open(os.path.join(temp_dir1, "test-file"), "w+") as f:
            f.write("Testfile")
        checksum1 = dir_checksum(temp_dir1)

        temp_dir2 = shutil.move(temp_dir1, os.path.join(self.temp_dir, "temp-dir-2"))
        checksum2 = dir_checksum(temp_dir2)

        self.assertEqual(checksum1, checksum2)

    def test_dir_hash_independent_of_file_order(self):
        file1 = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir)
        file1.write(b"Testfile")
        file1.close()

        file2 = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir)
        file2.write(b"Testfile")
        file2.close()

        dir_checksums = {}
        with patch("os.walk") as mockwalk:
            mockwalk.return_value = [
                (
                    self.temp_dir,
                    (),
                    (
                        file1.name,
                        file2.name,
                    ),
                ),
            ]
            dir_checksums["first"] = dir_checksum(self.temp_dir)

        with patch("os.walk") as mockwalk:
            mockwalk.return_value = [
                (
                    self.temp_dir,
                    (),
                    (
                        file2.name,
                        file1.name,
                    ),
                ),
            ]
            dir_checksums["second"] = dir_checksum(self.temp_dir)

        self.assertEqual(dir_checksums["first"], dir_checksums["second"])

    def test_dir_hash_same_contents_diff_file_per_directory(self):
        _file = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir)
        _file.write(b"Testfile")
        _file.close()
        checksum_before = dir_checksum(os.path.dirname(_file.name))
        shutil.move(os.path.abspath(_file.name), os.path.join(os.path.dirname(_file.name), "different_name"))
        checksum_after = dir_checksum(os.path.dirname(_file.name))
        self.assertNotEqual(checksum_before, checksum_after)

    def test_dir_cyclic_links(self):
        _file = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir)
        _file.write(b"Testfile")
        _file.close()
        os.symlink(os.path.abspath(_file.name), os.path.join(os.path.dirname(_file.name), "symlink"))
        os.symlink(
            os.path.join(os.path.dirname(_file.name), "symlink"), os.path.join(os.path.dirname(_file.name), "symlink2")
        )
        os.unlink(os.path.abspath(_file.name))
        os.symlink(os.path.join(os.path.dirname(_file.name), "symlink2"), os.path.abspath(_file.name))
        with self.assertRaises(OSError) as ex:
            dir_checksum(os.path.dirname(_file.name))
            self.assertIn("Too many levels of symbolic links", ex.message)

    def test_str_checksum(self):
        checksum = str_checksum("Hello, World!")
        self.assertEqual(checksum, "65a8e27d8879283831b664bd8b7f0ad4")
