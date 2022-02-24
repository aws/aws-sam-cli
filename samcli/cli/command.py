"""
Base classes that implement the CLI framework
"""

import logging
import importlib
from collections import OrderedDict

import click

logger = logging.getLogger(__name__)

# Commands that are bundled with the CLI by default in app life-cycle order.

_SAM_CLI_COMMAND_PACKAGES = [
    "samcli.commands.init",
    "samcli.commands.validate.validate",
    "samcli.commands.build",
    "samcli.commands.local.local",
    "samcli.commands.package",
    "samcli.commands.deploy",
    "samcli.commands.delete",
    "samcli.commands.logs",
    "samcli.commands.publish",
    "samcli.commands.traces",
    "samcli.commands.sync",
    "samcli.commands.pipeline.pipeline",
    # We intentionally do not expose the `bootstrap` command for now. We might open it up later
    # "samcli.commands.bootstrap",
]


class BaseCommand(click.MultiCommand):
    """
    Dynamically loads commands. It takes a list of names of Python packages representing the commands, loads
    these packages, and initializes them as Click commands. If a command "hello" is available in a Python package
    "foo.bar.hello", then this package name is passed to this class to load the command. This allows commands
    to be written as standalone packages that are dynamically initialized by the CLI.

    Each command, along with any subcommands, is implemented using Click annotations. When the command is loaded
    dynamically, this class expects the Click object to be exposed through an attribute called ``cli``. If the
    attribute is not present, or is not a Click object, then an exception will be raised.

    For example: if "foo.bar.hello" is the package where "hello" command is implemented, then
    "/foo/bar/hello/__init__.py" file is expected to contain a Click object called ``cli``.

    The command package is dynamically loaded using Python's standard ``importlib`` library. Therefore package names
    can be specified using the standard Python's dot notation such as "foo.bar.hello".

    By convention, the name of last module in the package's name is the command's name. ie. A package of "foo.bar.baz"
    will produce a command name "baz".
    """

    def __init__(self, *args, cmd_packages=None, **kwargs):
        """
        Initializes the class, optionally with a list of available commands

        :param cmd_packages: List of Python packages names of CLI commands
        :param args: Other Arguments passed to super class
        :param kwargs: Other Arguments passed to super class
        """
        # alias -h to --help for all commands
        kwargs["context_settings"] = dict(help_option_names=["-h", "--help"])
        super().__init__(*args, **kwargs)

        if not cmd_packages:
            cmd_packages = _SAM_CLI_COMMAND_PACKAGES

        self._commands = {}
        self._commands = BaseCommand._set_commands(cmd_packages)

    @staticmethod
    def _set_commands(package_names):
        """
        Extract the command name from package name. Last part of the module path is the command
        ie. if path is foo.bar.baz, then "baz" is the command name.

        :param package_names: List of package names
        :return: Dictionary with command name as key and the package name as value.
        """

        commands = OrderedDict()

        for pkg_name in package_names:
            cmd_name = pkg_name.split(".")[-1]
            commands[cmd_name] = pkg_name

        return commands

    def list_commands(self, ctx):
        """
        Overrides a method from Click that returns a list of commands available in the CLI.

        :param ctx: Click context
        :return: List of commands available in the CLI
        """
        return list(self._commands.keys())

    def get_command(self, ctx, cmd_name):
        """
        Overrides method from ``click.MultiCommand`` that returns Click CLI object for given command name, if found.

        :param ctx: Click context
        :param cmd_name: Top-level command name
        :return: Click object representing the command
        """
        if cmd_name not in self._commands:
            logger.error("Command %s not available", cmd_name)
            return None

        pkg_name = self._commands[cmd_name]

        try:
            mod = importlib.import_module(pkg_name)
        except ImportError:
            logger.exception("Command '%s' is not configured correctly. Unable to import '%s'", cmd_name, pkg_name)
            return None

        if not hasattr(mod, "cli"):
            logger.error("Command %s is not configured correctly. It must expose an function called 'cli'", cmd_name)
            return None

        return mod.cli
