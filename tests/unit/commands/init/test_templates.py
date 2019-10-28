import json
import subprocess
import click

from unittest.mock import mock_open, patch, PropertyMock, MagicMock
from re import search
from unittest import TestCase

from samcli.commands.init.init_templates import InitTemplates


class TestTemplates(TestCase):
    @patch("subprocess.check_output")
    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    def test_location_from_app_template(self, subprocess_mock, git_exec_mock):
        it = InitTemplates(True)

        manifest = {
            "ruby2.5": [
                {
                    "directory": "mock-ruby-template",
                    "displayName": "Hello World Example",
                    "dependencyManager": "bundler",
                    "appTemplate": "hello-world",
                }
            ]
        }
        manifest_json = json.dumps(manifest)

        m = mock_open(read_data=manifest_json)
        with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
            mock_cfg.return_value = "/tmp/test-sam"
            with patch("samcli.commands.init.init_templates.open", m):
                location = it.location_from_app_template("ruby2.5", "bundler", "hello-world")
                self.assertEqual(location, "/tmp/test-sam/aws-sam-cli-app-templates/mock-ruby-template")

    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    @patch("click.prompt")
    def test_fallback_options(self, git_exec_mock, prompt_mock):
        prompt_mock.return_value = "1"
        with patch("subprocess.check_output", new_callable=MagicMock) as mock_sub:
            with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
                mock_sub.side_effect = OSError("Fail")
                mock_cfg.return_value = "/tmp/test-sam"
                it = InitTemplates(True)
                location = it.prompt_for_location("ruby2.5", "bundler")
                self.assertTrue(search("cookiecutter-aws-sam-hello-ruby", location))

    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    @patch("click.prompt")
    def test_fallback_process_error(self, git_exec_mock, prompt_mock):
        prompt_mock.return_value = "1"
        with patch("subprocess.check_output", new_callable=MagicMock) as mock_sub:
            with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
                mock_sub.side_effect = subprocess.CalledProcessError("fail", "fail", "not found".encode("utf-8"))
                mock_cfg.return_value = "/tmp/test-sam"
                it = InitTemplates(True)
                location = it.prompt_for_location("ruby2.5", "bundler")
                self.assertTrue(search("cookiecutter-aws-sam-hello-ruby", location))
