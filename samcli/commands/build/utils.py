"""
Utilities for sam build command
"""

import click

from samcli.lib.build.workflow_config import CONFIG


def prompt_user_to_enable_mount_with_write(config: CONFIG, source_dir: str) -> bool:
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
        f"Pass --mount-with-write to `sam build` CLI to avoid this confirmation. "
        f"\nWould you like to enable mounting with write permissions? "
    ):
        return True
    return False
