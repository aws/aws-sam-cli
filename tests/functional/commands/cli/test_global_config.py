import json
import tempfile
import shutil
import os
from time import time

from unittest.mock import MagicMock, patch, ANY
from unittest import TestCase
from samcli.cli.global_config import GlobalConfig
from pathlib import Path


class TestGlobalConfig(TestCase):
    def setUp(self):
        self._cfg_dir = tempfile.mkdtemp()
        if "SAM_CLI_TELEMETRY" in os.environ:
            os.environ.pop("SAM_CLI_TELEMETRY")
        self.saved_env_var = dict(os.environ)

    def tearDown(self):
        shutil.rmtree(self._cfg_dir)
        # Force singleton to recreate after each test
        GlobalConfig._Singleton__instance = None
        os.environ.clear()
        os.environ.update(self.saved_env_var)

    def test_installation_id_with_side_effect(self):
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        installation_id = gc.installation_id
        expected_path = Path(self._cfg_dir, "metadata.json")
        json_body = json.loads(expected_path.read_text())
        self.assertIsNotNone(installation_id)
        self.assertTrue(expected_path.exists())
        self.assertEqual(installation_id, json_body["installationId"])
        installation_id_refetch = gc.installation_id
        self.assertEqual(installation_id, installation_id_refetch)

    def test_installation_id_on_existing_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"foo": "bar"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        installation_id = gc.installation_id
        json_body = json.loads(path.read_text())
        self.assertEqual(installation_id, json_body["installationId"])
        self.assertEqual("bar", json_body["foo"])

    def test_installation_id_exists(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        installation_id = gc.installation_id
        self.assertEqual("stub-uuid", installation_id)

    def test_invalid_json(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            f.write("NOT JSON, PROBABLY VALID YAML AM I RIGHT!?")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertIsInstance(gc.installation_id, str)
        self.assertFalse(gc.telemetry_enabled)

    def test_telemetry_flag_provided(self):
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.telemetry_enabled = True
        self.assertTrue(gc.telemetry_enabled)

    def test_telemetry_flag_from_cfg(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertTrue(gc.telemetry_enabled)

    def test_telemetry_flag_no_file(self):
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertFalse(gc.telemetry_enabled)

    def test_telemetry_flag_not_in_cfg(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertFalse(gc.telemetry_enabled)

    def test_set_telemetry_flag_no_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertFalse(gc.telemetry_enabled)  # pre-state test
        gc.telemetry_enabled = True
        from_gc = gc.telemetry_enabled
        json_body = json.loads(path.read_text())
        from_file = json_body["telemetryEnabled"]
        self.assertTrue(from_gc)
        self.assertTrue(from_file)

    def test_set_telemetry_flag_no_key(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.telemetry_enabled = True
        json_body = json.loads(path.read_text())
        self.assertTrue(gc.telemetry_enabled)
        self.assertTrue(json_body["telemetryEnabled"])

    def test_set_telemetry_flag_overwrite(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertTrue(gc.telemetry_enabled)
        gc.telemetry_enabled = False
        json_body = json.loads(path.read_text())
        self.assertFalse(gc.telemetry_enabled)
        self.assertFalse(json_body["telemetryEnabled"])

    def test_telemetry_flag_explicit_false(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.telemetry_enabled = False
        self.assertFalse(gc.telemetry_enabled)

    def test_last_version_check_value_provided(self):
        last_version_check_value = time()
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.last_version_check = last_version_check_value
        self.assertEqual(gc.last_version_check, last_version_check_value)

    def test_last_version_check_value_cfg(self):
        last_version_check_value = time()
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"lastVersionCheck": last_version_check_value}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertEqual(gc.last_version_check, last_version_check_value)

    def test_last_version_check_value_no_file(self):
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertIsNone(gc.last_version_check)

    def test_last_version_check_value_not_in_cfg(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertIsNone(gc.last_version_check)

    def test_set_last_version_check_value_no_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertIsNone(gc.last_version_check)  # pre-state test

        last_version_check_value = time()
        gc.last_version_check = last_version_check_value
        from_gc = gc.last_version_check
        json_body = json.loads(path.read_text())
        from_file = json_body["lastVersionCheck"]
        self.assertEqual(from_gc, from_file)

    def test_last_version_check_value_no_key(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)

        last_version_check_value = time()
        gc.last_version_check = last_version_check_value
        json_body = json.loads(path.read_text())
        self.assertEqual(gc.last_version_check, json_body["lastVersionCheck"])

    def test_set_last_version_check_value_overwrite(self):
        last_version_check_value = time()
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"lastVersionCheck": last_version_check_value}
            f.write(json.dumps(cfg, indent=4) + "\n")

        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        self.assertEqual(gc.last_version_check, last_version_check_value)

        last_version_check_new_value = time()
        gc.last_version_check = last_version_check_new_value
        json_body = json.loads(path.read_text())
        self.assertEqual(gc.last_version_check, json_body["lastVersionCheck"])

    def test_last_version_check_explicit_value(self):
        last_version_check_value = time()
        last_version_check_value_override = time()
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"lastVersionCheck": last_version_check_value}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.last_version_check = last_version_check_value_override
        self.assertEqual(gc.last_version_check, last_version_check_value_override)

    def test_setter_on_invalid_json(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            f.write("NOT JSON, PROBABLY VALID YAML AM I RIGHT!?")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        gc.telemetry_enabled = True
        self.assertTrue(gc.telemetry_enabled)

    @patch("samcli.cli.global_config.LOG")
    def test_setter_cannot_open_file(self, patched_logger):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        m = MagicMock()
        m.side_effect = OSError("fail")
        gc = GlobalConfig()
        gc.config_dir = Path(self._cfg_dir)
        with patch("samcli.cli.global_config.Path.write_text", m):
            gc.telemetry_enabled = True
            patched_logger.warning.assert_called_with("Error when writing global config file: %s", ANY, exc_info=ANY)
