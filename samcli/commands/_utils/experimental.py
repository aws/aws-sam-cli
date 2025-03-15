"""Experimental flag"""

import logging
import sys
from dataclasses import dataclass
from functools import wraps
from typing import Dict, List, Optional

import click

from samcli.cli.context import Context
from samcli.cli.global_config import ConfigEntry, GlobalConfig
from samcli.commands._utils.parameterized_option import parameterized_option
from samcli.lib.utils.colors import Colored, Colors

LOG = logging.getLogger(__name__)

EXPERIMENTAL_PROMPT = """
This feature is currently in beta.
Visit the docs page to learn more about the AWS Beta terms https://aws.amazon.com/service-terms/.
Enter Y to proceed with the command, or enter N to cancel:
"""

EXPERIMENTAL_WARNING = """
Experimental features are enabled for this session.
Visit the docs page to learn more about the AWS Beta terms https://aws.amazon.com/service-terms/.
"""

EXPERIMENTAL_ENV_VAR_PREFIX = "SAM_CLI_BETA_"


@dataclass(frozen=True, eq=True)
class ExperimentalEntry(ConfigEntry):
    """Child data class of ConfigEntry that enforces
    config_key and env_var_key to be not None"""

    config_key: str
    env_var_key: str
    persistent: bool = False


class ExperimentalFlag:
    """Class for storing all experimental related ConfigEntries"""

    All = ExperimentalEntry("experimentalAll", EXPERIMENTAL_ENV_VAR_PREFIX + "FEATURES")
    BuildPerformance = ExperimentalEntry(
        "experimentalBuildPerformance", EXPERIMENTAL_ENV_VAR_PREFIX + "BUILD_PERFORMANCE"
    )
    PackagePerformance = ExperimentalEntry(
        "experimentalPackagePerformance", EXPERIMENTAL_ENV_VAR_PREFIX + "PACKAGE_PERFORMANCE"
    )
    IaCsSupport = {
        "terraform": ExperimentalEntry(
            "experimentalTerraformSupport", EXPERIMENTAL_ENV_VAR_PREFIX + "TERRAFORM_SUPPORT"
        )
    }
    RustCargoLambda = ExperimentalEntry("experimentalCargoLambda", EXPERIMENTAL_ENV_VAR_PREFIX + "RUST_CARGO_LAMBDA")


def is_experimental_enabled(config_entry: ExperimentalEntry) -> bool:
    """Whether a given experimental flag is enabled or not.
    If experimentalAll is set to True, then it will always return True.

    Parameters
    ----------
    config_entry : ExperimentalEntry
        Experimental flag ExperimentalEntry

    Returns
    -------
    bool
        Whether the experimental flag is enabled or not.
    """
    gc = GlobalConfig()
    enabled = gc.get_value(config_entry, default=False, value_type=bool, is_flag=True)
    if not enabled:
        enabled = gc.get_value(ExperimentalFlag.All, default=False, value_type=bool, is_flag=True)
    return enabled


def set_experimental(config_entry: ExperimentalEntry = ExperimentalFlag.All, enabled: bool = True) -> None:
    """Set the experimental flag to enabled or disabled.

    Parameters
    ----------
    config_entry : ExperimentalEntry, optional
        Flag to be set, by default ExperimentalFlag.All
    enabled : bool, optional
        Enabled or disabled, by default True
    """
    gc = GlobalConfig()
    gc.set_value(config_entry, enabled, is_flag=True, flush=False)


def get_all_experimental() -> List[ExperimentalEntry]:
    """
    Returns
    -------
    List[ExperimentalEntry]
        List all experimental flags in the ExperimentalFlag class.
    """
    all_experimental_flags = []
    for name in dir(ExperimentalFlag):
        if name.startswith("__"):
            continue
        value = getattr(ExperimentalFlag, name)
        if isinstance(value, ExperimentalEntry):
            all_experimental_flags.append(value)
        elif isinstance(value, dict):
            all_experimental_flags += value.values()
    return all_experimental_flags


def get_all_experimental_env_vars() -> List[str]:
    """
    Returns
    -------
    List[str]
        List all env var names of experimental flags
    """
    flags = get_all_experimental()
    return [flag.env_var_key for flag in flags]


