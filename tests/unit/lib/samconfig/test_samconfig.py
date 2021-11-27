import os
from pathlib import Path
from unittest import TestCase

from samcli.lib.config.exceptions import SamConfigVersionException
from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME, DEFAULT_GLOBAL_CMDNAME, DEFAULT_ENV
from samcli.lib.config.version import VERSION_KEY, SAM_CONFIG_VERSION
from samcli.lib.utils import osutils


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
        self._check_config_file()

    def _check_config_file(self):
        self.assertTrue(self.samconfig.exists())
        self.assertTrue(self.samconfig.sanity_check())
        self.assertEqual(SAM_CONFIG_VERSION, self.samconfig.document.get(VERSION_KEY))

    def _update_samconfig(self, cmd_names, section, key, value, env=None):
        if env:
            self.samconfig.put(cmd_names=cmd_names, section=section, key=key, value=value, env=env)
        else:
            self.samconfig.put(cmd_names=cmd_names, section=section, key=key, value=value)
        self.samconfig.flush()
        self._check_config_file()

    def test_init(self):
        self.assertEqual(self.samconfig.filepath, Path(self.config_dir, DEFAULT_CONFIG_FILE_NAME))

    def test_get_stage_configuration_names(self):
        self.assertEqual(self.samconfig.get_stage_configuration_names(), [])
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5401, env="stage1")
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5401, env="stage2")
        self.assertEqual(self.samconfig.get_stage_configuration_names(), ["stage1", "stage2"])
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5401)
        self.assertEqual(self.samconfig.get_stage_configuration_names(), ["stage1", "stage2", DEFAULT_ENV])

    def test_param_overwrite(self):
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5401, env="myEnv")
        self.assertEqual(
            {"port": 5401}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv")
        )
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5402, env="myEnv")
        self.assertEqual(
            {"port": 5402}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv")
        )

    def test_add_params_from_different_env(self):
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5401, env="myEnvA")
        self.assertEqual(
            {"port": 5401}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnvA")
        )
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="port", value=5402, env="myEnvB")
        self.assertEqual(
            {"port": 5401}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnvA")
        )
        self.assertEqual(
            {"port": 5402}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnvB")
        )

    def test_add_params_from_different_cmd_names(self):
        self._update_samconfig(cmd_names=["myCommand1"], section="mySection", key="port", value="ABC", env="myEnv")
        self.assertEqual(
            {"port": "ABC"}, self.samconfig.get_all(cmd_names=["myCommand1"], section="mySection", env="myEnv")
        )
        self._update_samconfig(
            cmd_names=["myCommand2", "mySubCommand"], section="mySection", key="port", value="DEF", env="myEnv"
        )
        self.assertEqual(
            {"port": "ABC"}, self.samconfig.get_all(cmd_names=["myCommand1"], section="mySection", env="myEnv")
        )
        self.assertEqual(
            {"port": "DEF"},
            self.samconfig.get_all(cmd_names=["myCommand2", "mySubCommand"], section="mySection", env="myEnv"),
        )

    def test_add_params_from_different_sections(self):
        self._update_samconfig(cmd_names=["myCommand"], section="mySection1", key="testKey1", value=True, env="myEnv")
        self.assertEqual(
            {"testKey1": True}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection1", env="myEnv")
        )
        self._update_samconfig(cmd_names=["myCommand"], section="mySection2", key="testKey2", value=False, env="myEnv")
        self.assertEqual(
            {"testKey1": True},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection1", env="myEnv"),
        )
        self.assertEqual(
            {"testKey2": False},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection2", env="myEnv"),
        )

    def test_add_params_from_different_keys(self):
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="testKey1", value=True, env="myEnv")
        self.assertEqual(
            {"testKey1": True}, self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv")
        )
        self._update_samconfig(cmd_names=["myCommand"], section="mySection", key="testKey2", value=321, env="myEnv")
        self.assertEqual(
            {"testKey1": True, "testKey2": 321},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv"),
        )

    def test_get_global_param(self):
        self._update_samconfig(
            cmd_names=[DEFAULT_GLOBAL_CMDNAME],
            section="mySection",
            key="testKey1",
            value="ValueFromGlobal",
            env="myEnv",
        )
        self.assertEqual(
            {"testKey1": "ValueFromGlobal"},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv"),
        )

    def test_global_param_priority(self):
        self._update_samconfig(
            cmd_names=[DEFAULT_GLOBAL_CMDNAME],
            section="mySection",
            key="testKey1",
            value="ValueFromGlobal1",
            env="myEnv",
        )
        self._update_samconfig(
            cmd_names=["myCommand"], section="mySection", key="testKey1", value="ValueFromCommand", env="myEnv"
        )
        self._update_samconfig(
            cmd_names=[DEFAULT_GLOBAL_CMDNAME],
            section="mySection",
            key="testKey1",
            value="ValueFromGlobal2",
            env="myEnv",
        )
        self.assertEqual(
            {"testKey1": "ValueFromCommand"},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv"),
        )

    def test_dedup_global_param(self):
        self._update_samconfig(
            cmd_names=[DEFAULT_GLOBAL_CMDNAME],
            section="mySection",
            key="testKey",
            value="ValueFromGlobal",
            env="myEnv",
        )
        self._update_samconfig(
            cmd_names=["myCommand"], section="mySection", key="testKey", value="ValueFromGlobal", env="myEnv"
        )
        self.assertEqual(
            {"testKey": "ValueFromGlobal"},
            self.samconfig.get_all(cmd_names=["myCommand"], section="mySection", env="myEnv"),
        )
        self.assertEqual(self.samconfig.document["myEnv"]["myCommand"]["mySection"], {})
        self.assertEqual(
            self.samconfig.document["myEnv"][DEFAULT_GLOBAL_CMDNAME]["mySection"], {"testKey": "ValueFromGlobal"}
        )

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

    def test_write_config_file_will_create_the_file_if_not_exist(self):
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            non_existing_dir = os.path.join(tempdir, "non-existing-dir")
            non_existing_file = "non-existing-file"
            samconfig = SamConfig(config_dir=non_existing_dir, filename=non_existing_file)

            self.assertFalse(samconfig.exists())

            samconfig.flush()
            self.assertFalse(samconfig.exists())  # nothing to write, no need to create the file

            samconfig.put(cmd_names=["any", "command"], section="any-section", key="any-key", value="any-value")
            samconfig.flush()
            self.assertTrue(samconfig.exists())
