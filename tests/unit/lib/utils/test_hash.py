import os
import shutil
import tempfile
from unittest import TestCase

from samcli.lib.utils.hash import dir_checksum


class TestFile(TestCase):
    def setUp(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), "test_hash")
        os.mkdir(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dir_hash(self):
        _file = tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir)
        _file.write(b"Testfile")
        _file.close()
        self.assertEqual("774c0c0955d1d6574f518a5fd022d8b5", dir_checksum(self.temp_dir))
