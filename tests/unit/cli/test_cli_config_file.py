import tempfile

from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch, call

import click

from samcli.cli.cli_config_file import TomlProvider, configuration_option, configuration_callback


class TestTomlProvider(TestCase):
    def setUp(self):
        self.toml_provider = TomlProvider()
        self.cmd_name = "topic"

    def test_toml_valid(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[topic]\nword='clarity'\n")
            toml_file.flush()
            self.assertEqual(self.toml_provider(toml_file.name, self.cmd_name), {"topic": {"word": "clarity"}})

    def test_toml_valid_with_section(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[topic]\nword='clarity'\n")
            toml_file.flush()
            self.assertEqual(TomlProvider(section="topic")(toml_file.name, self.cmd_name), {"word": "clarity"})

    def test_toml_invalid(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[topic]\nword=clarity\n")
            toml_file.flush()
            with self.assertRaises(ValueError):
                self.toml_provider(toml_file.name, self.cmd_name)


class TestCliConfiguration(TestCase):
    def setUp(self):
        self.cmd_name = "test_cmd"
        self.option_name = "test_option"
        self.config_file_name = "test_file"
        self.saved_callback = MagicMock()
        self.provider = MagicMock()
        self.ctx = MagicMock()
        self.param = MagicMock()

    class Dummy:
        pass

    def test_callback_with_valid_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            configuration_callback(
                cmd_name=self.cmd_name,
                option_name=self.option_name,
                config_file_name=toml_file.name,
                saved_callback=self.saved_callback,
                provider=self.provider,
                ctx=self.ctx,
                param=self.param,
                value=toml_file.name,
            )
            self.assertEqual(self.saved_callback.call_count, 1)
            for arg in [self.ctx, self.param, toml_file.name]:
                self.assertIn(arg, self.saved_callback.call_args[0])

    def test_callback_with_invalid_file(self):
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            config_file_name=self.config_file_name,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value="invalid",
        )
        self.assertEqual(self.provider.call_count, 0)

    def test_callback_with_exception(self):
        self.provider = MagicMock(side_effect=Exception)
        with tempfile.NamedTemporaryFile(delete=False) as temp_value:
            with self.assertRaises(click.BadOptionUsage):
                configuration_callback(
                    cmd_name=self.cmd_name,
                    option_name=self.option_name,
                    config_file_name=self.config_file_name,
                    saved_callback=self.saved_callback,
                    provider=self.provider,
                    ctx=self.ctx,
                    param=self.param,
                    value=temp_value.name,
                )
            self.assertEqual(self.provider.call_count, 1)

    def test_configuration_option(self):
        toml_provider = TomlProvider()
        click_option = configuration_option(provider=toml_provider)
        clc = click_option(self.Dummy())
        self.assertEqual(clc.__click_params__[0].is_eager, True)
        self.assertEqual(clc.__click_params__[0].help, "Read configuration from FILE.")
        self.assertEqual(clc.__click_params__[0].expose_value, False)
        self.assertEqual(
            clc.__click_params__[0].callback.args, (None, "--config", "sam-app-config", None, toml_provider)
        )
