import os
from pathlib import Path

from unittest import TestCase

from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME


class TestSamConfig(TestCase):
    def setUp(self):
        self.config_dir = os.getcwd()
        self.samconfig = SamConfig(self.config_dir)
        open(self.samconfig.path(), "w").close()

    def tearDown(self):
        if self.samconfig.exists():
            os.remove(self.samconfig.path())

    def _setup_config(self):
        self.samconfig.put(cmd_names=["local", "start", "api"], section="parameters", key="port", value=5401)
        self.samconfig.flush()

    def test_init(self):
        self.assertEqual(self.samconfig.filepath, Path(self.config_dir, DEFAULT_CONFIG_FILE_NAME))

    def test_check_config_get(self):
        self._setup_config()
        self.assertEqual(
            {"port": 5401}, self.samconfig.get_all(cmd_names=["local", "start", "api"], section="parameters")
        )

    def test_check_config_exists(self):
        self._setup_config()
        self.assertTrue(self.samconfig.exists())
