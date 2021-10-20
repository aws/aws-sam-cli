"""Experimental flag"""
import sys
from functools import wraps
from typing import List, Dict
import click

from samcli.cli.global_config import ConfigEntry, GlobalConfig
from samcli.commands._utils.options import parameterized_option

EXPERIMENTAL_PROMPT = """
This feature is currently in beta. Visit the docs page to learn more about the AWS Beta terms https://aws.amazon.com/service-terms/.
Enter Y to proceed with the command, or enter N to cancel:
"""

EXPERIMENTAL_ENV_VAR_PREFIX = "SAM_CLI_BETA_"


class ExperimentalFlag:
    """Data class for storing all experimental related ConfigEntries"""

    All = ConfigEntry("experimentalAll", EXPERIMENTAL_ENV_VAR_PREFIX + "FEATURES")
    Accelerate = ConfigEntry("experimentalAccelerate", EXPERIMENTAL_ENV_VAR_PREFIX + "ACCELERATE")


def is_experimental_enabled(config_entry: ConfigEntry) -> bool:
    """Whether a given experimental flag is enabled or not.
    If experimentalAll is set to True, then it will always return True.

    Parameters
    ----------
    config_entry : ConfigEntry
        Experimental flag ConfigEntry

    Returns
    -------
    bool
        Whether the experimental flag is enabled or not.
    """
    gc = GlobalConfig()
    enabled = gc.get_value(config_entry, False, bool, is_flag=True)
    if not enabled:
        enabled = gc.get_value(ExperimentalFlag.All, False, bool, is_flag=True)
    return enabled


def set_experimental(config_entry: ConfigEntry = ExperimentalFlag.All, enabled: bool = True) -> None:
    """Set the experimental flag to enabled or disabled.

    Parameters
    ----------
    config_entry : ConfigEntry, optional
        Flag to be set, by default ExperimentalFlag.All
    enabled : bool, optional
        Enabled or disabled, by default True
    """
    gc = GlobalConfig()
    gc.set_value(config_entry, enabled, is_flag=True, flush=False)


def get_all_experimental_flags() -> List[ConfigEntry]:
    """
    Returns
    -------
    List[ConfigEntry]
        List all experimental flags in the ExperimentalFlag class.
    """
    return [getattr(ExperimentalFlag, name) for name in dir(ExperimentalFlag) if not name.startswith("__")]


def get_all_experimental_flag_statues() -> Dict[str, bool]:
    """Get statues of all experimental flags in a dictionary.

    Returns
    -------
    Dict[str, bool]
        Dictionary with key as configuration value and value as enabled or disabled.
    """
    return {entry.config_key: is_experimental_enabled(entry) for entry in get_all_experimental_flags()}


def turn_off_all_experimental():
    """Turn off all experimental flags in the ExperimentalFlag class."""
    for entry in get_all_experimental_flags():
        set_experimental(entry, False)


def _experimental_option_callback(ctx, param, enabled: bool):
    """Click parameter callback for --beta-features or --no-beta-features.
    If neither is specified, this function will not be called.
    If --beta-features is set, enabled will be True,
    we should turn on all experimental flags.
    If --no-beta-features is set, enabled will be False,
    we should turn off all experimental flags, overriding existing env vars.
    """
    if enabled:
        set_experimental(ExperimentalFlag.All, True)
    else:
        turn_off_all_experimental()


def experimental_click_option(default: bool):
    return click.option(
        "--beta-features/--no-beta-features",
        default=default,
        required=False,
        is_flag=True,
        expose_value=False,
        callback=_experimental_option_callback,
        help="Should beta features be enabled.",
    )


@parameterized_option
def experimental_option(f, default: bool = False):
    """Decorator for adding --beta-features and --no-beta-features click options to a command."""
    return experimental_click_option(default)(f)


@parameterized_option
def force_experimental_option(f, prompt=EXPERIMENTAL_PROMPT):
    """Decorator for adding --beta-features and --no-beta-features click options to a command.
    If experimental flag env var or --beta-features flag is not specified, this will then
    prompt the user for confirmation.
    The program will exit if confirmation is denied.
    """

    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if not prompt_experimental(prompt=prompt):
                sys.exit(1)
            return func(*args, **kwargs)

        return wrapped_func

    return experimental_click_option(False)(wrap(f))


def prompt_experimental(config_entry: ConfigEntry = ExperimentalFlag.All, prompt=EXPERIMENTAL_PROMPT) -> bool:
    """Prompt the user for experimental features.
    If the corresponding experimental flag is already specified, the prompt will be skipped.
    If confirmation is granted, the corresponding experimental flag env var will be set.

    Parameters
    ----------
    config_entry : ConfigEntry, optional
        Which experimental flag should be set, by default ExperimentalFlag.All
    prompt : [type], optional
        Text to be shown in the prompt, by default EXPERIMENTAL_PROMPT

    Returns
    -------
    bool
        Whether user have accepted the experimental feature.
    """
    if is_experimental_enabled(config_entry):
        return True
    return click.confirm(prompt, default=False)
