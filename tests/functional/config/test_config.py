from unittest import TestCase

import logging
from samcli.config.config import Config

# This is an attempt to do a controlled import. pathlib is in the
# Python standard library starting at 3.4. This will import pathlib2,
# which is a backport of the Python Standard Library pathlib
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

import jsonschema
import yaml

LOG = logging.getLogger(__name__)


class TestConfig(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project_config = Path.cwd().joinpath('.samrc')
        cls.project_config_backup = Path.cwd().joinpath('.samrc.backup')
        cls.user_config = Path.home().joinpath('.samrc')
        cls.user_config_backup = Path.home().joinpath('.samrc.backup')
        cls.samrc_backup_message = "Backing up existing SAMRC as may be running on developer's laptop"

        # Backups up existing SAMRC in case func tests are running locally
        # No one wants to lose their existing configuration ;)
        if cls.user_config.exists() and not cls.user_config_backup.exists():
            LOG.info(cls.samrc_backup_message)
            cls.user_config.rename(cls.user_config_backup)

        if cls.project_config.exists() and not cls.project_config_backup.exists():
            LOG.info(cls.samrc_backup_message)
            cls.project_config.rename(cls.project_config_backup)

    @classmethod
    def tearDownClass(cls):
        if cls.project_config.exists():
            cls.project_config.unlink()

        if cls.project_config_backup.exists():
            cls.project_config_backup.rename(cls.project_config)

        if cls.user_config.exists():
            cls.user_config.unlink()

        if cls.user_config_backup.exists():
            cls.user_config_backup.rename(cls.user_config)

    def setUp(self):
        self.config = Config()
        self.valid_samrc_user_level = """
default:
    aws_region: 'eu-west-1'
    aws_profile: 'demo'
    default_port: 8080
    debug_port: 8080
    template: 'template.yaml'
        """
        self.valid_samrc_project_level = """
default:
    default_port: 4040
future_proof_section:
    something: else
        """

        with self.project_config.open(mode='w') as f:
            f.write(self.valid_samrc_project_level)

        with self.user_config.open(mode='w') as f:
            f.write(self.valid_samrc_user_level)

    def test_load(self):
        # GIVEN a project and user configuration file exist
        # WHEN config is loaded
        loaded_config = self.config.load()

        loaded_project_config = yaml.safe_load(self.valid_samrc_user_level)
        loaded_project_config['default']['default_port'] = 4040

        # THEN loaded configuration should be equals to project config's keys
        # As project config should always override user when duplicates are found
        # self.assertEqual(loaded_config, project_config)
        self.assertEqual(loaded_config['default']['default_port'], loaded_project_config['default']['default_port'])

    def test_load_project_config_only(self):
        # GIVEN a project configuration file exist but user
        self.user_config.unlink()

        # WHEN config is loaded
        loaded_config = self.config.load()

        expected_config = yaml.safe_load(self.valid_samrc_project_level)

        # THEN loaded configuration should be equals to project config
        # self.assertEqual(loaded_config, project_config)
        self.assertDictContainsSubset(loaded_config, expected_config)

    def test_load_user_config_only(self):
        # GIVEN an user configuration exist but project
        # Rename project config instead of deleting it
        self.project_config.unlink()

        # WHEN config is loaded
        loaded_config = self.config.load()
        user_config = yaml.safe_load(self.user_config.read_text())

        # THEN user configuration should be loaded
        self.assertEqual(loaded_config, user_config)

    def test_no_config(self):
        # GIVEN no configuration is found
        # WHEN config is loaded

        self.project_config.unlink()
        self.user_config.unlink()

        # THEN config should be None
        loaded_config = self.config.load()
        self.assertFalse(loaded_config)

    def test_invalid_config(self):
        # GIVEN an invalid SAMRC is passed
        # WHEN configuration is loaded
        # Some fields are optional but their value
        # should be checked against schema when present

        loaded_config = self.config.load()
        loaded_config['default']['default_port'] = '4040'

        # THEN throw a JSON Schema Error
        with self.assertRaisesRegex(jsonschema.exceptions.ValidationError, "'4040' is not of type 'integer'"):
            self.config.validate_config(loaded_config, self.config.default_schema)
