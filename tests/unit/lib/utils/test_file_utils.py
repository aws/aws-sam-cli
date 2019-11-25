import os
import tempfile
from unittest import TestCase

from samcli.lib.utils.osutils import remove, tempfile_platform_independent


class TestFile(TestCase):
    def test_file_remove(self):
        _file = tempfile.NamedTemporaryFile(delete=False)
        _file.close()
        remove(_file.name)
        self.assertFalse(os.path.exists(_file.name))
        # No Exception thrown
        remove(os.path.join(os.getcwd(), "random"))

    def test_temp_file(self):
        _path = None
        with tempfile_platform_independent() as _tempf:
            _path = _tempf.name
        self.assertFalse(os.path.exists(_path))
