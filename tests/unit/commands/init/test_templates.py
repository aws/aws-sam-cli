import json
import subprocess
from pathlib import Path
from re import search
from unittest import TestCase
from unittest.mock import mock_open, patch, PropertyMock, MagicMock

from samcli.commands.init.init_templates import InitTemplates
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestTemplates(TestCase):
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.GitRepo._git_executable")
    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("shutil.copytree")
    def test_location_from_app_template_zip(self, subprocess_mock, git_exec_mock, cd_mock, copy_mock):
        it = InitTemplates()

        manifest = {
            "ruby2.5": [
                {
                    "directory": "mock-ruby-template",
                    "displayName": "Hello World Example",
                    "dependencyManager": "bundler",
                    "appTemplate": "hello-world",
                    "packageType": ZIP,
                }
            ]
        }
        manifest_json = json.dumps(manifest)

        m = mock_open(read_data=manifest_json)
        with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
            mock_cfg.return_value = Path("/tmp/test-sam")
            with patch("samcli.commands.init.init_templates.open", m):
                location = it.location_from_app_template(ZIP, "ruby2.5", None, "bundler", "hello-world")
                self.assertTrue(search("mock-ruby-template", location))

    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.GitRepo._git_executable")
    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("shutil.copytree")
    def test_location_from_app_template_image(self, subprocess_mock, git_exec_mock, cd_mock, copy_mock):
        it = InitTemplates()

        manifest = {
            "ruby2.5-image": [
                {
                    "directory": "mock-ruby-image-template",
                    "displayName": "Hello World Lambda Image Example",
                    "dependencyManager": "bundler",
                    "appTemplate": "hello-world-lambda-image",
                    "packageType": IMAGE,
                }
            ]
        }
        manifest_json = json.dumps(manifest)

        m = mock_open(read_data=manifest_json)
        with patch("samcli.cli.global_config.GlobalConfig.config_dir", new_callable=PropertyMock) as mock_cfg:
            mock_cfg.return_value = Path("/tmp/test-sam")
            with patch("samcli.commands.init.init_templates.open", m):
                location = it.location_from_app_template(
                    IMAGE, None, "ruby2.5-image", "bundler", "hello-world-lambda-image"
                )
                self.assertTrue(search("mock-ruby-image-template", location))
