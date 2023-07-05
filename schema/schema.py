"""Handles JSON schema generation logic"""


import importlib

import click

from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES
from samcli.lib.config.samconfig import SamConfig


def format_param(param: click.core.Option):
    """Format a click Option parameter to a dictionary object."""
    formatted_param = {"name": param.name, "help": param.help}

    if param.type.name in ["text", "path", "choice"]:
        formatted_param["type"] = "string"
    else:
        formatted_param["type"] = param.type.name

    if param.default:
        formatted_param["default"] = param.default

    if param.type.name == "choice":
        formatted_param["choices"] = param.type.choices

    return formatted_param


def retrieve_command_structure(package_name: str) -> dict:
    """Given a SAM CLI package name, retrieve its structure.

    Returns
    -------
    dict
        A dictionary that maps the name of the command to its relevant click options.
    """
    module = importlib.import_module(package_name)
    command = {}

    def get_params_from_command(cli, main_command_name: str = "") -> dict:
        """Given a command CLI, return its parameters."""
        params = [
            param
            for param in cli.params
            if param.name is not None and isinstance(param, click.core.Option)  # exclude None and non-Options
        ]
        cmd_name = SamConfig.to_key([main_command_name, cli.name]) if main_command_name else cli.name
        return {cmd_name: {param.name: format_param(param) for param in params}}

    if isinstance(module.cli, click.core.Group):  # command has subcommands (e.g. local invoke)
        for subcommand in module.cli.commands.values():
            command.update(get_params_from_command(subcommand))
    else:
        command.update(get_params_from_command(module.cli))
    return command


def generate_schema() -> dict:
    """Generate a JSON schema for all SAM CLI commands.

    Returns
    -------
    dict
        A dictionary representation of the JSON schema.
    """
    schema = {}
    commands = {}
    params = set()  # NOTE(leogama): Currently unused due to some params having different help values
    # TODO: Populate schema with relevant attributes
    for package_name in _SAM_CLI_COMMAND_PACKAGES:
        new_command = retrieve_command_structure(package_name)
        commands.update(new_command)
        for param_list in new_command.values():
            command_params = [param for param in param_list]
        params.update(command_params)
    print(commands)  # DEBUG: note that some params appear multiple times due to slight differences
    return schema


if __name__ == "__main__":
    generate_schema()
