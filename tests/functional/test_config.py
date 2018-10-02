from unittest import TestCase

from samcli.config.config import Config

# This is an attempt to do a controlled import. pathlib is in the
# Python standard library starting at 3.4. This will import pathlib2,
# which is a backport of the Python Standard Library pathlib
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

import yaml


class TestConfig(TestCase):

    def setUp(self):
        self.config = Config()
        self.samrc_user_level = """
        aws_region: 'eu-west-1'
        aws_profile: 'demo'
        default_port: 8080
        debug_port: 8080
        template: 'template.yaml'
        """
        self.samrc_project_level = """
        default_port: 4040
        """
        self.project_config = Path.cwd().joinpath('.samrc')
        self.user_config = Path.home().joinpath('.samrc')

        with self.project_config.open(mode='w') as f:
            f.write(self.samrc_project_level)

        with self.user_config.open(mode='w') as f:
            f.write(self.samrc_user_level)

    def tearDown(self):
        self.project_config.unlink()
        self.user_config.unlink()

    def test_merge_config(self):
        # GIVEN two dictionaries were given
        # WHERE 'key' is present in both but has different values
        user_config = {"key": "val1"}
        project_config = {"key": "val2"}

        config = self.config.merge_config(project_config, user_config)

        # THEN project config (1st) overrides user config value
        self.assertEqual(config['key'], 'val2')

    def test_load(self):
        # GIVEN a project and user configuration file exist
        # WHEN config is loaded
        loaded_config = self.config.load()

        expected_config = yaml.safe_load(self.samrc_user_level)
        expected_config['default_port'] = 4040

        # THEN loaded configuration should be equals to project config
        # self.assertEqual(loaded_config, project_config)
        self.assertDictContainsSubset(loaded_config, expected_config)

    def test_load_project_config_only(self):
        # GIVEN a project configuration file exist but user
        self.user_config.rename(
            Path.home().joinpath('.samrc.backup'))

        # WHEN config is loaded
        loaded_config = self.config.load()

        expected_config = yaml.safe_load(self.samrc_project_level)

        # THEN loaded configuration should be equals to project config
        # self.assertEqual(loaded_config, project_config)
        self.assertDictContainsSubset(loaded_config, expected_config)

        # Rename it backwards
        Path.home().joinpath('.samrc.backup').rename(self.user_config)

    def test_load_user_config_only(self):
        # GIVEN an user configuration exist but project
        # Rename project config instead of deleting it
        self.project_config.rename(
            Path.cwd().joinpath('.samrc.backup'))

        # WHEN config is loaded
        loaded_config = self.config.load()
        user_config = yaml.safe_load(self.user_config.read_text())

        # THEN user configuration should be loaded
        self.assertEqual(loaded_config, user_config)

        # Rename it backwards
        Path.cwd().joinpath('.samrc.backup').rename(self.project_config)

    def test_validate_config(self):
        loaded_config = self.config.load()
        config_schema = ""

        with self.assertRaisesRegexp(Exception, "Not implemented yet"):
            self.config.validate_config(loaded_config, config_schema)

    def test_no_config(self):
        # GIVEN no configuration is found
        # WHEN config is loaded

        self.project_config.rename(
            Path.cwd().joinpath('.samrc.backup'))

        self.user_config.rename(
            Path.home().joinpath('.samrc.backup'))

        # THEN config should be None
        loaded_config = self.config.load()
        self.assertFalse(loaded_config)

        # Rename it backwards
        Path.cwd().joinpath('.samrc.backup').rename(self.project_config)
        Path.home().joinpath('.samrc.backup').rename(self.user_config)
