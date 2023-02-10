import os
from unittest.mock import MagicMock, call, patch
from unittest import TestCase

from samcli.commands._utils.experimental import (
    _experimental_option_callback,
    disable_all_experimental,
    force_experimental_option,
    get_all_experimental_statues,
    get_all_experimental,
    is_experimental_enabled,
    prompt_experimental,
    set_experimental,
    get_enabled_experimental_flags,
)
from samcli.lib.utils.colors import Colored


class TestExperimental(TestCase):
    def setUp(self):

        gc_patch = patch("samcli.commands._utils.experimental.GlobalConfig")
        self.gc_mock = gc_patch.start()
        self.addCleanup(gc_patch.stop)

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
        self.assertEqual(len(get_all_experimental()), 4)

    def test_get_all_experimental_statues(self):
        self.assertEqual(len(get_all_experimental_statues()), 4)

    def test_get_enabled_experimental_flags(self):
        self.assertEqual(len(get_enabled_experimental_flags()), 4)

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.get_all_experimental")
    def test_disable_all_experimental(self, get_all_experimental_mock, set_experimental_mock):
        flags = [MagicMock(), MagicMock(), MagicMock()]
        get_all_experimental_mock.return_value = flags
        disable_all_experimental()
        set_experimental_mock.assert_has_calls([call(flags[0], False), call(flags[1], False), call(flags[2], False)])

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.disable_all_experimental")
    @patch("samcli.commands._utils.experimental.update_experimental_context")
    def test_experimental_option_callback_true(
        self, update_experimental_context, disable_all_experimental_mock, set_experimental_mock
    ):
        _experimental_option_callback(MagicMock(), MagicMock(), True)
        set_experimental_mock.assert_called_once()
        disable_all_experimental_mock.assert_not_called()
        update_experimental_context.assert_called_once()

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.disable_all_experimental")
    def test_experimental_option_callback_false(self, disable_all_experimental_mock, set_experimental_mock):
        _experimental_option_callback(MagicMock(), MagicMock(), False)
        set_experimental_mock.assert_not_called()
        disable_all_experimental_mock.assert_called_once()

    @patch("samcli.commands._utils.experimental.Context")
    @patch("samcli.commands._utils.experimental.prompt_experimental")
    def test_force_experimental_option_true(self, prompt_experimental_mock, context_mock):
        config_entry = MagicMock()
        prompt = "abc"
        prompt_experimental_mock.return_value = True

        @force_experimental_option("param", config_entry, prompt)
        def func(param=None):
            self.assertEqual(param, 1)

        func(param=1)
        prompt_experimental_mock.assert_called_once_with(config_entry=config_entry, prompt=prompt)

    @patch("samcli.commands._utils.experimental.set_experimental")
    @patch("samcli.commands._utils.experimental.click.confirm")
    @patch("samcli.commands._utils.experimental.is_experimental_enabled")
    @patch("samcli.commands._utils.experimental.update_experimental_context")
    def test_prompt_experimental(self, update_experimental_context, enabled_mock, confirm_mock, set_experimental_mock):
        config_entry = MagicMock()
        prompt = "abc"
        enabled_mock.return_value = False
        confirm_mock.return_value = True
        prompt_experimental(config_entry, prompt)
        set_experimental_mock.assert_called_once_with(config_entry=config_entry, enabled=True)
        enabled_mock.assert_called_once_with(config_entry)
        confirm_mock.assert_called_once_with(Colored().yellow(prompt), default=False)
        update_experimental_context.assert_called_once()
