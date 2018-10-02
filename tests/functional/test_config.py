from unittest import TestCase

from samcli.config.config import Config, samrc

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
        self.samrc_valid_sample = """
        aws_region: 'eu-west-1'
        aws_profile: 'demo'
        default_port: 8080
        debug_port: 8080
        template: 'template.yaml'
        """
        self.project_config = Path.cwd().joinpath('.samrc')
        self.user_config = Path.home().joinpath('.samrc')

        with self.project_config.open(mode='w') as f:
            f.write(self.samrc_valid_sample)

    def tearDown(self):
        self.project_config.unlink()

    def test_merge_config(self):
        # GIVEN two dictionaries were given
        # WHERE 'key' is present in both but has different values
        user_config = {"key": "val1"}
        project_config = {"key": "val2"}

        config = self.config.merge_config(project_config, user_config)

        # THEN project config (1st) overrides user config value
        self.assertEqual(config['key'], 'val2')

    def test_load(self):
        with self.project_config.open(mode='w') as f:
            f.write(self.samrc_valid_sample)

        # GIVEN a project configuration file exists but user config
        # WHEN config is to be loaded
        loaded_config = self.config.load()
        project_config = yaml.safe_load(self.project_config.read_text())

        # THEN loaded configuration should be equals to project config
        self.assertEqual(loaded_config, project_config)

    def test_load_config_override(self):
        # If user's config exist don't override
        # As developer may have .samrc already in place
        if not self.user_config.is_file():
            with self.user_config.open(mode='w') as f:
                f.write(self.samrc_valid_sample)

        # GIVEN both project and user configuration exist
        # WHEN config is to be loaded

        with self.project_config.open(mode='w') as f:
            project_has_custom_port = """
            default_port: 4040
            """
            f.write(project_has_custom_port)

        loaded_config = self.config.load()

        # THEN any duplicated keys
        # should be overriden by project's config values
        self.assertEqual(loaded_config['default_port'], 4040)

    def test_samrc_singleton(self):

        loaded_config = self.config.load()
        loaded_samrc = samrc

        self.assertEqual(loaded_config, loaded_samrc)

    def test_validate_config(self):
        loaded_config = self.config.load()
        config_schema = ""

        with self.assertRaisesRegexp(Exception, "Not implemented yet"):
            self.config.validate_config(loaded_config, config_schema)
