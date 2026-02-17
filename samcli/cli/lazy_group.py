"""
LazyGroup implementation for Click CLI performance optimization
"""

import importlib

import click
from click import ClickException

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import HighlightNewRowNameModifier, RowDefinition


class LazyGroup(click.Group):
    class CustomFormatterContext(click.Context):
        formatter_class = RootCommandHelpTextFormatter

        def __init__(self, *args, **kwargs):
            if "max_content_width" not in kwargs:
                kwargs["max_content_width"] = 140
            super().__init__(*args, **kwargs)

    context_class = CustomFormatterContext

    def __init__(self, *args, lazy_subcommands=None, new_commands=None, **kwargs):
        # Set context_settings to use our custom formatter
        if "context_settings" not in kwargs:
            kwargs["context_settings"] = {}
        kwargs["context_settings"]["help_option_names"] = ["-h", "--help"]

        super().__init__(*args, **kwargs)
        # lazy_subcommands is a map of the form:
        #   {command-name} -> {module-name}.{command-object-name}
        self.lazy_subcommands = lazy_subcommands or {}
        # new_commands is a set of command names that should be marked as NEW
        self.new_commands = new_commands or set()

    @staticmethod
    def _write_rows_with_spacing(formatter: RootCommandHelpTextFormatter, section_name: str, rows: list):
        """Helper method to write rows with spacing between each row."""
        if rows:
            with formatter.indented_section(name=section_name, extra_indents=1):
                formatter.write_rd([RowDefinition(name="", text="\n")])
                formatter.write_rd(
                    [item for pair in zip(rows, [RowDefinition(name="", text="\n")] * len(rows)) for item in pair][
                        :-1
                    ]  # Remove trailing blank line
                )

    def format_options(self, ctx: click.Context, formatter: RootCommandHelpTextFormatter):  # type: ignore
        """Format options with spacing between each option."""
        opts = [
            RowDefinition(name=rv[0], text=rv[1])
            for param in self.get_params(ctx)
            if (rv := param.get_help_record(ctx)) is not None
        ]

        self._write_rows_with_spacing(formatter, "Options", opts)

        # Call format_commands to show the subcommands
        self.format_commands(ctx, formatter)

    def format_commands(self, ctx: click.Context, formatter: RootCommandHelpTextFormatter):  # type: ignore
        """Format commands with spacing between each command."""
        commands = [
            RowDefinition(
                name=subcommand,
                text=cmd.get_short_help_str(limit=formatter.width),
                extra_row_modifiers=[HighlightNewRowNameModifier()] if subcommand in self.new_commands else [],
            )
            for subcommand in self.list_commands(ctx)
            if (cmd := self.get_command(ctx, subcommand)) is not None and not (hasattr(cmd, "hidden") and cmd.hidden)
        ]

        self._write_rows_with_spacing(formatter, "Commands", commands)

    def list_commands(self, ctx):
        base = super().list_commands(ctx)
        lazy = sorted(self.lazy_subcommands.keys())
        return base + lazy

    def get_command(self, ctx, cmd_name):
        if cmd_name in self.lazy_subcommands:
            return self._lazy_load(cmd_name)
        return super().get_command(ctx, cmd_name)

    def _lazy_load(self, cmd_name):
        # lazily loading a command, first get the module name and attribute name
        import_path = self.lazy_subcommands[cmd_name]
        modname, cmd_object_name = import_path.rsplit(".", 1)
        # do the import
        try:
            mod = importlib.import_module(modname)
        except ImportError as e:
            raise ClickException(f"Failed to load command '{cmd_name}': {str(e)}")
        # get the Command object from that module
        try:
            cmd_object = getattr(mod, cmd_object_name)
        except AttributeError:
            raise ClickException(f"Command '{cmd_name}' not found in module '{modname}'")
        # check the result to make debugging easier
        if not isinstance(cmd_object, click.Command):
            raise ClickException(f"Lazy loading of {import_path} failed by returning a non-command object")
        return cmd_object
