import os
import tempfile

from unittest import TestCase
from unittest.mock import MagicMock, patch


from samcli.cli.cli_config_file import (
    TomlProvider,
    configuration_option,
    configuration_callback,
    get_ctx_defaults,
    DEFAULT_CONFIG_FILE_NAME,
)


class MockContext:
    def __init__(self, info_name, parent):
        self.info_name = info_name
        self.parent = parent


class TestTomlProvider(TestCase):
    def setUp(self):
        self.toml_provider = TomlProvider()
        self.config_env = "config_env"
        self.parameters = "parameters"
        self.cmd_name = "topic"

    def test_toml_valid_with_section(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[config_env.topic.parameters]\nword='clarity'\n")
            toml_file.flush()
            self.assertEqual(
                TomlProvider(section=self.parameters)(toml_file.name, self.config_env, self.cmd_name),
                {"word": "clarity"},
            )

    def test_toml_invalid_empty_dict(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[topic]\nword=clarity\n")
            toml_file.flush()
            self.assertEqual(self.toml_provider(toml_file.name, self.config_env, self.cmd_name), {})


class TestCliConfiguration(TestCase):
    def setUp(self):
        self.cmd_name = "test_cmd"
        self.option_name = "test_option"
        self.config_env = "test_config_env"
        self.saved_callback = MagicMock()
        self.provider = MagicMock()
        self.ctx = MagicMock()
        self.param = MagicMock()
        self.value = MagicMock()

    class Dummy:
        pass

    @patch("samcli.cli.cli_config_file.os.path.isfile", return_value=True)
    @patch("samcli.cli.cli_config_file.os.path.join", return_value=MagicMock())
    @patch("samcli.cli.cli_config_file.os.path.abspath", return_value=MagicMock())
    def test_callback_with_valid_config_env(self, mock_os_path_is_file, mock_os_path_join, mock_os_path_abspath):
        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)
        self.ctx.parent = mock_context3
        self.ctx.info_name = "test_info"
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            config_env_name=self.config_env,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value=self.value,
        )
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, self.value]:
            self.assertIn(arg, self.saved_callback.call_args[0])

    @patch("samcli.cli.cli_config_file.os.path.isfile", return_value=False)
    @patch("samcli.cli.cli_config_file.os.path.join", return_value=MagicMock())
    def test_callback_with_config_file_not_file(self, mock_os_isfile, mock_os_path_join):
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            config_env_name=self.config_env,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value=self.value,
        )
        self.assertEqual(self.provider.call_count, 0)
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, self.value]:
            self.assertIn(arg, self.saved_callback.call_args[0])
        self.assertEqual(mock_os_isfile.call_count, 1)
        self.assertEqual(mock_os_path_join.call_count, 1)

    def test_configuration_option(self):
        toml_provider = TomlProvider()
        click_option = configuration_option(provider=toml_provider)
        clc = click_option(self.Dummy())
        self.assertEqual(clc.__click_params__[0].is_eager, True)
        self.assertEqual(clc.__click_params__[0].help, "Read config-env from Configuration File.")
        self.assertEqual(clc.__click_params__[0].hidden, True)
        self.assertEqual(clc.__click_params__[0].expose_value, False)
        self.assertEqual(clc.__click_params__[0].callback.args, (None, "--config-env", "default", None, toml_provider))

    @patch("samcli.cli.cli_config_file.os.path.isfile", return_value=True)
    def test_get_ctx_defaults_non_nested(self, mock_os_file):
        provider = MagicMock()

        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)

        get_ctx_defaults("start-api", provider, mock_context3)

        provider.assert_called_with(os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE_NAME), "default", "local_start_api")

    @patch("samcli.cli.cli_config_file.os.path.isfile", return_value=True)
    def test_get_ctx_defaults_nested(self, mock_os_file):
        provider = MagicMock()

        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="generate-event", parent=mock_context2)
        mock_context4 = MockContext(info_name="alexa-skills-kit", parent=mock_context3)

        get_ctx_defaults("intent-answer", provider, mock_context4)

        provider.assert_called_with(
            os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE_NAME),
            "default",
            "local_generate_event_alexa_skills_kit_intent_answer",
        )
