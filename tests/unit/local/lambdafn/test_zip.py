
import stat
import zipfile
import os
import shutil

from samcli.local.lambdafn.zip import unzip

from tempfile import NamedTemporaryFile, mkdtemp
from contextlib import contextmanager
from unittest import TestCase
from nose_parameterized import parameterized, param


class TestUnzipWithPermissions(TestCase):

    files_with_permissions = {
        "folder1/1.txt": 0o644,
        "folder1/2.txt": 0o777,
        "folder2/subdir/1.txt": 0o666,
        "folder2/subdir/2.txt": 0o400
    }

    @parameterized.expand([param(True), param(False)])
    def test_must_unzip(self, check_permissions):

        with self._create_zip(self.files_with_permissions, check_permissions) as zip_file_name:
            with self._temp_dir() as extract_dir:

                unzip(zip_file_name, extract_dir)

                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        filepath = os.path.join(extract_dir, root, file)
                        perm = oct(stat.S_IMODE(os.stat(filepath).st_mode))
                        key = os.path.relpath(filepath, extract_dir)
                        expected_permission = oct(self.files_with_permissions[key])

                        self.assertIn(key, self.files_with_permissions)

                        if check_permissions:
                            self.assertEquals(expected_permission,
                                              perm,
                                              "File {} has wrong permission {}".format(key, perm))

    @contextmanager
    def _create_zip(self, files_with_permissions, add_permissions=True):

        zipfilename = None
        data = b'hello world'
        try:
            zipfilename = NamedTemporaryFile(mode="w+b").name

            zf = zipfile.ZipFile(zipfilename, "w", zipfile.ZIP_DEFLATED)
            for filename, perm in files_with_permissions.items():
                fileinfo = zipfile.ZipInfo(filename)

                if add_permissions:
                    fileinfo.external_attr = perm << 16

                zf.writestr(fileinfo, data)

            zf.close()

            yield zipfilename

        finally:
            if zipfilename:
                os.remove(zipfilename)

    @contextmanager
    def _temp_dir(self):
        name = None
        try:
            name = mkdtemp()
            yield name
        finally:
            if name:
                shutil.rmtree(name)
