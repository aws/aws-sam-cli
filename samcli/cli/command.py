"""
Base classes that implement the CLI framework
"""

import importlib
import logging
from collections import OrderedDict

import click
from click import Group

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.root.command_list import SAM_CLI_COMMANDS
from samcli.cli.row_modifiers import HighlightNewRowNameModifier, RowDefinition, ShowcaseRowModifier

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
    "samcli.commands.list.list",
    "samcli.commands.docs",
    "samcli.commands.remote.remote",
    # We intentionally do not expose the `bootstrap` command for now. We might open it up later
    # "samcli.commands.bootstrap",
]


class BaseCommand(Group):
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

    class CustomFormatterContext(click.Context):
        formatter_class = RootCommandHelpTextFormatter

    context_class = CustomFormatterContext

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

    def format_options(self, ctx: click.Context, formatter: RootCommandHelpTextFormatter):  # type: ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.
        # NOTE(sriram-mv): Re-order options so that they come after the commands.
        self.format_commands(ctx, formatter)
        opts = [RowDefinition(name="", text="\n")]
        for param in self.get_params(ctx):
            row = param.get_help_record(ctx)
            if row is not None:
                term, help_text = row
                opts.append(RowDefinition(name=term, text=help_text))

        if opts:
            with formatter.indented_section(name="Options", extra_indents=1):
                formatter.write_rd(opts)

        with formatter.indented_section(name="Examples", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        name="",
                        text="\n",
                    ),
                    RowDefinition(
                        name="Get Started:",
                        text=click.style(f"$ {ctx.command_path} init"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ],
            )

    def format_commands(self, ctx: click.Context, formatter: RootCommandHelpTextFormatter):  # type: ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.
        with formatter.section("Commands"):
            with formatter.section("Learn"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name="docs",
                            text=SAM_CLI_COMMANDS.get("docs", ""),
                            extra_row_modifiers=[HighlightNewRowNameModifier()],
                        )
                    ]
                )

            with formatter.section("Create an App"):
                formatter.write_rd(
                    [
                        RowDefinition(name="init", text=SAM_CLI_COMMANDS.get("init", "")),
                    ],
                )

            with formatter.section("Develop your App"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name="build",
                            text=SAM_CLI_COMMANDS.get("build", ""),
                        ),
                        RowDefinition(
                            name="local",
                            text=SAM_CLI_COMMANDS.get("local", ""),
                        ),
                        RowDefinition(
                            name="validate",
                            text=SAM_CLI_COMMANDS.get("validate", ""),
                        ),
                        RowDefinition(
                            name="sync",
                            text=SAM_CLI_COMMANDS.get("sync", ""),
                            extra_row_modifiers=[HighlightNewRowNameModifier()],
                        ),
                        RowDefinition(
                            name="remote",
                            text=SAM_CLI_COMMANDS.get("remote", ""),
                            extra_row_modifiers=[HighlightNewRowNameModifier()],
                        ),
                    ],
                )

            with formatter.section("Deploy your App"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name="package",
                            text=SAM_CLI_COMMANDS.get("package", ""),
                        ),
                        RowDefinition(
                            name="deploy",
                            text=SAM_CLI_COMMANDS.get("deploy", ""),
                        ),
                    ]
                )

            with formatter.section("Monitor your App"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name="logs",
                            text=SAM_CLI_COMMANDS.get("logs", ""),
                        ),
                        RowDefinition(
                            name="traces",
                            text=SAM_CLI_COMMANDS.get("traces", ""),
                        ),
                    ],
                )

            with formatter.section("And More"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name="list",
                            text=SAM_CLI_COMMANDS.get("list", ""),
                            extra_row_modifiers=[HighlightNewRowNameModifier()],
                        ),
                        RowDefinition(
                            name="delete",
                            text=SAM_CLI_COMMANDS.get("delete", ""),
                        ),
                        RowDefinition(
                            name="pipeline",
                            text=SAM_CLI_COMMANDS.get("pipeline", ""),
                        ),
                        RowDefinition(
                            name="publish",
                            text=SAM_CLI_COMMANDS.get("publish", ""),
                        ),
                    ],
                )

    def list_commands(self, ctx):
        """
        Overrides a method from Click that returns a list of commands available in the CLI.

        :param ctx: Click context
        :return: List of commands available in the CLI
        """
        return list(self._commands.keys())

    def get_command(self, ctx, cmd_name):
        """
        Overrides method from ``Group`` that returns Click CLI object for given command name, if found.

        :param ctx: Click context
        :param cmd_name: Top-level command name
        :return: Click object representing the command
        """
        if cmd_name not in self._commands:
            logger.error("Command %s not available", cmd_name)
            return None

        pkg_name = self._commands[cmd_name]

        mod = None
        try:
            if ctx.obj:
                # NOTE(sriram-mv): Only attempt to import if a relevant `aws sam cli` context has been set.
                # `aws sam cli` context is only set after the `samcli.cli.main:cli` has been executed.
                mod = importlib.import_module(pkg_name)
        except ImportError:
            logger.exception("Command '%s' is not configured correctly. Unable to import '%s'", cmd_name, pkg_name)
            return None

        if mod is not None:
            if not hasattr(mod, "cli"):
                logger.error(
                    "Command %s is not configured correctly. It must expose an function called 'cli'", cmd_name
                )
                return None

        return mod.cli if mod else click.Command(name=cmd_name, short_help=SAM_CLI_COMMANDS.get(cmd_name, ""))
