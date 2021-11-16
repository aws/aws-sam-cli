from unittest.mock import patch, Mock, PropertyMock, call

from unittest import TestCase
from click.testing import CliRunner
from samcli.cli.main import cli


class TestCliBase(TestCase):
    def test_cli_base(self):
        """
        Just invoke the CLI without any commands and assert that help text was printed
        :return:
        """
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, [])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue("--help" in result.output, "Help text must be printed")
            self.assertTrue("--debug" in result.output, "--debug option must be present in help text")

    def test_cli_some_command(self):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, ["local", "generate-event", "s3"])
            self.assertEqual(result.exit_code, 0)

    def test_cli_with_debug(self):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, ["local", "generate-event", "s3", "put", "--debug"])
            self.assertEqual(result.exit_code, 0)

    @patch("samcli.cli.main.send_installed_metric")
    def test_cli_enable_telemetry_with_prompt(self, send_installed_metric_mock):
        with patch("samcli.cli.global_config.GlobalConfig.telemetry_enabled", new_callable=PropertyMock) as mock_flag:
            mock_flag.return_value = None
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"])
            mock_flag.assert_called_with(True)

            # If telemetry is enabled, this should be called
            send_installed_metric_mock.assert_called_once()

    @patch("samcli.cli.main.send_installed_metric")
    def test_prompt_skipped_when_value_set(self, send_installed_metric_mock):
        with patch("samcli.cli.global_config.GlobalConfig.telemetry_enabled", new_callable=PropertyMock) as mock_flag:
            mock_flag.return_value = True
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"])
            mock_flag.assert_called_once_with()

            # If prompt is skipped, this should be NOT called
            send_installed_metric_mock.assert_not_called()
