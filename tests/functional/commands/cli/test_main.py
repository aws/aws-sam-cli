import mock
import tempfile
import shutil

from unittest import TestCase
from click.testing import CliRunner
from samcli.cli.main import cli
from samcli.cli.global_config import GlobalConfig


class TestTelemetryPrompt(TestCase):
    def setUp(self):
        self._cfg_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._cfg_dir)

    def test_cli_prompt(self):
        gc = GlobalConfig(config_dir=self._cfg_dir)
        with mock.patch("samcli.cli.main.global_cfg", gc):
            self.assertIsNone(gc.telemetry_enabled)  # pre-state test
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"])
            # assertFalse is not appropriate, because None would also count
            self.assertEqual(False, gc.telemetry_enabled)

    def test_cli_prompt_false(self):
        gc = GlobalConfig(config_dir=self._cfg_dir)
        with mock.patch("samcli.cli.main.global_cfg", gc):
            self.assertIsNone(gc.telemetry_enabled)  # pre-state test
            runner = CliRunner()
            runner.invoke(cli, ["local", "generate-event", "s3"], input="Y")
            self.assertEqual(True, gc.telemetry_enabled)
