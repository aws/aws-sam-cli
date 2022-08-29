import os
import tempfile

from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock

from samcli.commands.exceptions import ConfigException
from samcli.cli.cli_config_file import TomlProvider, configuration_option, configuration_callback, get_ctx_defaults
from samcli.lib.config.samconfig import DEFAULT_ENV


class MockContext:
    def __init__(self, info_name, parent, params=None, command=None, default_map=None):
        self.info_name = info_name
        self.parent = parent
        self.params = params
        self.command = command
        self.default_map = default_map


class TestTomlProvider(TestCase):
    def setUp(self):
        self.toml_provider = TomlProvider()
        self.config_env = "config_env"
        self.parameters = "parameters"
        self.cmd_name = "topic"

    def test_toml_valid_with_section(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword='clarity'\n")
        self.assertEqual(
            TomlProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name]), {"word": "clarity"}
        )

    def test_toml_valid_with_no_version(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("[config_env.topic.parameters]\nword='clarity'\n")
        with self.assertRaises(ConfigException):
            TomlProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name])

    def test_toml_valid_with_invalid_version(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version='abc'\n[config_env.topic.parameters]\nword='clarity'\n")
        with self.assertRaises(ConfigException):
            TomlProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name])

    def test_toml_invalid_empty_dict(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("[topic]\nword=clarity\n")

        self.assertEqual(self.toml_provider(config_dir, self.config_env, [self.cmd_name]), {})

    def test_toml_invalid_file_name(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "mysamconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword='clarity'\n")
        config_path_invalid = Path(config_dir, "samconfig.toml")

        with self.assertRaises(ConfigException):
            self.toml_provider(config_path_invalid, self.config_env, [self.cmd_name])

    def test_toml_invalid_syntax(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword=_clarity'\n")

        with self.assertRaises(ConfigException):
            self.toml_provider(config_path, self.config_env, [self.cmd_name])


class TestCliConfiguration(TestCase):
    def setUp(self):
        self.cmd_name = "test_cmd"
        self.option_name = "test_option"
        # No matter what config-env is passed in, default is chosen.
        self.config_env = "test_config_env"
        self.saved_callback = MagicMock()
        self.provider = MagicMock()
        self.ctx = MagicMock()
        self.param = MagicMock()
        self.value = MagicMock()
        self.config_file = "otherconfig.toml"

    class Dummy:
        pass

    def test_callback_with_valid_config_env(self):
        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)
        self.ctx.parent = mock_context3
        self.ctx.info_name = "test_info"
        self.ctx.params = {}
        setattr(self.ctx, "samconfig_dir", None)
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value=self.value,
        )
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, DEFAULT_ENV]:
            self.assertIn(arg, self.saved_callback.call_args[0])
        self.assertNotIn(self.value, self.saved_callback.call_args[0])

    def test_callback_with_invalid_config_file(self):
        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)
        self.ctx.parent = mock_context3
        self.ctx.info_name = "test_info"
        self.ctx.params = {"config_file": "invalid_config_file"}
        setattr(self.ctx, "samconfig_dir", None)
        with self.assertRaises(ConfigException):
            configuration_callback(
                cmd_name=self.cmd_name,
                option_name=self.option_name,
                saved_callback=self.saved_callback,
                provider=self.provider,
                ctx=self.ctx,
                param=self.param,
                value=self.value,
            )

    def test_callback_with_valid_config_file_path(self):
        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)
        self.ctx.parent = mock_context3
        self.ctx.info_name = "test_info"
        # Create a temporary directory.
        temp_dir = tempfile.mkdtemp()
        # Create a new config file path that is one layer above the temporary directory.
        config_file_path = Path(temp_dir).parent.joinpath(self.config_file)
        with open(config_file_path, "wb"):
            # Set the `samconfig_dir` to be temporary directory that was created.
            setattr(self.ctx, "samconfig_dir", temp_dir)
            # set a relative path for the config file from `samconfig_dir`.
            self.ctx.params = {"config_file": os.path.join("..", self.config_file)}
            configuration_callback(
                cmd_name=self.cmd_name,
                option_name=self.option_name,
                saved_callback=self.saved_callback,
                provider=self.provider,
                ctx=self.ctx,
                param=self.param,
                value=self.value,
            )
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, DEFAULT_ENV]:
            self.assertIn(arg, self.saved_callback.call_args[0])
        self.assertNotIn(self.value, self.saved_callback.call_args[0])

    def test_configuration_option(self):
        toml_provider = TomlProvider()
        click_option = configuration_option(provider=toml_provider)
        clc = click_option(self.Dummy())
        self.assertEqual(clc.__click_params__[0].is_eager, True)
        self.assertEqual(
            clc.__click_params__[0].help,
            "This is a hidden click option whose callback function loads configuration parameters.",
        )
        self.assertEqual(clc.__click_params__[0].hidden, True)
        self.assertEqual(clc.__click_params__[0].expose_value, False)
        self.assertEqual(clc.__click_params__[0].callback.args, (None, None, None, toml_provider))

    def test_get_ctx_defaults_non_nested(self):
        provider = MagicMock()

        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)

        get_ctx_defaults("start-api", provider, mock_context3, "default")

        provider.assert_called_with(None, "default", ["local", "start-api"])

    def test_get_ctx_defaults_nested(self):
        provider = MagicMock()

        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="generate-event", parent=mock_context2)
        mock_context4 = MockContext(info_name="alexa-skills-kit", parent=mock_context3)

        get_ctx_defaults("intent-answer", provider, mock_context4, "default")

        provider.assert_called_with(None, "default", ["local", "generate-event", "alexa-skills-kit", "intent-answer"])
