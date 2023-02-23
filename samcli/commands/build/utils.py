"""
Utilities for sam build command
"""
import pathlib

import click

from samcli.lib.build.workflow_config import CONFIG, get_workflow_config
from samcli.lib.providers.provider import ResourcesToBuildCollector


def prompt_user_to_enable_mount_with_write_if_needed(
    resources_to_build: ResourcesToBuildCollector,
    base_dir: str,
) -> bool:
    """
    First check if mounting with write permissions is needed for building inside container or not. If it is needed, then
    prompt user to choose if enables mounting with write permissions or not.

    Parameters
    ----------
    resources_to_build:
        Resource to build inside container

    base_dir : str
        Path to the base directory

    Returns
    -------
    bool
        True, if user enabled mounting with write permissions.
    """

    functions = resources_to_build.functions
    layers = resources_to_build.layers
    runtime = None
    specified_workflow = None
    code_uri = None

    if len(functions) > 0:
        function = functions[0]
        runtime = function.runtime
        code_uri = function.codeuri
        # get specified_workflow if metadata exists
        metadata = function.metadata
        specified_workflow = metadata.get("BuildMethod", None) if metadata else None
    elif len(layers) > 0:
        layer = layers[0]
        specified_workflow = layer.build_method
        code_uri = layer.codeuri

    if code_uri:
        code_dir = str(pathlib.Path(base_dir, code_uri).resolve())
        config = get_workflow_config(runtime, code_dir, base_dir, specified_workflow)
        # prompt if mount with write is needed
        if config.must_mount_with_write_in_container:
            return _prompt(config, code_dir)

    return False


def _prompt(config: CONFIG, source_dir: str) -> bool:
    """
    Prompt user to choose if enables mounting with write permissions or not when building lambda functions/layers

    Parameters
    ----------
    config: namedtuple(Capability)
        Config specifying the particular build workflow

    source_dir : str
        Path to the function source code

    Returns
    -------
    bool
        True, if user enabled mounting with write permissions.
    """
    if click.confirm(
        f"\nBuilding functions with {config.language} inside containers needs "
        f"mounting with write permissions to the source code directory {source_dir}. "
        f"Some files in this directory may be changed or added by the build process. "
        f"Pass `--mount-with WRITE` to `sam build` CLI to avoid this confirmation. "
        f"\nWould you like to enable mounting with write permissions? "
    ):
        return True
    return False
