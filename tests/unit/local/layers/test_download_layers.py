from unittest import TestCase
from mock import patch, Mock, call

from botocore.exceptions import NoCredentialsError, ClientError

from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound


class TestDownloadLayers(TestCase):

    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    def test_initialization(self, create_cache_patch):
        create_cache_patch.return_value = None

        download_layers = LayerDownloader("/some/path", ".")

        self.assertEquals(download_layers.layer_cache, "/some/path")
        create_cache_patch.assert_called_with("/some/path")

    @patch("samcli.local.layers.layer_downloader.LayerDownloader.download")
    def test_download_all_without_force(self, download_patch):
        download_patch.side_effect = ['/home/layer1', '/home/layer2']

        download_layers = LayerDownloader("/home", ".")

        acutal_results = download_layers.download_all(['layer1', 'layer2'])

        self.assertEquals(acutal_results, ['/home/layer1', '/home/layer2'])

        download_patch.assert_has_calls([call('layer1', False), call("layer2", False)])

    @patch("samcli.local.layers.layer_downloader.LayerDownloader.download")
    def test_download_all_with_force(self, download_patch):
        download_patch.side_effect = ['/home/layer1', '/home/layer2']

        download_layers = LayerDownloader("/home", ".")

        acutal_results = download_layers.download_all(['layer1', 'layer2'], force=True)

        self.assertEquals(acutal_results, ['/home/layer1', '/home/layer2'])

        download_patch.assert_has_calls([call('layer1', True), call("layer2", True)])

    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._is_layer_cached")
    def test_download_layer_that_is_cached(self, is_layer_cached_patch, create_cache_patch):
        is_layer_cached_patch.return_value = True

        download_layers = LayerDownloader("/home", ".")

        layer_mock = Mock()
        layer_mock.is_defined_within_template = False
        layer_mock.name = "layer1"

        actual = download_layers.download(layer_mock)

        self.assertEquals(actual.codeuri, '/home/layer1')

        create_cache_patch.assert_called_once_with("/home")

    @patch("samcli.local.layers.layer_downloader.resolve_code_path")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    def test_download_layer_that_was_template_defined(self, create_cache_patch, resolve_code_path_patch):

        download_layers = LayerDownloader("/home", ".")

        layer_mock = Mock()
        layer_mock.is_template_defined = True
        layer_mock.name = "layer1"
        layer_mock.codeuri = "/some/custom/path"

        resolve_code_path_patch.return_value = './some/custom/path'

        actual = download_layers.download(layer_mock)

        self.assertEquals(actual.codeuri, './some/custom/path')

        create_cache_patch.assert_not_called()
        resolve_code_path_patch.assert_called_once_with(".", "/some/custom/path")

    @patch("samcli.local.layers.layer_downloader.unzip_from_uri")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._fetch_layer_uri")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._create_cache")
    @patch("samcli.local.layers.layer_downloader.LayerDownloader._is_layer_cached")
    def test_download_layer(self, is_layer_cached_patch, create_cache_patch,
                            fetch_layer_uri_patch, unzip_from_uri_patch):
        is_layer_cached_patch.return_value = False

        download_layers = LayerDownloader("/home", ".")

        layer_mock = Mock()
        layer_mock.is_defined_within_template = False
        layer_mock.name = "layer1"
        layer_mock.arn = "arn:layer:layer1:1"
        layer_mock.layer_arn = "arn:layer:layer1"

        fetch_layer_uri_patch.return_value = "layer/uri"

        actual = download_layers.download(layer_mock)

        self.assertEquals(actual.codeuri, "/home/layer1")

        create_cache_patch.assert_called_once_with("/home")
        fetch_layer_uri_patch.assert_called_once_with(layer_mock)
        unzip_from_uri_patch.assert_called_once_with("layer/uri",
                                                     '/home/layer1.zip',
                                                     unzip_output_dir='/home/layer1',
                                                     progressbar_label="Downloading arn:layer:layer1")

    def test_layer_is_cached(self):
        download_layers = LayerDownloader("/", ".")

        layer_path = Mock()
        layer_path.exists.return_value = True

        self.assertTrue(download_layers._is_layer_cached(layer_path))

    def test_layer_is_not_cached(self):
        download_layers = LayerDownloader("/", ".")

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
        download_layers = LayerDownloader("/", ".", lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1
        actual_uri = download_layers._fetch_layer_uri(layer=layer)

        self.assertEquals(actual_uri, "some/uri")

    def test_fetch_layer_uri_fails_with_no_creds(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = NoCredentialsError()
        download_layers = LayerDownloader("/", ".", lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(CredentialsRequired):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_fails_with_AccessDeniedException(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDeniedException'}}, operation_name="lambda")
        download_layers = LayerDownloader("/", ".", lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(CredentialsRequired):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_fails_with_ResourceNotFoundException(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={'Error': {'Code': 'ResourceNotFoundException'}}, operation_name="lambda")
        download_layers = LayerDownloader("/", ".", lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(ResourceNotFound):
            download_layers._fetch_layer_uri(layer=layer)

    def test_fetch_layer_uri_re_raises_client_error(self):
        lambda_client_mock = Mock()
        lambda_client_mock.get_layer_version.side_effect = ClientError(
            error_response={'Error': {'Code': 'Unknown'}}, operation_name="lambda")
        download_layers = LayerDownloader("/", ".", lambda_client_mock)

        layer = Mock()
        layer.layer_arn = "arn"
        layer.version = 1

        with self.assertRaises(ClientError):
            download_layers._fetch_layer_uri(layer=layer)
