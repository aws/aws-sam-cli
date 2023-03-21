"""
Utilities for sam build command
"""
import pathlib
from enum import Enum
from typing import List

import click

from samcli.lib.build.workflow_config import CONFIG, get_workflow_config
from samcli.lib.providers.provider import ResourcesToBuildCollector
from samcli.lib.utils.packagetype import IMAGE


class MountMode(Enum):
    """
    Enums that represent mount mode used when build lambda functions/layers inside container
    """

    READ = "READ"
    WRITE = "WRITE"

    @classmethod
    def values(cls) -> List[str]:
        """
        A getter to retrieve the accepted value list for mount mode

        Returns: List[str]
            The accepted mount mode list
        """
        return [e.value for e in cls]


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

    for function in resources_to_build.functions:
        if function.packagetype == IMAGE:
            continue
        code_uri = function.codeuri
        if not code_uri:
            continue
        runtime = function.runtime
        code_dir = str(pathlib.Path(base_dir, code_uri).resolve())
        # get specified_workflow if metadata exists
        metadata = function.metadata
        specified_workflow = metadata.get("BuildMethod", None) if metadata else None
        config = get_workflow_config(runtime, code_dir, base_dir, specified_workflow)
        # at least one function needs mount with write, return with prompting
        if not config.must_mount_with_write_in_container:
            continue
        return prompt(config, code_dir)

    for layer in resources_to_build.layers:
        code_uri = layer.codeuri
        if not code_uri:
            continue
        code_dir = str(pathlib.Path(base_dir, code_uri).resolve())
        specified_workflow = layer.build_method
        config = get_workflow_config(None, code_dir, base_dir, specified_workflow)
        # at least one layer needs mount with write, return with prompting
        if not config.must_mount_with_write_in_container:
            continue
        return prompt(config, code_dir)

    return False


def prompt(config: CONFIG, source_dir: str) -> bool:
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
