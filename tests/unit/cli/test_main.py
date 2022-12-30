import json
from unittest.mock import patch, Mock, PropertyMock, call

from unittest import TestCase
from click.testing import CliRunner
from samcli.cli.main import (
    cli,
    _gather_system_info,
    _gather_additional_dependencies_info,
    _gather_cdk_info,
    _gather_docker_info,
    _gather_terraform_info,
)
from samcli import __version__


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
    @patch("samcli.cli.main._gather_system_info")
    @patch("samcli.cli.main._gather_additional_dependencies_info")
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

    @patch("platform.platform")
    @patch("platform.python_version")
    def test_gather_system_info(self, python_version_mock, platform_mock):
        python_version_mock.return_value = "1.2.3"
        platform_mock.return_value = "some_system"
        result = _gather_system_info()
        self.assertEqual(result, {"python": "1.2.3", "os": "some_system"})

    @patch("samcli.cli.main._gather_docker_info")
    @patch("samcli.cli.main._gather_cdk_info")
    @patch("samcli.cli.main._gather_terraform_info")
    def test_gather_additional_dependencies_info(self, terraform_info_mock, cdk_info_mock, docker_info_mock):
        docker_info_mock.return_value = "1.1.1"
        cdk_info_mock.return_value = "2.2.2"
        terraform_info_mock.return_value = "3.3.3"
        result = _gather_additional_dependencies_info()
        self.assertEqual(result, {"docker_engine": "1.1.1", "aws_cdk": "2.2.2", "terraform": "3.3.3"})

    @patch("docker.from_env")
    @patch("samcli.local.docker.utils.is_docker_reachable")
    def test_gather_docker_info_when_client_is_reachable(self, is_docker_reachable_mock, from_env_mock):
        docker_client_mock = Mock()
        is_docker_reachable_mock.return_value = True
        docker_client_mock.version.return_value = {"Version": "1.1.1"}
        from_env_mock.return_value = docker_client_mock
        result = _gather_docker_info()
        self.assertEqual(result, "1.1.1")

    @patch("docker.from_env")
    @patch("samcli.local.docker.utils.is_docker_reachable")
    def test_gather_docker_info_when_client_is_not_reachable(self, is_docker_reachable_mock, from_env_mock):
        is_docker_reachable_mock.return_value = False
        result = _gather_docker_info()
        self.assertEqual(result, "Not available")

    @patch("subprocess.run")
    def test_gather_cdk_info_when_cdk_is_available(self, run_mock):
        process_mock = Mock()
        process_mock.stdout = "1.1.1\n"
        run_mock.return_value = process_mock
        result = _gather_cdk_info()
        self.assertEqual(result, "1.1.1")

    @patch("subprocess.run")
    def test_gather_cdk_info_when_cdk_is_not_available(self, run_mock):
        run_mock.side_effect = FileNotFoundError
        result = _gather_cdk_info()
        self.assertEqual(result, "Not available")

    @patch("subprocess.run")
    def test_gather_terraform_info_when_terraform_is_available(self, run_mock):
        process_mock = Mock()
        process_mock.stdout = """
        {
            "terraform_version": "1.1.1"
        }"""
        run_mock.return_value = process_mock
        result = _gather_terraform_info()
        self.assertEqual(result, "1.1.1")

    @patch("subprocess.run")
    def test_gather_terraform_info_when_terraform_is_not_available(self, process_mock):
        process_mock.side_effect = FileNotFoundError
        result = _gather_terraform_info()
        self.assertEqual(result, "Not available")
