from unittest.case import TestCase
from unittest.mock import patch, Mock

from samcli.local.lambdafn.remote_files import unzip_from_uri


class TestUnzipFromUri(TestCase):
    @patch("samcli.local.lambdafn.remote_files.unzip")
    @patch("samcli.local.lambdafn.remote_files.Path")
    @patch("samcli.local.lambdafn.remote_files.progressbar")
    @patch("samcli.local.lambdafn.remote_files.requests")
    @patch("samcli.local.lambdafn.remote_files.os")
    def test_successfully_unzip_from_uri(self, os_patch, requests_patch, progressbar_patch, path_patch, unzip_patch):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = True
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = True

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)

    @patch("samcli.local.lambdafn.remote_files.unzip")
    @patch("samcli.local.lambdafn.remote_files.Path")
    @patch("samcli.local.lambdafn.remote_files.progressbar")
    @patch("samcli.local.lambdafn.remote_files.requests")
    @patch("samcli.local.lambdafn.remote_files.os")
    def test_not_unlink_file_when_file_doesnt_exist(
        self, os_patch, requests_patch, progressbar_patch, path_patch, unzip_patch
    ):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = False
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = True

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify=True)
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_not_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)

    @patch("samcli.local.lambdafn.remote_files.unzip")
    @patch("samcli.local.lambdafn.remote_files.Path")
    @patch("samcli.local.lambdafn.remote_files.progressbar")
    @patch("samcli.local.lambdafn.remote_files.requests")
    @patch("samcli.local.lambdafn.remote_files.os")
    def test_unzip_from_uri_reads_AWS_CA_BUNDLE_env_var(
        self, os_patch, requests_patch, progressbar_patch, path_patch, unzip_patch
    ):
        get_request_mock = Mock()
        get_request_mock.headers = {"Content-length": "200"}
        get_request_mock.iter_content.return_value = [b"data1"]
        requests_patch.get.return_value = get_request_mock

        progressbar_mock = Mock()
        progressbar_patch.return_value.__enter__.return_value = progressbar_mock

        path_mock = Mock()
        path_mock.exists.return_value = True
        path_patch.return_value = path_mock

        os_patch.environ.get.return_value = "/some/path/on/the/system"

        unzip_from_uri("uri", "layer_zip_path", "output_zip_dir", "layer_arn")

        requests_patch.get.assert_called_with("uri", stream=True, verify="/some/path/on/the/system")
        get_request_mock.iter_content.assert_called_with(chunk_size=None)
        progressbar_mock.update.assert_called_with(5)
        path_patch.assert_called_with("layer_zip_path")
        path_mock.unlink.assert_called()
        unzip_patch.assert_called_with("layer_zip_path", "output_zip_dir", permission=0o700)
        os_patch.environ.get.assert_called_with("AWS_CA_BUNDLE", True)
