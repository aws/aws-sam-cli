import stat
import zipfile
import os
import shutil
from unittest import TestCase
from contextlib import contextmanager
from tempfile import NamedTemporaryFile, mkdtemp
from mock import Mock, patch

from nose_parameterized import parameterized, param

from samcli.local.lambdafn.zip import unzip, unzip_from_uri, _override_permissions


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


class TestUnzipFromUri(TestCase):

    @patch('samcli.local.lambdafn.zip.unzip')
    @patch('samcli.local.lambdafn.zip.Path')
    @patch('samcli.local.lambdafn.zip.progressbar')
    @patch('samcli.local.lambdafn.zip.requests')
    @patch('samcli.local.lambdafn.zip.open')
    def test_successfully_unzip_from_uri(self, open_patch, requests_patch, progressbar_patch, path_patch, unzip_patch):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b'data1']
        requests_patch.get.return_value = get_request_mock

        file_mock = Mock()
        open_patch.return_value.__enter__.return_value = file_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = True
        path_patch.return_value = path_mock

        unzip_from_uri('uri', 'layer_zip_path', 'output_zip_dir', 'layer_arn')

        requests_patch.get.assert_called_with('uri', stream=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        open_patch.assert_called_with('layer_zip_path', 'wb')
        file_mock.write.assert_called_with(b'data1')
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with('layer_zip_path')
        path_mock.unlink.assert_called()
        unzip_patch.assert_called_with('layer_zip_path', 'output_zip_dir', permission=0o700)

    @patch('samcli.local.lambdafn.zip.unzip')
    @patch('samcli.local.lambdafn.zip.Path')
    @patch('samcli.local.lambdafn.zip.progressbar')
    @patch('samcli.local.lambdafn.zip.requests')
    @patch('samcli.local.lambdafn.zip.open')
    def test_not_unlink_file_when_file_doesnt_exist(self,
                                                    open_patch,
                                                    requests_patch,
                                                    progressbar_patch,
                                                    path_patch,
                                                    unzip_patch):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b'data1']
        requests_patch.get.return_value = get_request_mock

        file_mock = Mock()
        open_patch.return_value.__enter__.return_value = file_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = False
        path_patch.return_value = path_mock

        unzip_from_uri('uri', 'layer_zip_path', 'output_zip_dir', 'layer_arn')

        requests_patch.get.assert_called_with('uri', stream=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        open_patch.assert_called_with('layer_zip_path', 'wb')
        file_mock.write.assert_called_with(b'data1')
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with('layer_zip_path')
        path_mock.unlink.assert_not_called()
        unzip_patch.assert_called_with('layer_zip_path', 'output_zip_dir', permission=0o700)


class TestOverridePermissions(TestCase):

    @patch('samcli.local.lambdafn.zip.os')
    def test_must_override_permissions(self, os_patch):
        _override_permissions(path="./home", permission=0o700)

        os_patch.chmod.assert_called_once_with("./home", 0o700)

    @patch('samcli.local.lambdafn.zip.os')
    def test_must_not_override_permissions(self, os_patch):
        _override_permissions(path="./home", permission=None)

        os_patch.chmod.assert_not_called()
