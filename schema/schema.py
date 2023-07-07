"""Handles JSON schema generation logic"""


import importlib
from typing import Dict, List, Optional, Union

import click

from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES
from samcli.lib.config.samconfig import SamConfig


def format_param(param: click.core.Option) -> Dict[str, Union[Optional[str], List[str]]]:
    """Format a click Option parameter to a dictionary object.

    A parameter object should contain the following information that will be
    necessary for including in the JSON schema:
    * name - The name of the parameter
    * help - The parameter's description (may vary between commands)
    * type - The data type accepted by the parameter
      * type.choices - If there are only a certain number of options allowed,
                       a list of those allowed options
    * default - The default option for that parameter
    """
    formatted_param: Dict[str, Union[Optional[str], List[str]]] = {"name": param.name, "help": param.help}

    # NOTE: Params do not have explicit "string" type; either "text" or "path".
    #       All choice options are from a set of strings.
    if param.type.name in ["text", "path", "choice"]:
        formatted_param["type"] = "string"
    else:
        formatted_param["type"] = param.type.name

    if param.default:
        formatted_param["default"] = str(param.default)

    if param.type.name == "choice" and isinstance(param.type, click.Choice):
        formatted_param["choices"] = list(param.type.choices)

    return formatted_param


def get_params_from_command(cli, main_command_name: str = "") -> Dict[str, dict]:
    """Given a command CLI, return it in a dictionary, pointing to its parameters as dictionary objects."""
    params = [
        param
        for param in cli.params
        if param.name and isinstance(param, click.core.Option)  # exclude None and non-Options
    ]
    cmd_name = SamConfig.to_key([main_command_name, cli.name]) if main_command_name else cli.name
    return {cmd_name: {param.name: format_param(param) for param in params}}


def retrieve_command_structure(package_name: str) -> Dict[str, dict]:
    """Given a SAM CLI package name, retrieve its structure.

    Parameters
    ----------
    package_name: str
        The name of the command package to retrieve.

    Returns
    -------
    dict
        A dictionary that maps the name of the command to its relevant click options.
    """
    module = importlib.import_module(package_name)
    command = {}

    if isinstance(module.cli, click.core.Group):  # command has subcommands (e.g. local invoke)
        for subcommand in module.cli.commands.values():
            command.update(
                get_params_from_command(
                    subcommand,
                    module.__name__.split(".")[-1],  # if Group CLI, get last section of module name for cmd name
                )
            )
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
    schema: dict = {}
    commands = {}
    params = set()  # NOTE(leogama): Currently unused due to some params having different help values
    # TODO: Populate schema with relevant attributes
    for package_name in _SAM_CLI_COMMAND_PACKAGES:
        new_command = retrieve_command_structure(package_name)
        commands.update(new_command)
        for param_list in new_command.values():
            command_params = [param for param in param_list]
        params.update(command_params)
    return schema


if __name__ == "__main__":
    generate_schema()
