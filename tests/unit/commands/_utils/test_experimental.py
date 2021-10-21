import os
from unittest.mock import MagicMock, call, patch
from unittest import TestCase
from samcli.cli.global_config import ConfigEntry, DefaultEntry, GlobalConfig
from pathlib import Path

from samcli.commands._utils.experimental import (
    _experimental_option_callback,
    disable_all_experimental,
    experimental,
    force_experimental_option,
    get_all_experimental_statues,
    get_all_experimental,
    is_experimental_enabled,
    prompt_experimental,
    set_experimental,
)


class TestGlobalConfig(TestCase):
    def setUp(self):

        gc_patch = patch("samcli.commands._utils.experimental.GlobalConfig")
        self.gc_mock = gc_patch.start()
        self.addCleanup(gc_patch.stop)

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
        pass

    def test_is_experimental_enabled(self):
        config_entry = MagicMock()
        self.gc_mock.return_value.get_value.side_effect = [False, True]
        result = is_experimental_enabled(config_entry)
        self.assertTrue(result)

    def test_is_experimental_enabled_all(self):
        config_entry = MagicMock()
        self.gc_mock.return_value.get_value.side_effect = [True, False]
        result = is_experimental_enabled(config_entry)
        self.assertTrue(result)

    def test_is_experimental_enabled_false(self):
        config_entry = MagicMock()
        self.gc_mock.return_value.get_value.side_effect = [False, False]
        result = is_experimental_enabled(config_entry)
        self.assertFalse(result)

    def test_set_experimental(self):
        config_entry = MagicMock()
        set_experimental(config_entry, False)
        self.gc_mock.return_value.set_value.assert_called_once_with(config_entry, False, is_flag=True, flush=False)

    def test_get_all_experimental(self):
        self.assertEqual(len(get_all_experimental()), 2)

    def test_get_all_experimental_statues(self):
        self.assertEqual(len(get_all_experimental_statues()), 2)

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.get_all_experimental")
    def test_disable_all_experimental(self, get_all_experimental_mock, set_experimental_mock):
        flags = [MagicMock(), MagicMock(), MagicMock()]
        get_all_experimental_mock.return_value = flags
        disable_all_experimental()
        set_experimental_mock.assert_has_calls([call(flags[0], False), call(flags[1], False), call(flags[2], False)])

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.disable_all_experimental")
    def test_experimental_option_callback_true(self, disable_all_experimental_mock, set_experimental_mock):
        _experimental_option_callback(MagicMock(), MagicMock(), True)
        set_experimental_mock.assert_called_once()
        disable_all_experimental_mock.assert_not_called()

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.disable_all_experimental")
    def test_experimental_option_callback_false(self, disable_all_experimental_mock, set_experimental_mock):
        _experimental_option_callback(MagicMock(), MagicMock(), False)
        set_experimental_mock.assert_not_called()
        disable_all_experimental_mock.assert_called_once()

    @patch("samcli.commands._utils.experimental.click.option")
    def test_experimental_flag(self, option_mock):
        pass

    @patch("samcli.commands._utils.experimental.prompt_experimental")
    def test_force_experimental_option_true(self, prompt_experimental_mock):
        config_entry = MagicMock()
        prompt = "abc"
        prompt_experimental_mock.return_value = True

        @force_experimental_option("param", config_entry, prompt)
        def func(param=None):
            self.assertEqual(param, 1)

        func(param=1)
        prompt_experimental_mock.assert_called_once_with(config_entry=config_entry, prompt=prompt)

    @patch("samcli.commands._utils.experimental.click.confirm")
    @patch("samcli.commands._utils.experimental.is_experimental_enabled")
    def test_prompt_experimental(self, enabled_mock, confirm_mock):
        config_entry = MagicMock()
        prompt = "abc"
        enabled_mock.return_value = False
        prompt_experimental(config_entry, prompt)
        enabled_mock.assert_called_once_with(config_entry)
        confirm_mock.assert_called_once_with(prompt, default=False)
