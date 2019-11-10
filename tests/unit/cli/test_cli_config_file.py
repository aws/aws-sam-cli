import os
import tempfile

from unittest import TestCase
from unittest.mock import MagicMock, patch


from samcli.cli.cli_config_file import TomlProvider, configuration_option, configuration_callback


class TestTomlProvider(TestCase):
    def setUp(self):
        self.toml_provider = TomlProvider()
        self.identifier = "identifier"
        self.parameters = "parameters"
        self.cmd_name = "topic"

    def test_toml_valid_with_section(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[identifier.topic.parameters]\nword='clarity'\n")
            toml_file.flush()
            self.assertEqual(
                TomlProvider(cmd=self.cmd_name, section=self.parameters)(
                    toml_file.name, self.identifier, self.cmd_name
                ),
                {"word": "clarity"},
            )

    def test_toml_invalid(self):
        with tempfile.NamedTemporaryFile(delete=False) as toml_file:
            toml_file.write(b"[topic]\nword=clarity\n")
            toml_file.flush()
            with self.assertRaises(ValueError):
                self.toml_provider(toml_file.name, self.identifier, self.cmd_name)


class TestCliConfiguration(TestCase):
    def setUp(self):
        self.cmd_name = "test_cmd"
        self.option_name = "test_option"
        self.identifier_name = "test_identifier"
        self.custom_identifier = "custom"
        self.saved_callback = MagicMock()
        self.provider = MagicMock()
        self.ctx = MagicMock()
        self.param = MagicMock()

    class Dummy:
        pass

    def test_callback_with_valid_identifier(self):
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            identifier_name=self.identifier_name,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value=self.custom_identifier,
        )
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, self.custom_identifier]:
            self.assertIn(arg, self.saved_callback.call_args[0])

    def test_callback_with_invalid_identifier(self):
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            identifier_name=self.identifier_name,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value="invalid",
        )
        self.assertEqual(self.provider.call_count, 0)

    @patch("samcli.cli.cli_config_file.os.path.isfile", return_value=False)
    def test_callback_with_config_file_not_file(self, mock_os_isfile):
        configuration_callback(
            cmd_name=self.cmd_name,
            option_name=self.option_name,
            identifier_name=self.identifier_name,
            saved_callback=self.saved_callback,
            provider=self.provider,
            ctx=self.ctx,
            param=self.param,
            value=self.custom_identifier,
        )
        self.assertEqual(self.provider.call_count, 0)
        self.assertEqual(self.saved_callback.call_count, 1)
        for arg in [self.ctx, self.param, self.custom_identifier]:
            self.assertIn(arg, self.saved_callback.call_args[0])

    @patch("samcli.cli.cli_config_file.os.path.isfile")
    def test_callback_with_env_variable_set(self, mock_os_isfile):
        with patch.dict(os.environ, {"SAM_CONFIG": "~/sam-configurations/sam-config"}):
            configuration_callback(
                cmd_name=self.cmd_name,
                option_name=self.option_name,
                identifier_name=self.identifier_name,
                saved_callback=self.saved_callback,
                provider=self.provider,
                ctx=self.ctx,
                param=self.param,
                value=self.custom_identifier,
            )
            self.assertEqual(self.provider.call_count, 1)
            self.provider.assert_called_with("~/sam-configurations/sam-config", self.custom_identifier, self.cmd_name)

    def test_configuration_option(self):
        toml_provider = TomlProvider()
        click_option = configuration_option(provider=toml_provider)
        clc = click_option(self.Dummy())
        self.assertEqual(clc.__click_params__[0].is_eager, True)
        self.assertEqual(clc.__click_params__[0].help, "Read identifier from Configuration File.")
        self.assertEqual(clc.__click_params__[0].expose_value, False)
        self.assertEqual(clc.__click_params__[0].callback.args, (None, "--identifier", "default", None, toml_provider))
