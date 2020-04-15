import os
import platform
import shutil
import stat
import zipfile
from contextlib import contextmanager
from tempfile import NamedTemporaryFile, mkdtemp
from unittest import TestCase
from unittest import skipIf
from unittest.mock import Mock, patch
from parameterized import parameterized, param

from samcli.local.lambdafn.zip import unzip, unzip_from_uri, _override_permissions

# On Windows, permissions do not match 1:1 with permissions on Unix systems.
SKIP_UNZIP_PERMISSION_TESTS = platform.system() == "Windows"


@skipIf(SKIP_UNZIP_PERMISSION_TESTS, "Skip UnZip Permissions tests in Windows only")
class TestUnzipWithPermissions(TestCase):
    """
    External Attribute Magic = type + permission + DOS is-dir flag?

    TTTTugsrwxrwxrwx0000000000ADVSHR
    ^^^^____________________________ File Type [UPPER 4 bits, 29-32]
        ^___________________________ setuid [bit 28]
         ^__________________________ setgid [bit 27]
          ^_________________________ sticky [bit 26]
           ^^^^^^^^^________________ Permissions [bits 17-25]
                    ^^^^^^^^________ Other [bits 9-16]
                            ^^^^^^^^ DOS attribute bits: [LOWER 8 bits]

    Interesting File Types
    S_IFDIR  0040000  /* directory */
    S_IFREG  0100000  /* regular */
    S_IFLNK  0120000  /* symbolic link */

    See: https://unix.stackexchange.com/questions/14705/%20the-zip-formats-external-file-attribute
    """

    files_with_external_attr = {
        "1.txt": {"file_type": 0o10, "contents": b"foo", "permissions": 0o644},
        "folder1/2.txt": {"file_type": 0o10, "contents": b"bar", "permissions": 0o777},
        "folder2/subdir/3.txt": {"file_type": 0o10, "contents": b"foo bar", "permissions": 0o666},
        "folder2/subdir/4.txt": {"file_type": 0o10, "contents": b"bar foo", "permissions": 0o400},
        "symlinkToF2": {"file_type": 0o12, "contents": b"1.txt", "permissions": 0o644},
    }

    expected_files = 0
    expected_symlinks = 0
    actual_files = 0
    actual_symlinks = 0

    @parameterized.expand([param(True), param(False)])
    def test_must_unzip(self, verify_external_attributes):
        self._reset(verify_external_attributes)

        with self._create_zip(self.files_with_external_attr, verify_external_attributes) as zip_file_name:
            with self._temp_dir() as extract_dir:
                unzip(zip_file_name, extract_dir)

                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        self._verify_file(extract_dir, file, root, verify_external_attributes)

        self._verify_file_count(verify_external_attributes)

    @contextmanager
    def _reset(self, verify_external_attributes):
        self.expected_files = 0
        self.expected_symlinks = 0
        self.actual_files = 0
        self.actual_symlinks = 0
        if verify_external_attributes:
            for filename, data in self.files_with_external_attr.items():
                if data["file_type"] == 0o12:
                    self.expected_symlinks += 1
                elif data["file_type"] == 0o10:
                    self.expected_files += 1

    @contextmanager
    def _create_zip(self, file_dict, add_attributes=True):

        zipfilename = None
        try:
            zipfilename = NamedTemporaryFile(mode="w+b").name

            zf = zipfile.ZipFile(zipfilename, "w", zipfile.ZIP_DEFLATED)
            for filename, data in file_dict.items():

                fileinfo = zipfile.ZipInfo(filename)

                if add_attributes:
                    fileinfo.external_attr = (data["file_type"] << 28) | (data["permissions"] << 16)

                zf.writestr(fileinfo, data["contents"])

            zf.close()

            yield zipfilename

        finally:
            if zipfilename:
                os.remove(zipfilename)

    @contextmanager
    def _verify_file(self, extract_dir, file, root, verify_external_attributes):
        filepath = os.path.join(extract_dir, root, file)
        key = os.path.relpath(filepath, extract_dir)
        mode = os.lstat(filepath).st_mode
        actual_permissions = oct(stat.S_IMODE(mode))
        expected_permission = oct(self.files_with_external_attr[key]["permissions"])

        self.assertIn(key, self.files_with_external_attr)
        if verify_external_attributes:
            self._verify_external_attributes(actual_permissions, expected_permission, key, mode)

    @contextmanager
    def _verify_external_attributes(self, actual_permissions, expected_permission, key, mode):
        if stat.S_ISREG(mode):
            self.assertTrue(self.files_with_external_attr[key]["file_type"] == 0o10, "Expected a regular file.")
            self.actual_files += 1
        elif stat.S_ISLNK(mode):
            self.assertTrue(self.files_with_external_attr[key]["file_type"] == 0o12, "Expected a Symlink.")
            self.actual_symlinks += 1
            return

        self.assertEqual(
            expected_permission,
            actual_permissions,
            "File {} has wrong permission {}, expected {}.".format(key, actual_permissions, expected_permission),
        )

    @contextmanager
    def _verify_file_count(self, verify_external_attributes):
        if verify_external_attributes:
            self.assertEqual(
                self.expected_files,
                self.actual_files,
                "Expected {} files but found {}.".format(self.expected_files, self.actual_files),
            )
            self.assertEqual(
                self.expected_symlinks,
                self.actual_symlinks,
                "Expected {} symlinks but found {}.".format(self.expected_symlinks, self.actual_symlinks),
            )

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
    @patch("samcli.local.lambdafn.zip.unzip")
    @patch("samcli.local.lambdafn.zip.Path")
    @patch("samcli.local.lambdafn.zip.progressbar")
    @patch("samcli.local.lambdafn.zip.requests")
    @patch("samcli.local.lambdafn.zip.open")
    @patch("samcli.local.lambdafn.zip.os")
    def test_successfully_unzip_from_uri(
        self, os_patch, open_patch, requests_patch, progressbar_patch, path_patch, unzip_patch
    ):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        file_mock = Mock()
        open_patch.return_value.__enter__.return_value = file_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = True
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = True

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        open_patch.assert_called_with("layer_zip_path", "wb")
        file_mock.write.assert_called_with(b"data1")
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)

    @patch("samcli.local.lambdafn.zip.unzip")
    @patch("samcli.local.lambdafn.zip.Path")
    @patch("samcli.local.lambdafn.zip.progressbar")
    @patch("samcli.local.lambdafn.zip.requests")
    @patch("samcli.local.lambdafn.zip.open")
    @patch("samcli.local.lambdafn.zip.os")
    def test_not_unlink_file_when_file_doesnt_exist(
        self, os_patch, open_patch, requests_patch, progressbar_patch, path_patch, unzip_patch
    ):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        file_mock = Mock()
        open_patch.return_value.__enter__.return_value = file_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = False
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = True

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        open_patch.assert_called_with("layer_zip_path", "wb")
        file_mock.write.assert_called_with(b"data1")
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_not_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)

    @patch("samcli.local.lambdafn.zip.unzip")
    @patch("samcli.local.lambdafn.zip.Path")
    @patch("samcli.local.lambdafn.zip.progressbar")
    @patch("samcli.local.lambdafn.zip.requests")
    @patch("samcli.local.lambdafn.zip.open")
    @patch("samcli.local.lambdafn.zip.os")
    def test_unzip_from_uri_reads_AWS_CA_BUNDLE_env_var(
        self, os_patch, open_patch, requests_patch, progressbar_patch, path_patch, unzip_patch
    ):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        file_mock = Mock()
        open_patch.return_value.__enter__.return_value = file_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = True
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = "/some/path/on/the/system"

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify="/some/path/on/the/system")
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        open_patch.assert_called_with("layer_zip_path", "wb")
        file_mock.write.assert_called_with(b"data1")
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)


class TestOverridePermissions(TestCase):
    @patch("samcli.local.lambdafn.zip.os")
    def test_must_override_permissions(self, os_patch):
        _override_permissions(path="./home", permission=0o700)

        os_patch.chmod.assert_called_once_with("./home", 0o700)

    @patch("samcli.local.lambdafn.zip.os")
    def test_must_not_override_permissions(self, os_patch):
        _override_permissions(path="./home", permission=None)

        os_patch.chmod.assert_not_called()
