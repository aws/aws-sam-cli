import os
from pathlib import Path

from unittest import TestCase

from samcli.lib.config.exceptions import SamConfigVersionException
from samcli.lib.config.version import VERSION_KEY, SAM_CONFIG_VERSION
from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME


class TestSamConfig(TestCase):
    def setUp(self):
        self.config_dir = os.getcwd()
        self.samconfig = SamConfig(self.config_dir)

    def tearDown(self):
        if self.samconfig.exists():
            os.remove(self.samconfig.path())

    def _setup_config(self):
        self.samconfig.put(cmd_names=["local", "start", "api"], section="parameters", key="port", value=5401)
        self.samconfig.flush()
        self.assertTrue(self.samconfig.exists())
        self.assertTrue(self.samconfig.sanity_check())
        self.assertEqual(SAM_CONFIG_VERSION, self.samconfig.document.get(VERSION_KEY))

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

    def test_check_sanity(self):
        self.assertTrue(self.samconfig.sanity_check())

    def test_check_version_non_supported_type(self):
        self._setup_config()
        self.samconfig.document.remove(VERSION_KEY)
        self.samconfig.document.add(VERSION_KEY, "aadeff")
        with self.assertRaises(SamConfigVersionException):
            self.samconfig.sanity_check()

    def test_check_version_no_version_exists(self):
        self._setup_config()
        self.samconfig.document.remove(VERSION_KEY)
        with self.assertRaises(SamConfigVersionException):
            self.samconfig.sanity_check()

    def test_check_version_float(self):
        self._setup_config()
        self.samconfig.document.remove(VERSION_KEY)
        self.samconfig.document.add(VERSION_KEY, 0.2)
        self.samconfig.sanity_check()

    def test_write_config_file_non_standard_version(self):
        self._setup_config()
        self.samconfig.document.remove(VERSION_KEY)
        self.samconfig.document.add(VERSION_KEY, 0.2)
        self.samconfig.put(cmd_names=["local", "start", "api"], section="parameters", key="skip_pull_image", value=True)
        self.samconfig.sanity_check()
        self.assertEqual(self.samconfig.document.get(VERSION_KEY), 0.2)
