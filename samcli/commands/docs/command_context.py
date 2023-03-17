import functools
import os
import sys

from click import echo

from samcli.cli.main import common_options
from samcli.commands.docs.exceptions import InvalidDocsCommandException
from samcli.lib.docs.browser_configuration import BrowserConfiguration, BrowserConfigurationError
from samcli.lib.docs.documentation import Documentation

COMMAND_NAME = "docs"

SUCCESS_MESSAGE = "Documentation page opened in a browser. These other sub-commands are also invokable."
ERROR_MESSAGE = "Failed to open a web browser. Use the following link to navigate to the documentation page: {URL}"


class DocsCommandContext:
    def get_complete_command_paths(self):
        return [self.base_command + " " + command for command in self.all_commands]

    @property
    def command_callback(self):
        impl = CommandImplementation(command=self.sub_command_string)
        return functools.partial(impl.run_command)

    @property
    def all_commands(self):
        return list(Documentation.load().keys())

    @property
    def sub_command_string(self):
        return " ".join(self.sub_commands)

    @property
    def sub_commands(self):
        return self._filter_arguments(sys.argv[2:])

    @property
    def base_command(self):
        return f"sam {COMMAND_NAME}"

    @staticmethod
    def _filter_arguments(commands):
        return list(filter(lambda arg: not arg.startswith("-"), commands))


class CommandImplementation:
    def __init__(self, command: str):
        self.command = command
        self.docs_command = DocsCommandContext()

    @common_options
    def run_command(self):
        """
        Run the necessary logic for the `sam docs` command
        """
        if self.docs_command.sub_commands and self.command not in self.docs_command.all_commands:
            raise InvalidDocsCommandException(
                f"Command not found. Try using one of the following available commands:{os.linesep}"
                f"{os.linesep.join([command for command in self.docs_command.get_complete_command_paths()])}"
            )
        browser = BrowserConfiguration()
        documentation = Documentation(browser=browser, command=self.command)
        try:
            documentation.open_docs()
        except BrowserConfigurationError:
            echo(ERROR_MESSAGE.format(URL=documentation.url))
        else:
            echo(SUCCESS_MESSAGE)

