from unittest import TestCase
from unittest.mock import patch, Mock, PropertyMock

from parameterized import parameterized

from samcli.commands.docs.command_context import (
    DocsCommandContext,
    ERROR_MESSAGE,
    SUCCESS_MESSAGE,
    CommandImplementation,
)
from samcli.commands.docs.exceptions import InvalidDocsCommandException
from samcli.lib.docs.browser_configuration import BrowserConfigurationError

SUPPORTED_COMMANDS = [
    "config",
    "build",
    "local",
    "local invoke",
    "local start-api",
    "local start-lambda",
    "list",
    "list stack-outputs",
    "list endpoints",
    "list resources",
    "deploy",
    "remote invoke",
    "package",
    "delete",
    "sync",
    "publish",
    "validate",
    "init",
    "logs",
    "traces",
]


class TestDocsCommandContext(TestCase):
    @patch("samcli.commands.docs.command_context.sys.argv", ["sam", "docs", "local", "invoke"])
    def test_properties(self) -> None:
        docs_command_context = DocsCommandContext()
        self.assertEqual(docs_command_context.base_command, "sam docs")
        self.assertEqual(docs_command_context.sub_commands, ["local", "invoke"])
        self.assertEqual(docs_command_context.sub_command_string, "local invoke")
        self.assertEqual(docs_command_context.all_commands, SUPPORTED_COMMANDS)

    def test_get_complete_command_paths(self):
        docs_command_context = DocsCommandContext()
        with patch(
            "samcli.commands.docs.command_context.DocsCommandContext.all_commands", new_callable=PropertyMock
        ) as mock_all_commands:
            mock_all_commands.return_value = ["config", "build", "local invoke"]
            command_paths = docs_command_context.get_complete_command_paths()
        self.assertEqual(command_paths, ["sam docs config", "sam docs build", "sam docs local invoke"])

    @parameterized.expand(
        [
            (["local", "invoke", "--help"], ["local", "invoke"]),
            (["local", "invoke", "-h"], ["local", "invoke"]),
            (["build", "--random-args"], ["build"]),
        ]
    )
    def test_filter_arguments(self, commands, expected):
        output = DocsCommandContext._filter_arguments(commands)
        self.assertEqual(output, expected)


class TestCommandImplementation(TestCase):
    @patch("samcli.commands.docs.command_context.echo")
    @patch("samcli.commands.docs.command_context.Documentation.open_docs")
    def test_run_command(self, mock_open_docs, mock_echo):
        command_implementation = CommandImplementation(command="build")
        command_implementation.run_command()
        mock_open_docs.assert_called_once()
        mock_echo.assert_called_once_with(SUCCESS_MESSAGE)

    @patch("samcli.commands.docs.command_context.echo")
    @patch("samcli.commands.docs.command_context.Documentation.open_docs")
    def test_run_command_invalid_command(self, mock_open_docs, mock_echo):
        with patch(
            "samcli.commands.docs.command_context.DocsCommandContext.sub_commands", new_callable=PropertyMock
        ) as mock_sub_commands:
            with self.assertRaises(InvalidDocsCommandException):
                mock_sub_commands.return_value = True
                command_implementation = CommandImplementation(command="not-a-command")
                command_implementation.run_command()
        mock_open_docs.assert_not_called()
        mock_echo.assert_not_called()

    @patch("samcli.commands.docs.command_context.echo")
    @patch("samcli.commands.docs.command_context.Documentation")
    @patch("samcli.commands.docs.command_context.BrowserConfiguration")
    def test_run_command_no_browser(self, mock_browser_config, mock_documentation, mock_echo):
        mock_browser = Mock()
        mock_documentation_object = Mock()
        mock_documentation_object.open_docs.side_effect = BrowserConfigurationError
        mock_documentation_object.url = "some-url"
        mock_documentation_object.sub_commands = []
        mock_browser_config.return_value = mock_browser
        mock_documentation.return_value = mock_documentation_object
        command_implementation = CommandImplementation(command="build")
        command_implementation.docs_command = Mock()
        command_implementation.docs_command.sub_commands = []
        command_implementation.run_command()
        mock_echo.assert_called_once_with(ERROR_MESSAGE.format(URL="some-url"), err=True)
