"""Experimental flag"""
import sys
from functools import wraps
from typing import List, Dict
import click

from samcli.cli.global_config import ConfigEntry, GlobalConfig
from samcli.commands._utils.options import parameterized_option

EXPERIMENTAL_PROMPT = """
This feature is currently in beta. Visit the docs page to learn more about the AWS Beta terms https://aws.amazon.com/service-terms/.
To proceed with the command enter Y, or enter anything else to cancel:
"""

EXPERIMENTAL_ENV_VAR_PREFIX = "SAM_CLI_BETA_"


class ExperimentalFlag:
    All = ConfigEntry("experimentalAll", EXPERIMENTAL_ENV_VAR_PREFIX + "FEATURES")
    Accelerate = ConfigEntry("experimentalAccelerate", EXPERIMENTAL_ENV_VAR_PREFIX + "ACCELERATE")


def is_experimental_enabled(config_entry: ConfigEntry) -> bool:
    gc = GlobalConfig()
    enabled = gc.get_value(config_entry, False, bool, is_flag=True)
    if not enabled:
        enabled = gc.get_value(ExperimentalFlag.All, False, bool, is_flag=True)
    return enabled


def set_experimental(config_entry: ConfigEntry = ExperimentalFlag.All, enabled: bool = True) -> None:
    gc = GlobalConfig()
    gc.set_value(config_entry, enabled, is_flag=True, flush=False)


def get_all_experimental_flags() -> List[ConfigEntry]:
    return [getattr(ExperimentalFlag, name) for name in dir(ExperimentalFlag) if not name.startswith("__")]


def get_all_experimental_flag_statues() -> Dict[str, bool]:
    return {entry.config_key: is_experimental_enabled(entry) for entry in get_all_experimental_flags()}


def turn_off_all_experimental():
    for entry in get_all_experimental_flags():
        set_experimental(entry, False)


def _experimental_option_callback(ctx, param, enabled: bool):
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
    return experimental_click_option(default)(f)


@parameterized_option
def force_experimental_option(f, prompt=EXPERIMENTAL_PROMPT):
    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if not prompt_experimental(prompt=prompt):
                sys.exit(1)
            return_value = func(*args, **kwargs)
            return return_value

        return wrapped_func

    return experimental_click_option(False)(wrap(f))


def prompt_experimental(config_entry: ConfigEntry = ExperimentalFlag.All, prompt=EXPERIMENTAL_PROMPT):
    if is_experimental_enabled(config_entry):
        return True
    return click.confirm(prompt, default=False)
