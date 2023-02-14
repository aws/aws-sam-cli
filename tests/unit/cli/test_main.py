import json
from unittest.mock import patch, Mock, PropertyMock, call

from unittest import TestCase
from click.testing import CliRunner
from samcli.cli.main import cli
from samcli import __version__
from samcli.commands.exceptions import RegionError


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

    def test_cli_with_non_standard_format_region(self):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            for command in ["validate", "deploy"]:
                result = runner.invoke(cli, [command, "--region", "--non-standard-format"])
                self.assertEqual(result.exit_code, 1)
                self.assertIn(
                    "Error: Provided region: --non-standard-format doesn't match a supported format", result.output
                )
                self.assertRaises(RegionError)

    def test_cli_with_empty_region(self):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            for command in ["validate", "deploy"]:
                result = runner.invoke(cli, [command, "--region"])
                self.assertEqual(result.exit_code, 2)
                self.assertIn("Error: Option '--region' requires an argument", result.output)

    @patch("samcli.commands.validate.validate.do_cli")
    def test_cli_with_valid_region(self, mock_do_cli):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, ["validate", "--region", "us-west-2"])
            self.assertEqual(result.exit_code, 0)
        self.assertTrue(mock_do_cli.called)
        self.assertEqual(mock_do_cli.call_count, 1)

    def test_cli_with_debug(self):
        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, ["local", "generate-event", "s3", "put", "--debug"])
            self.assertEqual(result.exit_code, 0)

    @patch("samcli.lib.telemetry.metric.send_installed_metric")
    def test_cli_enable_telemetry_with_prompt(self, send_installed_metric_mock):
        with patch("samcli.cli.global_config.GlobalConfig.telemetry_enabled", new_callable=PropertyMock) as mock_flag:
            mock_flag.return_value = None
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"])
            mock_flag.assert_called_with(True)

            # If telemetry is enabled, this should be called
            send_installed_metric_mock.assert_called_once()

    @patch("samcli.lib.telemetry.metric.send_installed_metric")
    def test_prompt_skipped_when_value_set(self, send_installed_metric_mock):
        with patch("samcli.cli.global_config.GlobalConfig.telemetry_enabled", new_callable=PropertyMock) as mock_flag:
            mock_flag.return_value = True
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"])
            mock_flag.assert_called_once_with()

            # If prompt is skipped, this should be NOT called
            send_installed_metric_mock.assert_not_called()


class TestPrintSamCliInfo(TestCase):
    @patch("samcli.cli.main.gather_system_info")
    @patch("samcli.cli.main.gather_additional_dependencies_info")
    def test_print_info(self, deps_info_mock, system_info_mock):
        system_info_mock.return_value = {"Python": "1.2.3"}
        deps_info_mock.return_value = {"dep1": "1.2.3", "dep2": "1.2.3"}
        expected = {
            "version": __version__,
            "system": {
                "Python": "1.2.3",
            },
            "additional_dependencies": {
                "dep1": "1.2.3",
                "dep2": "1.2.3",
            },
        }

        mock_cfg = Mock()
        with patch("samcli.cli.main.GlobalConfig", mock_cfg):
            runner = CliRunner()
            result = runner.invoke(cli, ["--info"])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(json.loads(result.output), expected)
