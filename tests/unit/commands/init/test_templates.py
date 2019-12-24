import json
import subprocess
import click

from unittest.mock import mock_open, patch, PropertyMock, MagicMock
from re import search
from unittest import TestCase

from pathlib import Path

from samcli.commands.init.init_templates import InitTemplates


class TestTemplates(TestCase):
    @patch("subprocess.check_output")
    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("shutil.copytree")
    def test_location_from_app_template(self, subprocess_mock, git_exec_mock, sd_mock, copy_mock):
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
                self.assertTrue(search("mock-ruby-template", location))

    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    @patch("click.prompt")
    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    def test_fallback_options(self, git_exec_mock, prompt_mock, sd_mock):
        prompt_mock.return_value = "1"
        with patch("subprocess.check_output", new_callable=MagicMock) as mock_sub:
            with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
                mock_sub.side_effect = OSError("Fail")
                mock_cfg.return_value = "/tmp/test-sam"
                it = InitTemplates(True)
                location, app_template = it.prompt_for_location("ruby2.5", "bundler")
                self.assertTrue(search("cookiecutter-aws-sam-hello-ruby", location))
                self.assertEqual("hello-world", app_template)

    @patch("samcli.commands.init.init_templates.InitTemplates._git_executable")
    @patch("click.prompt")
    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    def test_fallback_process_error(self, git_exec_mock, prompt_mock, sd_mock):
        prompt_mock.return_value = "1"
        with patch("subprocess.check_output", new_callable=MagicMock) as mock_sub:
            with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
                mock_sub.side_effect = subprocess.CalledProcessError("fail", "fail", "not found".encode("utf-8"))
                mock_cfg.return_value = "/tmp/test-sam"
                it = InitTemplates(True)
                location, app_template = it.prompt_for_location("ruby2.5", "bundler")
                self.assertTrue(search("cookiecutter-aws-sam-hello-ruby", location))
                self.assertEqual("hello-world", app_template)

    def test_git_executable_windows(self):
        with patch("platform.system", new_callable=MagicMock) as mock_platform:
            mock_platform.return_value = "Windows"
            with patch("subprocess.Popen", new_callable=MagicMock) as mock_popen:
                it = InitTemplates(True)
                executable = it._git_executable()
                self.assertEqual(executable, "git")

    def test_git_executable_fails(self):
        with patch("subprocess.Popen", new_callable=MagicMock) as mock_popen:
            mock_popen.side_effect = OSError("fail")
            it = InitTemplates(True)
            with self.assertRaises(OSError):
                executable = it._git_executable()

    def test_shared_dir_check(self):
        it = InitTemplates(True, False)
        shared_dir_mock = MagicMock()
        self.assertTrue(it._shared_dir_check(shared_dir_mock))

    def test_shared_dir_failure(self):
        it = InitTemplates(True, False)
        shared_dir_mock = MagicMock()
        shared_dir_mock.mkdir.side_effect = OSError("fail")
        self.assertFalse(it._shared_dir_check(shared_dir_mock))
