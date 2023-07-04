"""Handles JSON schema generation logic"""


import click
import importlib

from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands.build.click_container import ContainerOptions
from samcli.lib.config.samconfig import SamConfig


def retrieve_command_structure(package_name: str) -> dict:
    """Given a SAM CLI package name, retrieve its structure.

    Returns
    -------
    dict
        A dictionary that maps the name of the command to its relevant click options.
    """
    module = importlib.import_module(package_name)
    command_name = package_name.split(".")[-1]  # command name is the last folder
    command = {}

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

    if isinstance(module.cli, click.core.Group):  # command has subcommands (e.g. local invoke)
        for subcommand in module.cli.commands.values():
            params = [
                param
                for param in subcommand.params
                if param.name != None and isinstance(param, click.core.Option)  # exclude None and non-Options
            ]
            formatted_params = {param.name: format_param(param) for param in params}
            command.update({SamConfig._to_key([command_name, subcommand.name]): formatted_params})
    else:
        params = [
            param
            for param in module.cli.params
            if param.name != None and isinstance(param, click.core.Option)  # exclude None and non-Options
        ]
        formatted_params = {param.name: format_param(param) for param in params}
        command.update({command_name: formatted_params})
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
        command_params = [param for param_list in new_command.values() for param in param_list]
        params.update(command_params)
    print(commands)  # DEBUG: note that some params appear
    return schema


if __name__ == "__main__":
    generate_schema()
