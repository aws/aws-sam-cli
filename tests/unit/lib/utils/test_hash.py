import os
import shutil
import tempfile
from unittest import TestCase

from samcli.lib.utils.hash import dir_checksum


class TestHash(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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
