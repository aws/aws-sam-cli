from mock import mock_open, patch, Mock
from unittest import TestCase
from parameterized import parameterized
from samcli.cli.global_config import GlobalConfig

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class TestGlobalConfig(TestCase):
    def test_config_write_error(self):
        m = mock_open()
        m.side_effect = IOError("fail")
        gc = GlobalConfig()
        with patch("samcli.cli.global_config.open", m):
            installation_id = gc.installation_id
            self.assertIsNone(installation_id)

    def test_unable_to_create_dir(self):
        m = mock_open()
        m.side_effect = OSError("Permission DENIED")
        gc = GlobalConfig()
        with patch("samcli.cli.global_config.Path.mkdir", m):
            installation_id = gc.installation_id
            self.assertIsNone(installation_id)
            telemetry_enabled = gc.telemetry_enabled
            self.assertFalse(telemetry_enabled)

    def test_setter_cannot_open_path(self):
        m = mock_open()
        m.side_effect = IOError("fail")
        gc = GlobalConfig()
        with patch("samcli.cli.global_config.open", m):
            with self.assertRaises(IOError):
                gc.telemetry_enabled = True

    @patch("samcli.cli.global_config.click")
    def test_config_dir_default(self, mock_click):
        mock_click.get_app_dir.return_value = "mock/folders"
        gc = GlobalConfig()
        self.assertEqual(Path("mock/folders"), gc.config_dir)
        mock_click.get_app_dir.assert_called_once_with("AWS SAM", force_posix=True)

    def test_explicit_installation_id(self):
        gc = GlobalConfig(installation_id="foobar")
        self.assertEqual("foobar", gc.installation_id)

    @patch("samcli.cli.global_config.uuid")
    @patch("samcli.cli.global_config.Path")
    @patch("samcli.cli.global_config.click")
    def test_setting_installation_id(self, mock_click, mock_path, mock_uuid):
        gc = GlobalConfig()
        mock_uuid.uuid4.return_value = "SevenLayerDipMock"
        path_mock = Mock()
        joinpath_mock = Mock()
        joinpath_mock.exists.return_value = False
        path_mock.joinpath.return_value = joinpath_mock
        mock_path.return_value = path_mock
        mock_click.get_app_dir.return_value = "mock/folders"
        mock_io = mock_open(Mock())
        with patch("samcli.cli.global_config.open", mock_io):
            self.assertEquals("SevenLayerDipMock", gc.installation_id)

    def test_explicit_telemetry_enabled(self):
        gc = GlobalConfig(telemetry_enabled=True)
        self.assertTrue(gc.telemetry_enabled)

    @patch("samcli.cli.global_config.Path")
    @patch("samcli.cli.global_config.click")
    @patch("samcli.cli.global_config.os")
    def test_missing_telemetry_flag(self, mock_os, mock_click, mock_path):
        gc = GlobalConfig()
        mock_click.get_app_dir.return_value = "mock/folders"
        path_mock = Mock()
        joinpath_mock = Mock()
        joinpath_mock.exists.return_value = False
        path_mock.joinpath.return_value = joinpath_mock
        mock_path.return_value = path_mock
        mock_os.environ = {}  # env var is not set
        self.assertIsNone(gc.telemetry_enabled)

    @patch("samcli.cli.global_config.Path")
    @patch("samcli.cli.global_config.click")
    @patch("samcli.cli.global_config.os")
    def test_error_reading_telemetry_flag(self, mock_os, mock_click, mock_path):
        gc = GlobalConfig()
        mock_click.get_app_dir.return_value = "mock/folders"
        path_mock = Mock()
        joinpath_mock = Mock()
        joinpath_mock.exists.return_value = True
        path_mock.joinpath.return_value = joinpath_mock
        mock_path.return_value = path_mock
        mock_os.environ = {}  # env var is not set

        m = mock_open()
        m.side_effect = IOError("fail")
        with patch("samcli.cli.global_config.open", m):
            self.assertFalse(gc.telemetry_enabled)

    @parameterized.expand(
        [
            # Only values of '1' and 1 will enable Telemetry. Everything will disable.
            (1, True),
            ("1", True),
            (0, False),
            ("0", False),
            # words true, True, False, False etc will disable telemetry
            ("true", False),
            ("True", False),
            ("False", False),
        ]
    )
    @patch("samcli.cli.global_config.os")
    @patch("samcli.cli.global_config.click")
    def test_set_telemetry_through_env_variable(self, env_value, expected_result, mock_click, mock_os):
        gc = GlobalConfig()

        mock_os.environ = {"SAM_CLI_TELEMETRY": env_value}
        mock_os.getenv.return_value = env_value

        self.assertEquals(gc.telemetry_enabled, expected_result)

        mock_os.getenv.assert_called_once_with("SAM_CLI_TELEMETRY")

        # When environment variable is set, we shouldn't be reading the real config file at all.
        mock_click.get_app_dir.assert_not_called()