def get_all_experimental_statues() -> Dict[str, bool]:
    """Get statues of all experimental flags in a dictionary.

    Returns
    -------
    Dict[str, bool]
        Dictionary with key as configuration value and value as enabled or disabled.
    """
    return {entry.config_key: is_experimental_enabled(entry) for entry in get_all_experimental() if entry.config_key}


def get_enabled_experimental_flags() -> List[str]:
    """
    Returns a list of string, which contains enabled experimental flags for current session

    Returns
    -------
    List[str]
        List of strings which contains all enabled experimental flag names
    """
    enabled_experimentals = []
    for experimental_key, status in get_all_experimental_statues().items():
        if status:
            enabled_experimentals.append(experimental_key)
    return enabled_experimentals


def disable_all_experimental():
    """Turn off all experimental flags in the ExperimentalFlag class."""
    for entry in get_all_experimental():
        set_experimental(entry, False)


def update_experimental_context(show_warning=True):
    """Set experimental for the current click context.

    Parameters
    ----------
    show_warning : bool, optional
        Should warning be shown, by default True
    """
    if not Context.get_current_context().experimental:
        Context.get_current_context().experimental = True
        if show_warning:
            LOG.warning(Colored().color_log(EXPERIMENTAL_WARNING, color=Colors.WARNING), extra=dict(markup=True))


def _experimental_option_callback(ctx, param, enabled: Optional[bool]):
    """Click parameter callback for --beta-features or --no-beta-features.
    If neither is specified, enabled will be None.
    If --beta-features is set, enabled will be True,
    we should turn on all experimental flags.
    If --no-beta-features is set, enabled will be False,
    we should turn off all experimental flags, overriding existing env vars.
    """
    if enabled is None:
        return

    if enabled:
        set_experimental(ExperimentalFlag.All, True)
        update_experimental_context()
    else:
        disable_all_experimental()


def experimental_click_option(default: Optional[bool]):
    return click.option(
        "--beta-features/--no-beta-features",
        default=default,
        required=False,
        is_flag=True,
        expose_value=False,
        callback=_experimental_option_callback,
        help="Enable/Disable beta features.",
    )


@parameterized_option
def experimental(f, default: Optional[bool] = None):
    """Decorator for adding --beta-features and --no-beta-features click options to a command."""
    return experimental_click_option(default)(f)


@parameterized_option
def force_experimental(
    f, config_entry: ExperimentalEntry = ExperimentalFlag.All, prompt=EXPERIMENTAL_PROMPT, default=None
):
    """Decorator for adding --beta-features and --no-beta-features click options to a command.
    If experimental flag env var or --beta-features flag is not specified, this will then
    prompt the user for confirmation.
    The program will exit if confirmation is denied.
    """

    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if not prompt_experimental(config_entry=config_entry, prompt=prompt):
                sys.exit(1)
            return func(*args, **kwargs)

        return wrapped_func

    return experimental_click_option(default)(wrap(f))


@parameterized_option
def force_experimental_option(
    f, option: str, config_entry: ExperimentalEntry = ExperimentalFlag.All, prompt=EXPERIMENTAL_PROMPT
):
    """Decorator for making a specific option to be experimental.
    A prompt will be shown if experimental is not enabled and the option is specified.
    """

    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if kwargs[option]:
                if not prompt_experimental(config_entry=config_entry, prompt=prompt):
                    sys.exit(1)
            return func(*args, **kwargs)

        return wrapped_func

    return wrap(f)


def prompt_experimental(
    config_entry: ExperimentalEntry = ExperimentalFlag.All, prompt: str = EXPERIMENTAL_PROMPT
) -> bool:
    """Prompt the user for experimental features.
    If the corresponding experimental flag is already specified, the prompt will be skipped.
    If confirmation is granted, the corresponding experimental flag env var will be set.

    Parameters
    ----------
    config_entry : ExperimentalEntry, optional
        Which experimental flag should be set, by default ExperimentalFlag.All
    prompt : str, optional
        Text to be shown in the prompt, by default EXPERIMENTAL_PROMPT

    Returns
    -------
    bool
        Whether user have accepted the experimental feature.
    """
    if is_experimental_enabled(config_entry):
        update_experimental_context()
        return True
    confirmed = click.confirm(Colored().yellow(prompt), default=False)
    if confirmed:
        set_experimental(config_entry=config_entry, enabled=True)
        update_experimental_context()
    return confirmed
