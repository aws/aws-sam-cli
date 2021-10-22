import os
from unittest.mock import ANY, MagicMock, patch
from unittest import TestCase
from samcli.cli.global_config import ConfigEntry, DefaultEntry, GlobalConfig
from pathlib import Path


class TestGlobalConfig(TestCase):
    def setUp(self):
        # Force singleton to recreate after each test
        GlobalConfig._Singleton__instance = None

        path_write_patch = patch("samcli.cli.global_config.Path.write_text")
        self.path_write_mock = path_write_patch.start()
        self.addCleanup(path_write_patch.stop)

        path_read_patch = patch("samcli.cli.global_config.Path.read_text")
        self.path_read_mock = path_read_patch.start()
        self.addCleanup(path_read_patch.stop)

        path_exists_patch = patch("samcli.cli.global_config.Path.exists")
        self.path_exists_mock = path_exists_patch.start()
        self.path_exists_mock.return_value = True
        self.addCleanup(path_exists_patch.stop)

        path_mkdir_patch = patch("samcli.cli.global_config.Path.mkdir")
        self.path_mkdir_mock = path_mkdir_patch.start()
        self.addCleanup(path_mkdir_patch.stop)

        json_patch = patch("samcli.cli.global_config.json")
        self.json_mock = json_patch.start()
        self.json_mock.loads.return_value = {}
        self.json_mock.dumps.return_value = "{}"
        self.addCleanup(json_patch.stop)

        click_patch = patch("samcli.cli.global_config.click")
        self.click_mock = click_patch.start()
        self.click_mock.get_app_dir.return_value = "app_dir"
        self.addCleanup(click_patch.stop)

        threading_patch = patch("samcli.cli.global_config.threading")
        self.threading_mock = threading_patch.start()
        self.addCleanup(threading_patch.stop)

        self.patch_environ({})

    def patch_environ(self, values):
        environ_patch = patch.dict(os.environ, values, clear=True)
        environ_patch.start()
        self.addCleanup(environ_patch.stop)

    def tearDown(self):
        # Force singleton to recreate after each test
        GlobalConfig._Singleton__instance = None

    def test_singleton(self):
        gc1 = GlobalConfig()
        gc2 = GlobalConfig()
        self.assertTrue(gc1 is gc2)

    def test_default_config_dir(self):
        self.assertEqual(GlobalConfig().config_dir, Path("app_dir"))

    def test_inject_config_dir(self):
        self.patch_environ({"__SAM_CLI_APP_DIR": "inject_dir"})
        self.assertEqual(GlobalConfig().config_dir, Path("inject_dir"))

    @patch("samcli.cli.global_config.Path.is_dir")
    def test_set_config_dir(self, is_dir_mock):
        is_dir_mock.return_value = True
        GlobalConfig().config_dir = Path("new_app_dir")
        self.assertEqual(GlobalConfig().config_dir, Path("new_app_dir"))
        self.assertIsNone(GlobalConfig()._config_data)

    @patch("samcli.cli.global_config.Path.is_dir")
    def test_set_config_dir_not_dir(self, is_dir_mock):
        is_dir_mock.return_value = False
        with self.assertRaises(ValueError):
            GlobalConfig().config_dir = Path("new_app_dir")
        self.assertEqual(GlobalConfig().config_dir, Path("app_dir"))

    def test_default_config_filename(self):
        self.assertEqual(GlobalConfig().config_filename, "metadata.json")

    def test_set_config_filename(self):
        GlobalConfig().config_filename = "new_metadata.json"
        self.assertEqual(GlobalConfig().config_filename, "new_metadata.json")
        self.assertIsNone(GlobalConfig()._config_data)

    def test_default_config_path(self):
        self.assertEqual(GlobalConfig().config_path, Path("app_dir", "metadata.json"))

    def test_get_value_locking(self):
        GlobalConfig()._get_value = MagicMock()
        GlobalConfig().get_value(MagicMock(), True, object, False, True)
        GlobalConfig()._access_lock.__enter__.assert_called_once()
        GlobalConfig()._get_value.assert_called_once()

    def test_set_value_locking(self):
        GlobalConfig()._set_value = MagicMock()
        GlobalConfig().set_value(MagicMock(), MagicMock(), True, True)
        GlobalConfig()._access_lock.__enter__.assert_called_once()
        GlobalConfig()._set_value.assert_called_once()

    def test_get_value_env_var_only(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        result = GlobalConfig().get_value(
            ConfigEntry(None, "ENV_VAR"), default="default", value_type=str, is_flag=False, reload_config=False
        )
        self.assertEqual(result, "env_var_value")

    def test_get_value_env_var_and_config_priority(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", "ENV_VAR"), default="default", value_type=str, is_flag=False, reload_config=False
        )
        self.assertEqual(result, "env_var_value")

    def test_get_value_config_only(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        self.json_mock.loads.return_value = {"config_key": "config_value"}
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", None), default="default", value_type=str, is_flag=False, reload_config=False
        )
        self.assertEqual(result, "config_value")

    def test_get_value_error_default(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        self.json_mock.loads.side_effect = ValueError()
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", None), default="default", value_type=str, is_flag=False, reload_config=False
        )
        self.assertEqual(result, "default")

    def test_get_value_incorrect_type_default(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        self.json_mock.loads.return_value = {"config_key": 1}
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", None), default="default", value_type=str, is_flag=True, reload_config=False
        )
        self.assertEqual(result, "default")

    def test_get_value_flag_env_var_True(self):
        self.patch_environ({"ENV_VAR": "1"})
        self.json_mock.loads.return_value = {"config_key": False}
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", "ENV_VAR"), default=False, value_type=bool, is_flag=True, reload_config=False
        )
        self.assertTrue(result)

    def test_get_value_flag_env_var_False(self):
        self.patch_environ({"ENV_VAR": "0"})
        self.json_mock.loads.return_value = {"config_key": True}
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", "ENV_VAR"), default=True, value_type=bool, is_flag=True, reload_config=False
        )
        self.assertFalse(result)

    def test_get_value_flag_config_True(self):
        self.json_mock.loads.return_value = {"config_key": True}
        result = GlobalConfig().get_value(
            ConfigEntry("config_key", "ENV_VAR"), default=False, value_type=bool, is_flag=True, reload_config=False
        )
        self.assertTrue(result)

    def test_set_value(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        GlobalConfig().set_value(ConfigEntry("config_key", "ENV_VAR"), "value", False, True)
        self.assertEqual(os.environ["ENV_VAR"], "value")
        self.assertEqual(GlobalConfig()._config_data["config_key"], "value")
        self.json_mock.dumps.assert_called_once_with({"config_key": "value"}, indent=ANY)
        self.path_write_mock.assert_called_once()

    def test_set_value_non_persistent(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        GlobalConfig().set_value(ConfigEntry("config_key", "ENV_VAR", False), "value", False, True)
        self.assertEqual(os.environ["ENV_VAR"], "value")
        self.assertEqual(GlobalConfig()._config_data["config_key"], "value")
        self.json_mock.dumps.assert_called_once_with({}, indent=ANY)
        self.path_write_mock.assert_called_once()

    def test_set_value_no_flush(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        GlobalConfig().set_value(ConfigEntry("config_key", "ENV_VAR"), "value", False, False)
        self.assertEqual(os.environ["ENV_VAR"], "value")
        self.assertEqual(GlobalConfig()._config_data["config_key"], "value")
        self.json_mock.dumps.assert_not_called()
        self.path_write_mock.assert_not_called()

    def test_set_value_flag_true(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        GlobalConfig().set_value(ConfigEntry("config_key", "ENV_VAR"), True, True, True)
        self.assertEqual(os.environ["ENV_VAR"], "1")
        self.assertEqual(GlobalConfig()._config_data["config_key"], True)
        self.json_mock.dumps.assert_called_once()
        self.path_write_mock.assert_called_once()

    def test_set_value_flag_false(self):
        self.patch_environ({"ENV_VAR": "env_var_value"})
        GlobalConfig().set_value(ConfigEntry("config_key", "ENV_VAR"), False, True, True)
        self.assertEqual(os.environ["ENV_VAR"], "0")
        self.assertEqual(GlobalConfig()._config_data["config_key"], False)
        self.json_mock.dumps.assert_called_once()
        self.path_write_mock.assert_called_once()

    def test_load_config(self):
        self.path_exists_mock.return_value = True
        self.json_mock.loads.return_value = {"a": "b"}
        self.assertIsNone(GlobalConfig()._config_data)
        GlobalConfig()._load_config()
        self.assertEqual(GlobalConfig()._config_data, {"a": "b"})

    def test_load_config_file_does_not_exist(self):
        self.path_exists_mock.return_value = False
        self.json_mock.loads.return_value = {"a": "b"}
        self.assertIsNone(GlobalConfig()._config_data)
        GlobalConfig()._load_config()
        self.assertEqual(GlobalConfig()._config_data, {})

    def test_load_config_error(self):
        self.path_exists_mock.return_value = True
        self.json_mock.loads.return_value = {"a": "b"}
        self.json_mock.loads.side_effect = ValueError()
        self.assertIsNone(GlobalConfig()._config_data)
        GlobalConfig()._load_config()
        self.assertEqual(GlobalConfig()._config_data, {})

    def test_write_config(self):
        self.path_exists_mock.return_value = False
        GlobalConfig()._persistent_fields = ["a"]
        GlobalConfig()._config_data = {"a": 1}
        GlobalConfig()._write_config()
        self.json_mock.dumps.assert_called_once()
        self.path_mkdir_mock.assert_called_once()
        self.path_write_mock.assert_called_once()

    @patch("samcli.cli.global_config.uuid.uuid4")
    def test_get_installation_id_saved(self, uuid_mock):
        self.json_mock.loads.return_value = {DefaultEntry.INSTALLATION_ID.config_key: "saved_uuid"}
        uuid_mock.return_value = "default_uuid"
        result = GlobalConfig().installation_id
        self.assertEqual(result, "saved_uuid")

    @patch("samcli.cli.global_config.uuid.uuid4")
    def test_get_installation_id_default(self, uuid_mock):
        self.json_mock.loads.return_value = {}
        uuid_mock.return_value = "default_uuid"
        result = GlobalConfig().installation_id
        self.assertEqual(result, "default_uuid")

    def test_get_telemetry_enabled(self):
        self.patch_environ({DefaultEntry.TELEMETRY.env_var_key: "1"})
        self.json_mock.loads.return_value = {DefaultEntry.TELEMETRY.config_key: True}
        result = GlobalConfig().telemetry_enabled
        self.assertEqual(result, True)

    def test_get_telemetry_disabled(self):
        self.patch_environ({DefaultEntry.TELEMETRY.env_var_key: "0"})
        self.json_mock.loads.return_value = {DefaultEntry.TELEMETRY.config_key: True}
        result = GlobalConfig().telemetry_enabled
        self.assertEqual(result, False)

    def test_get_telemetry_default(self):
        self.patch_environ({"__SAM_CLI_APP_DIR": "inject_dir"})
        result = GlobalConfig().telemetry_enabled
        self.assertIsNone(result)

    def test_set_telemetry(self):
        GlobalConfig().telemetry_enabled = True
        self.assertEqual(os.environ[DefaultEntry.TELEMETRY.env_var_key], "1")
        self.assertEqual(GlobalConfig()._config_data[DefaultEntry.TELEMETRY.config_key], True)

    def test_get_last_version_check(self):
        self.json_mock.loads.return_value = {DefaultEntry.LAST_VERSION_CHECK.config_key: 123.4}
        result = GlobalConfig().last_version_check
        self.assertEqual(result, 123.4)

    def test_set_last_version_check(self):
        GlobalConfig().last_version_check = 123.4
        self.assertEqual(GlobalConfig()._config_data[DefaultEntry.LAST_VERSION_CHECK.config_key], 123.4)
