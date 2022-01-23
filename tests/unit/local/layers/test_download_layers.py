import os
from unittest import TestCase
from unittest.mock import Mock, call, patch

from botocore.exceptions import NoCredentialsError, ClientError
from pathlib import Path

from parameterized import parameterized

from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound


class TestDownloadLayers(TestCase):
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    def test_initialization(self, create_cache_patch):
        create_cache_patch.return_value = None

        download_layers = LayerDownloader("/some/path", ".", Mock())

        self.assertEqual(download_layers.layer_cache, "/some/path")
        create_cache_patch.assert_called_with("/some/path")

    @patch("samcli.local.layers.layer_downloader.LayerDownloader.download")
    def test_download_all_without_force(self, download_patch):
        download_patch.side_effect = ["/home/layer1", "/home/layer2"]

        download_layers = LayerDownloader("/home", ".", Mock())

        acutal_results = download_layers.download_all(["layer1", "layer2"])

        self.assertEqual(acutal_results, ["/home/layer1", "/home/layer2"])

        download_patch.assert_has_calls([call("layer1", False), call("layer2", False)])

    @patch("samcli.local.layers.layer_downloader.LayerDownloader.download")
    def test_download_all_with_force(self, download_patch):
        download_patch.side_effect = ["/home/layer1", "/home/layer2"]

        download_layers = LayerDownloader("/home", ".", Mock())

        acutal_results = download_layers.download_all(["layer1", "layer2"], force=True)

        self.assertEqual(acutal_results, ["/home/layer1", "/home/layer2"])

        download_patch.assert_has_calls([call("layer1", True), call("layer2", True)])

    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._is_layer_cached")
    def test_download_layer_that_is_cached(self, is_layer_cached_patch, create_cache_patch):
        is_layer_cached_patch.return_value = True

        download_layers = LayerDownloader("/home", ".", Mock())

        layer_mock = Mock()
        layer_mock.is_defined_within_template = False
        layer_mock.name = "layer1"

        actual = download_layers.download(layer_mock)

        self.assertEqual(actual.codeuri, str(Path("/home/layer1").resolve()))

        create_cache_patch.assert_called_once_with("/home")

    @patch("samcli.local.layers.layer_downloader.resolve_code_path")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    def test_download_layer_that_was_template_defined(self, create_cache_patch, resolve_code_path_patch):
        """
        when the template is not lcoated in working directory, layer's codeuri needs to be adjusted
        """
        stack_path_mock = Mock()
        stack_template_location = "./some/path/template.yaml"

        download_layers = LayerDownloader(
            "/home", ".", [Mock(stack_path=stack_path_mock, location=stack_template_location)]
        )

        layer_mock = Mock()
        layer_mock.is_template_defined = True
        layer_mock.name = "layer1"
        layer_mock.codeuri = "codeuri"
        layer_mock.stack_path = stack_path_mock

        resolve_code_path_return_mock = Mock()
        resolve_code_path_patch.return_value = resolve_code_path_return_mock

        actual = download_layers.download(layer_mock)

        self.assertEqual(actual.codeuri, resolve_code_path_return_mock)

        create_cache_patch.assert_not_called()
        resolve_code_path_patch.assert_called_once_with(".", "codeuri")

    @patch("samcli.local.layers.layer_downloader.unzip_from_uri")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._fetch_layer_uri")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._is_layer_cached")
    def test_download_layer(
        self, is_layer_cached_patch, create_cache_patch, fetch_layer_uri_patch, unzip_from_uri_patch
    ):
        is_layer_cached_patch.return_value = False

        download_layers = LayerDownloader("/home", ".", Mock())

        layer_mock = Mock()
        layer_mock.is_defined_within_template = False
        layer_mock.name = "layer1"
        layer_mock.arn = "arn:layer:layer1:1"
        layer_mock.layer_arn = "arn:layer:layer1"

        fetch_layer_uri_patch.return_value = "layer/uri"

        actual = download_layers.download(layer_mock)

        self.assertEqual(actual.codeuri, str(Path("/home/layer1").resolve()))

        create_cache_patch.assert_called_once_with("/home")
        fetch_layer_uri_patch.assert_called_once_with(layer_mock)
        unzip_from_uri_patch.assert_called_once_with(
            "layer/uri",
            str(Path("/home/layer1.zip").resolve()),
            unzip_output_dir=str(Path("/home/layer1").resolve()),
            progressbar_label="Downloading arn:layer:layer1",
        )

    def test_layer_is_cached(self):
        download_layers = LayerDownloader("/", ".", Mock())

        layer_path = Mock()
        layer_path.exists.return_value = True

        self.assertTrue(download_layers._is_layer_cached(layer_path))

    def test_layer_is_not_cached(self):
        download_layers = LayerDownloader("/", ".", Mock())

        layer_path = Mock()
        layer_path.exists.return_value = False

        self.assertFalse(download_layers._is_layer_cached(layer_path))

    @patch("samcli.local.layers.layer_downloader.Path")
    def test_create_cache(self, path_patch):
        cache_path_mock = Mock()
        path_patch.return_value = cache_path_mock

        self.assertIsNone(LayerDownloader._create_cache("./home"))

        path_patch.assert_called_once_with("./home")
        cache_path_mock.mkdir.assert_called_once_with(parents=True, exist_ok=True, mode=0o700)


class TestLayerDownloader_fetch_layer_uri(TestCase):
    def test_fetch_layer_uri_is_successful(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.return_value = {"Content": {"Location": "some/uri"}}
        download_layers = LayerDownloader("/", ".", Mock(), lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1
        actual_uri = download_layers._fetch_layer_uri(layer=layer)

        self.assertEqual(actual_uri, "some/uri")

    def test_fetch_layer_uri_fails_with_no_creds(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = NoCredentialsError()
        download_layers = LayerDownloader("/", ".", Mock(), lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(CredentialsRequired):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_fails_with_AccessDeniedException(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException"}}, operation_name="lambda"
        )
        download_layers = LayerDownloader("/", ".", Mock(), lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(CredentialsRequired):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_fails_with_ResourceNotFoundException(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="lambda"
        )
        download_layers = LayerDownloader("/", ".", Mock(), lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(ResourceNotFound):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_re_raises_client_error(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={"Error": {"Code": "Unknown"}}, operation_name="lambda"
        )
        download_layers = LayerDownloader("/", ".", Mock(), lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(ClientError):
            download_layers._fetch_layer_uri(layer=layer)
