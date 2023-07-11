"""Handles JSON schema generation logic"""


import importlib
import json
from enum import Enum
from typing import Any, Dict

import click

from samcli.cli.command import _SAM_CLI_COMMAND_PACKAGES
from samcli.lib.config.samconfig import SamConfig


class SchemaKeys(Enum):
    SCHEMA_FILE_NAME = "schema/samcli.json"
    SCHEMA_DRAFT = "http://json-schema.org/draft-04/schema"
    TITLE = "AWS SAM CLI samconfig schema"
    ENVIRONMENT_REGEX = "^.+$"


def format_param(param: click.core.Option) -> Dict[str, Any]:
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
    formatted_param: Dict[str, Any] = {"title": param.name, "description": param.help}

    # NOTE: Params do not have explicit "string" type; either "text" or "path".
    #       All choice options are from a set of strings.
    param_type = param.type.name.lower()
    if param_type in ["text", "path", "choice", "filename", "directory"]:
        formatted_param["type"] = "string"
    elif param_type == "list":
        formatted_param["type"] = "array"
    else:
        formatted_param["type"] = param_type or "string"

    if param.default:
        formatted_param["default"] = list(param.default) if isinstance(param.default, tuple) else param.default

    if param.type.name == "choice" and isinstance(param.type, click.Choice):
        formatted_param["enum"] = list(param.type.choices)

    return formatted_param


def get_params_from_command(cli) -> Dict[str, dict]:
    """Given a command CLI, return it in a dictionary, pointing to its parameters as dictionary objects."""
    params = [
        param
        for param in cli.params
        if param.name and isinstance(param, click.core.Option)  # exclude None and non-Options
    ]
    return {param.name: format_param(param) for param in params if param.name}


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
            cmd_name = SamConfig.to_key([module.__name__.split(".")[-1], str(subcommand.name)])
            command.update(
                {cmd_name: {"description": subcommand.help, "parameters": get_params_from_command(subcommand)}}
            )
    else:
        cmd_name = SamConfig.to_key([module.__name__.split(".")[-1]])
        command.update({cmd_name: {"description": module.cli.help, "parameters": get_params_from_command(module.cli)}})
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

    # Populate schema with relevant attributes
    schema["$schema"] = SchemaKeys.SCHEMA_DRAFT.value
    schema["title"] = SchemaKeys.TITLE.value
    schema["type"] = "object"
    schema["properties"] = {
        # Version number required for samconfig files to be valid
        "version": {"title": "Config version", "type": "number", "default": 0.1}
    }
    schema["required"] = ["version"]
    schema["additionalProperties"] = False
    # Iterate through packages for command and parameter information
    for package_name in _SAM_CLI_COMMAND_PACKAGES:
        new_command = retrieve_command_structure(package_name)
        commands.update(new_command)
    for cmd_properties in commands.values():
        for param_list in cmd_properties["parameters"].values():
            command_params = [param for param in param_list]
        params.update(command_params)
    # Generate schema for each of the commands
    schema["patternProperties"] = {SchemaKeys.ENVIRONMENT_REGEX.value: {"title": "Environment", "properties": {}}}
    COMMANDS_TO_EXCLUDE = [  # TEMPORARY: for use only while generating piece-by-piece
        "deploy",
        "build",
        "local",
        "validate",
        "package",
        "init",
        "delete",
        "bootstrap",
        "list",
        "traces",
        "sync",
        "publish",
        "pipeline",
        "logs",
        "remote",
    ]
    for cmd_name, cmd_items in commands.items():
        full_cmd_name = cmd_name.split("_")
        formatted_cmd_name = " ".join(full_cmd_name)
        exclude_params = full_cmd_name[0] in COMMANDS_TO_EXCLUDE
        formatted_params_list = (
            "* "
            + "\n* ".join([f"{param['title']}:\n{param['description']}" for param in cmd_items["parameters"].values()])
            if not exclude_params
            else ""
        )
        param_description = f"Available parameters for the {formatted_cmd_name} command:\n{formatted_params_list}"
        schema["patternProperties"][SchemaKeys.ENVIRONMENT_REGEX.value]["properties"].update(
            {
                cmd_name: {
                    "title": f"{' '.join(full_cmd_name).title()} command",
                    "description": cmd_items["description"] or "",
                    "properties": {
                        "parameters": {
                            "title": f"Parameters for the {formatted_cmd_name} command",
                            "description": param_description,
                            "type": "object",
                            "properties": cmd_items["parameters"] if not exclude_params else {},
                        },
                    },
                    "required": ["parameters"],
                }
            }
        )
    return schema


def write_schema():
    """Generate the SAM CLI JSON schema and write it to file."""
    schema = generate_schema()
    with open(SchemaKeys.SCHEMA_FILE_NAME.value, "w+", encoding="utf-8") as outfile:
        json.dump(schema, outfile, indent=2)


if __name__ == "__main__":
    write_schema()
