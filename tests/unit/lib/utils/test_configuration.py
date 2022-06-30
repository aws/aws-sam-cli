from unittest.case import TestCase
from unittest.mock import patch

from click import ClickException
from samcli.lib.utils import configuration


class TestConfiguration(TestCase):
    def test_config_is_read(self):
        self.assertIsInstance(configuration.config, dict)
        self.assertIn("app_template_repo_commit", configuration.config)

    @patch("samcli.lib.utils.configuration.config")
    def test_get_app_template_repo_commit_return_correct_value(self, config_mock):
        config_mock.get.return_value = "some_commit_hash"
        commit_hash = configuration.get_app_template_repo_commit()
        config_mock.get.assert_called_once_with("app_template_repo_commit", None)
        self.assertEqual(commit_hash, "some_commit_hash")

    @patch("samcli.lib.utils.configuration.config")
    def test_get_app_template_repo_commit_error(self, config_mock):
        config_mock.get.return_value = None
        with self.assertRaises(ClickException):
            configuration.get_app_template_repo_commit()
            config_mock.get.assert_called_once_with("app_template_repo_commit", None)
