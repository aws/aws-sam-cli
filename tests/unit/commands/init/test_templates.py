from subprocess import STDOUT

import json
from parameterized import parameterized
from pathlib import Path
from re import search
from unittest import TestCase
from unittest.mock import mock_open, patch, PropertyMock, Mock

from samcli.commands.init.init_templates import InitTemplates
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestTemplates(TestCase):
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.GitRepo.git_executable")
    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("shutil.copytree")
    def test_location_from_app_template_zip(self, subprocess_mock, git_exec_mock, cd_mock, copy_mock):
        it = InitTemplates()
        it._check_upsert_templates = Mock()

        manifest = {
            "ruby3.2": [
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
                location = it.location_from_app_template(ZIP, "ruby3.2", None, "bundler", "hello-world")
                self.assertTrue(search("mock-ruby-template", location))

    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.GitRepo.git_executable")
    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("shutil.copytree")
    def test_location_from_app_template_image(self, subprocess_mock, git_exec_mock, cd_mock, copy_mock):
        it = InitTemplates()
        it._check_upsert_templates = Mock()

        manifest = {
            "ruby3.2-image": [
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
                    IMAGE, None, "ruby3.2-image", "bundler", "hello-world-lambda-image"
                )
                self.assertTrue(search("mock-ruby-image-template", location))

    @parameterized.expand([("hash_a", "hash_a", False), ("hash_a", "hash_b", True)])
    @patch("samcli.lib.utils.git_repo.GitRepo.git_executable")
    @patch("samcli.commands.init.init_templates.check_output")
    def test_check_upsert_templates(self, first_hash, second_hash, expected_value, check_output_mock, git_exec_mock):
        it = InitTemplates()
        git_exec_mock.return_value = "git"
        check_output_mock.return_value = second_hash.encode("utf-8")
        with patch("samcli.commands.init.init_templates.APP_TEMPLATES_REPO_COMMIT", first_hash):
            return_value = it._check_upsert_templates(Path("shared_dir"), Path("cloned_folder_dir"))
        check_output_mock.assert_called_once_with(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=Path("shared_dir/cloned_folder_dir"), stderr=STDOUT
        )
        self.assertEqual(return_value, expected_value)
