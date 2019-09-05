import json
import tempfile
import shutil

from mock import mock_open, patch
from unittest import TestCase
from json import JSONDecodeError
from samcli.cli.global_config import GlobalConfig

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class TestGlobalConfig(TestCase):
    def setUp(self):
        self._cfg_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._cfg_dir)

    def test_installation_id_with_side_effect(self):
        gc = GlobalConfig(config_dir=self._cfg_dir)
        installation_id = gc.installation_id
        expected_path = Path(self._cfg_dir, "metadata.json")
        json_body = json.loads(expected_path.read_text())
        self.assertIsNotNone(installation_id)
        self.assertTrue(expected_path.exists())
        self.assertEquals(installation_id, json_body["installationId"])
        installation_id_refetch = gc.installation_id
        self.assertEquals(installation_id, installation_id_refetch)

    def test_installation_id_on_existing_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"foo": "bar"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        installation_id = gc.installation_id
        json_body = json.loads(path.read_text())
        self.assertEquals(installation_id, json_body["installationId"])
        self.assertEquals("bar", json_body["foo"])

    def test_installation_id_exists(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        installation_id = gc.installation_id
        self.assertEquals("stub-uuid", installation_id)

    def test_init_override(self):
        gc = GlobalConfig(installation_id="foo")
        installation_id = gc.installation_id
        self.assertEquals("foo", installation_id)

    def test_invalid_json(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            f.write("NOT JSON, PROBABLY VALID YAML AM I RIGHT!?")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        self.assertIsNone(gc.installation_id)
        self.assertFalse(gc.telemetry_enabled)

    def test_telemetry_flag_provided(self):
        gc = GlobalConfig(telemetry_enabled=True)
        self.assertTrue(gc.telemetry_enabled)

    def test_telemetry_flag_from_cfg(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        self.assertTrue(gc.telemetry_enabled)

    def test_telemetry_flag_no_file(self):
        gc = GlobalConfig(config_dir=self._cfg_dir)
        self.assertFalse(gc.telemetry_enabled)

    def test_telemetry_flag_not_in_cfg(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"installationId": "stub-uuid"}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        self.assertFalse(gc.telemetry_enabled)

    def test_set_telemetry_flag_no_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        self.assertIsNone(gc.telemetry_enabled)  # pre-state test
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
        gc = GlobalConfig(config_dir=self._cfg_dir)
        gc.telemetry_enabled = True
        json_body = json.loads(path.read_text())
        self.assertTrue(gc.telemetry_enabled)
        self.assertTrue(json_body["telemetryEnabled"])

    def test_set_telemetry_flag_overwrite(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        gc = GlobalConfig(config_dir=self._cfg_dir)
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
        gc = GlobalConfig(config_dir=self._cfg_dir, telemetry_enabled=False)
        self.assertFalse(gc.telemetry_enabled)

    def test_setter_raises_on_invalid_json(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            f.write("NOT JSON, PROBABLY VALID YAML AM I RIGHT!?")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        with self.assertRaises(JSONDecodeError):
            gc.telemetry_enabled = True

    def test_setter_cannot_open_file(self):
        path = Path(self._cfg_dir, "metadata.json")
        with open(str(path), "w") as f:
            cfg = {"telemetryEnabled": True}
            f.write(json.dumps(cfg, indent=4) + "\n")
        m = mock_open()
        m.side_effect = IOError("fail")
        gc = GlobalConfig(config_dir=self._cfg_dir)
        with patch("samcli.cli.global_config.open", m):
            with self.assertRaises(IOError):
                gc.telemetry_enabled = True
