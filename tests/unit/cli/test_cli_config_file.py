import os
import tempfile
from dataclasses import dataclass

from pathlib import Path
from typing import List, Optional
from unittest import TestCase, skipIf
from unittest.mock import MagicMock, patch

import tomlkit
from click.core import ParameterSource

from samcli.commands.exceptions import ConfigException
from samcli.cli.cli_config_file import (
    ConfigProvider,
    configuration_option,
    configuration_callback,
    get_ctx_defaults,
    save_command_line_args_to_config,
    handle_parse_options,
)
from samcli.lib.config.exceptions import SamConfigFileReadException, SamConfigVersionException
from samcli.lib.config.samconfig import DEFAULT_ENV

from tests.testing_utils import IS_WINDOWS


class MockContext:
    def __init__(self, info_name, parent, params=None, command=None, default_map=None):
        self.info_name = info_name
        self.parent = parent
        self.params = params
        self.command = command
        self.default_map = default_map


class TestConfigProvider(TestCase):
    def setUp(self):
        self.config_provider = ConfigProvider()
        self.config_env = "config_env"
        self.parameters = "parameters"
        self.cmd_name = "topic"

    @patch("samcli.cli.cli_config_file.handle_parse_options")
    def test_toml_valid_with_section(self, mock_handle_parse_options):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword='clarity'\n")
        self.assertEqual(
            ConfigProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name]), {"word": "clarity"}
        )

    def test_toml_valid_with_no_version(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("[config_env.topic.parameters]\nword='clarity'\n")
        with self.assertRaises(SamConfigVersionException):
            ConfigProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name])

    def test_toml_valid_with_invalid_version(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version='abc'\n[config_env.topic.parameters]\nword='clarity'\n")
        with self.assertRaises(SamConfigVersionException):
            ConfigProvider(section=self.parameters)(config_path, self.config_env, [self.cmd_name])

    def test_toml_invalid_empty_dict(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("[topic]\nword=clarity\n")

        with self.assertRaises(SamConfigFileReadException):
            self.config_provider(config_path, self.config_env, [self.cmd_name])

    def test_toml_invalid_file_name(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "mysamconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword='clarity'\n")
        config_path_invalid = Path(config_dir, "samconfig.toml")

        with self.assertRaises(SamConfigFileReadException):
            self.config_provider(config_path_invalid, self.config_env, [self.cmd_name])

    def test_toml_invalid_syntax(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic.parameters]\nword=_clarity'\n")

        with self.assertRaises(SamConfigFileReadException):
            self.config_provider(config_path, self.config_env, [self.cmd_name])


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
        self.config_file_pipe = "config"

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
        self.ctx._parameter_source.__get__ = "COMMANDLINE"
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

    @skipIf(IS_WINDOWS, "os.mkfifo doesn't exist on windows")
    def test_callback_with_config_file_from_pipe(self):
        mock_context1 = MockContext(info_name="sam", parent=None)
        mock_context2 = MockContext(info_name="local", parent=mock_context1)
        mock_context3 = MockContext(info_name="start-api", parent=mock_context2)
        self.ctx.parent = mock_context3
        self.ctx.info_name = "test_info"
        # Create a temporary directory.
        temp_dir = tempfile.mkdtemp()
        # Create a new config file path that is one layer above the temporary directory.
        config_file_pipe_path = Path(temp_dir).parent.joinpath(self.config_file_pipe)
        try:
            # Create a new pipe
            os.mkfifo(config_file_pipe_path)
            # Set the `samconfig_dir` to be temporary directory that was created.
            setattr(self.ctx, "samconfig_dir", temp_dir)
            # set a relative path for the config file from `samconfig_dir`.
            self.ctx.params = {"config_file": os.path.join("..", self.config_file_pipe)}
            configuration_callback(
                cmd_name=self.cmd_name,
                option_name=self.option_name,
                saved_callback=self.saved_callback,
                provider=self.provider,
                ctx=self.ctx,
                param=self.param,
                value=self.value,
            )
        finally:
            os.remove(config_file_pipe_path)
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, DEFAULT_ENV]:
            self.assertIn(arg, self.saved_callback.call_args[0])
        self.assertNotIn(self.value, self.saved_callback.call_args[0])

    def test_configuration_option(self):
        config_provider = ConfigProvider()
        click_option = configuration_option(provider=config_provider)
        clc = click_option(self.Dummy())
        self.assertEqual(clc.__click_params__[0].is_eager, True)
        self.assertEqual(
            clc.__click_params__[0].help,
            "This is a hidden click option whose callback function loads configuration parameters.",
        )
        self.assertEqual(clc.__click_params__[0].hidden, True)
        self.assertEqual(clc.__click_params__[0].expose_value, False)
        self.assertEqual(clc.__click_params__[0].callback.args, (None, None, None, config_provider))

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

    def _setup_mock_samconfig(self):
        mock_flush = MagicMock()
        mock_config_file = {}

        def mock_put_func(cmd_names, section, key, value, env):
            mock_config_file.update({env: {cmd_names[0]: {section: {key: value}}}})

        mock_put = MagicMock()
        mock_put.side_effect = mock_put_func
        return MagicMock(flush=mock_flush, put=mock_put), mock_config_file

    def _setup_context(self, params: dict, parameter_source: dict):
        mock_context = MockContext(info_name="sam", parent=None)
        mock_self_ctx = MagicMock()
        mock_self_ctx.parent = mock_context
        mock_self_ctx.info_name = "command"
        mock_self_ctx.params = params
        mock_self_ctx._parameter_source = parameter_source
        return mock_self_ctx

    def test_dont_save_command_line_args_if_flag_not_set(self):
        mock_samconfig, _ = self._setup_mock_samconfig()

        # Doesn't run if flag is not set
        mock_context = MockContext(info_name="sam", parent=None, params={})

        save_command_line_args_to_config(mock_context, [], "default", mock_samconfig)

        mock_samconfig.flush.assert_not_called()

    def test_save_command_line_args(self):
        mock_samconfig, mock_config_file = self._setup_mock_samconfig()
        self.ctx = self._setup_context(
            params={
                "save_params": True,
                "config_file": "samconfig.toml",  # member of "params_to_exclude", shouldn't be saved
                "some_param": "value",
            },
            parameter_source={
                "save_params": ParameterSource.COMMANDLINE,
                "config_file": ParameterSource.COMMANDLINE,
                "some_param": ParameterSource.COMMANDLINE,
            },
        )

        save_command_line_args_to_config(self.ctx, ["command"], "default", mock_samconfig)

        self.assertIn("default", mock_config_file.keys(), "Environment should be nested in config file")
        self.assertIn("command", mock_config_file["default"].keys(), "Command should be nested in config file")
        self.assertIn(
            "parameters", mock_config_file["default"]["command"].keys(), "Parameters should be nested in config file"
        )

        params = mock_config_file["default"]["command"]["parameters"]

        self.assertNotIn("save_params", params.keys(), "--save-params should not be saved to config")
        self.assertNotIn("config_file", params.keys(), "Excluded member should not be saved to config")
        self.assertIn("some_param", params.keys(), "Param key should be saved to config file")
        self.assertIn("value", params.values(), "Param value should be saved to config file")
        mock_samconfig.flush.assert_called_once()  # everything should be flushed to config file

    def test_dont_save_arguments_not_from_command_line(self):
        mock_samconfig, mock_config_file = self._setup_mock_samconfig()
        self.ctx = self._setup_context(
            params={
                "save_params": True,
                "param_from_commandline": "value",
                "param_not_from_commandline": "other_value",
            },
            parameter_source={
                "save_params": ParameterSource.COMMANDLINE,
                "param_from_commandline": ParameterSource.COMMANDLINE,
                "param_not_from_commandline": ParameterSource.DEFAULT_MAP,
            },
        )

        save_command_line_args_to_config(self.ctx, ["command"], "default", mock_samconfig)

        self.assertIn(
            "parameters",
            mock_config_file.get("default", {}).get("command", {}).keys(),
            "Parameters should be nested in config file",
        )

        params = mock_config_file["default"]["command"]["parameters"]

        self.assertIn("param_from_commandline", params.keys(), "Param from COMMANDLINE should be saved to config file")
        self.assertNotIn(
            "param_not_from_commandline", params.keys(), "Param not passed in via COMMANDLINE should not be saved"
        )

    def test_dont_save_command_line_args_if_value_is_none(self):
        mock_samconfig, mock_config_file = self._setup_mock_samconfig()
        self.ctx = self._setup_context(
            params={
                "save_params": True,
                "some_param": "value",
                "none_param": None,
            },
            parameter_source={
                "save_params": ParameterSource.COMMANDLINE,
                "some_param": ParameterSource.COMMANDLINE,
                "none_param": ParameterSource.COMMANDLINE,
            },
        )

        save_command_line_args_to_config(self.ctx, ["command"], "default", mock_samconfig)

        self.assertIn(
            "parameters",
            mock_config_file.get("default", {}).get("command", {}).keys(),
            "Parameters should be nested in config file",
        )

        params = mock_config_file["default"]["command"]["parameters"]

        self.assertNotIn("save_params", params.keys(), "--save-params should not be saved to config")
        self.assertNotIn("none_param", params.keys(), "Param with None value should not be saved to config")
        self.assertNotIn(None, params.values(), "None value should not be saved to config")


@dataclass
class MockParam:
    multiple: Optional[bool]
    name: Optional[str]


@dataclass
class MockCommand:
    params: List[MockParam]


@dataclass
class MockCommandContext:
    command: MockCommand


class TestHandleParseOptions(TestCase):
    @patch("samcli.cli.cli_config_file.click")
    def test_succeeds_updating_option(self, mock_click):
        mock_param = MockParam(multiple=True, name="debug_port")
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"debug_port": 5858}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"debug_port": [5858]})

    @patch("samcli.cli.cli_config_file.click")
    def test_doesnt_update_not_needed_options(self, mock_click):
        mock_param = MockParam(multiple=True, name="debug_port")
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"debug_port": [5858]}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"debug_port": [5858]})

    @patch("samcli.cli.cli_config_file.click")
    def test_doesnt_update_multiple_false(self, mock_click):
        mock_param = MockParam(multiple=False, name="debug_port")
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"debug_port": 5858}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"debug_port": 5858})

    @patch("samcli.cli.cli_config_file.click")
    def test_doesnt_update_not_found(self, mock_click):
        mock_param = MockParam(multiple=False, name="debug_port")
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"other_option": "hello"}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"other_option": "hello"})

    @patch("samcli.cli.cli_config_file.LOG")
    @patch("samcli.cli.cli_config_file.click")
    def test_handles_invalid_param_name(self, mock_click, mock_log):
        mock_param = None
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"other_option": "hello"}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"other_option": "hello"})
        mock_log.debug.assert_called_once_with("Unable to get parameters from click context.")

    @patch("samcli.cli.cli_config_file.get_options_map")
    @patch("samcli.cli.cli_config_file.LOG")
    @patch("samcli.cli.cli_config_file.click")
    def test_handles_invalid_param_multiple(self, mock_click, mock_log, mock_get_options_map):
        mock_param = None
        mock_command = MockCommand(params=[mock_param])
        mock_context = MockCommandContext(command=mock_command)
        mock_click.get_current_context.return_value = mock_context
        resolved_config = {"other_option": "hello"}
        mock_get_options_map.return_value = {"other_option": "option"}
        handle_parse_options(resolved_config)
        self.assertEqual(resolved_config, {"other_option": "hello"})
        mock_log.debug.assert_called_once_with("Unable to parse option: other_option. Leaving option as inputted")
