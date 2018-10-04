from unittest import TestCase
from mock import patch

from samcli.config import config


class TestInit(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.samrc_patch = patch.object(config, 'samrc')
        cls.path_patch = patch.object(config, 'Path')
        cls.json_patch = patch.object(config.json, 'load')

    def setUp(self):
        self.config = None
        self.valid_samrc_user_level = {
            "default": {
                "aws_region": "eu-west-1",
                "aws_profile": "demo",
                "default_port": 8080,
                "debug_port": 8080,
                "template": "template.yaml"
            }
        }
        self.valid_samrc_project_level = {
            "default": {
                "debug_port": 4040,
            },
            "future_proof_section": {
                "something": "else"
            }
        }

    @patch.object(config.Config, '_Config__find_config', return_value=('/home/user/.samrc', None))
    @patch.object(config.Config, '_Config__read_config')
    def test_load_user_config_only(self, read_config_patch, find_config_patch):
        self.config = config.Config()

        self.config.load()

        find_config_patch.assert_called_once()
        read_config_patch.assert_called_with('/home/user/.samrc')

    @patch.object(config.Config, '_Config__find_config', return_value=(None, '.samrc'))
    @patch.object(config.Config, '_Config__read_config')
    def test_load_project_config_only(self, read_config_patch, find_config_patch):
        self.config = config.Config()

        self.config.load()

        find_config_patch.assert_called_once()
        read_config_patch.assert_called_with('.samrc')

    @patch.object(config.Config, '_Config__find_config', return_value=('/home/user/.samrc', '.samrc'))
    @patch.object(config.Config, '_Config__read_config')
    def test_load_both_configs(self, read_config_patch, find_config_patch):
        self.config = config.Config()

        self.config.load()

        find_config_patch.assert_called_once()
        self.assertEqual(read_config_patch.call_count, 2)

    @patch.object(config.Config, '_Config__has_user_config', return_value=True)
    @patch.object(config.Config, '_Config__has_project_config', return_value=False)
    @patch.object(config.Config, '_Config__read_config')
    def test_find_user_config(self, read_config_patch, has_project_patch, has_user_patch):
        self.config = config.Config()

        self.config.load()

        self.assertEqual(has_project_patch.call_count, 2)
        self.assertEqual(has_user_patch.call_count, 2)

    @patch.object(config.Config, '_Config__has_user_config', return_value=False)
    @patch.object(config.Config, '_Config__has_project_config', return_value=True)
    @patch.object(config.Config, '_Config__read_config')
    def test_find_project_config(self, read_config_patch, has_project_patch, has_user_patch):
        self.config = config.Config()

        self.config.load()

        has_user_patch.assert_called_once()
        has_project_patch.assert_called_once()

    @patch.object(config.Config, '_Config__has_user_config', return_value=True)
    @patch.object(config.Config, '_Config__has_project_config', return_value=True)
    @patch.object(config.Config, '_Config__read_config')
    def test_find_both_configs(self, read_config_patch, has_project_patch, has_user_patch):
        self.config = config.Config()

        self.config.load()

        has_user_patch.assert_called_once()
        has_project_patch.assert_called_once()

    @patch.object(config.yaml, 'safe_load')
    @patch.object(config.Path, 'read_text')
    @patch.object(config.Config, '_Config__find_config', return_value=(None, '.samrc'))
    @patch.object(config.Config, '_Config__has_project_config', return_value=True)
    def test_read_config(self, has_project_patch, find_config_patch, path_read_text_patch, yaml_patch):
        self.config = config.Config()
        self.config.load()

        path_read_text_patch.assert_called_once()
        yaml_patch.assert_called_once()

    @patch.object(config.Config, '_Config__find_config', return_value=('/home/user/.samrc', '.samrc'))
    @patch.object(config.Config, '_Config__has_user_config', return_value=True)
    @patch.object(config.Config, '_Config__has_project_config', return_value=True)
    def test_merge_config(self, has_user_patch, has_project_patch, find_config_patch):
        with patch.object(config.Config, '_Config__read_config',
                          side_effect=[self.valid_samrc_user_level, self.valid_samrc_project_level]):
            self.config = config.Config()
            merged_config = self.config.load()
            self.assertIn('future_proof_section', merged_config)
            self.assertEqual(merged_config['default']['debug_port'], 4040)
