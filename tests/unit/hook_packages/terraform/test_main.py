from unittest import TestCase
from unittest.mock import patch

from samcli.hook_packages.terraform import main


class TestTerraformHookEntrypoints(TestCase):
    @patch("samcli.hook_packages.terraform.main.prepare_hook")
    def test_prepare_delegates_to_prepare_hook(self, prepare_hook_mock):
        prepare_hook_mock.return_value = {"ok": True}
        self.assertEqual({"ok": True}, main.prepare({"hello": "world"}))
        prepare_hook_mock.assert_called_once_with({"hello": "world"})
