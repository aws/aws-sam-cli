"""
LazyGroup implementation for Click CLI performance optimization
"""

import importlib

import click
from click import ClickException


class LazyGroup(click.Group):
    def __init__(self, *args, lazy_subcommands=None, **kwargs):
        super().__init__(*args, **kwargs)
        # lazy_subcommands is a map of the form:
        #   {command-name} -> {module-name}.{command-object-name}
        self.lazy_subcommands = lazy_subcommands or {}

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
