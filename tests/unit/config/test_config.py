from unittest import TestCase
from mock import patch

from samcli.config import config


class TestInit(TestCase):

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

    @patch('samcli.config.config.Config.merge_config')
    @patch('samcli.config.config.Config.validate_config')
    @patch('samcli.config.config.Config._read_config')
    @patch('samcli.config.config.Config._find_config')
    def test_load_config(self, find_config_patch, read_config_patch, validate_patch, merge_config_patch):
        # GIVEN an user configuration exist but project
        # WHEN config is loaded and I/O operations are patched
        # THEN user configuration should be loaded
        find_config_patch.return_value = ('/home/user/.samrc', '')
        merge_config_patch.return_value = self.valid_samrc_user_level

        self.config = config.Config().load()

        find_config_patch.assert_called_once()
        self.assertEqual(read_config_patch.call_count, 2)
        self.assertEqual(validate_patch.call_count, 2)

        merge_config_patch.assert_called_once()

        self.assertEqual(self.config, self.valid_samrc_user_level)

    @patch('samcli.config.config.json.load')
    @patch('samcli.config.config.Path')
    @patch('samcli.config.config.yaml.safe_load')
    @patch('samcli.config.config.Config._has_file')
    @patch('samcli.config.config.Config.validate_config')
    def test_merge_configs(self, validate_config_patch, has_file_patch, yaml_safe_load_patch, path_patch, json_patch):
        # GIVEN an user and project configuration exist
        # WHEN config is loaded and I/O operations are patched
        # THEN a new configuration out of both user and project should be loaded
        has_file_patch.return_value = True
        yaml_safe_load_patch.side_effect = [self.valid_samrc_user_level, self.valid_samrc_project_level]

        self.config = config.Config().load()

        json_patch.assert_called_once()
        self.assertEqual(yaml_safe_load_patch.call_count, 2)
        self.assertEqual(has_file_patch.call_count, 2)

        self.assertEqual(self.config['default']['debug_port'], 4040)
        self.assertEqual(self.config['future_proof_section']['something'], 'else')
