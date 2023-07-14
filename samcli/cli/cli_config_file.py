"""
CLI configuration decorator to use TOML configuration files for click commands.
"""

# This section contains code copied and modified from
# [click_config_file](https://github.com/phha/click_config_file/blob/master/click_config_file.py)
# SPDX-License-Identifier: MIT

import functools
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import click
from click.core import ParameterSource

from samcli.cli.context import get_cmd_names
from samcli.commands.exceptions import ConfigException
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME, DEFAULT_ENV, SamConfig

__all__ = ("ConfigProvider", "configuration_option", "get_ctx_defaults")

LOG = logging.getLogger(__name__)


class ConfigProvider:
    """
    A parser for sam configuration files
    """

    def __init__(self, section=None, cmd_names=None):
        """
        The constructor for ConfigProvider class

        Parameters
        ----------
        section
            The section defined in the configuration file nested within `cmd`
        cmd_names
            The cmd_name defined in the configuration file
        """
        self.section = section
        self.cmd_names = cmd_names

    def __call__(self, config_path: Path, config_env: str, cmd_names: List[str]) -> dict:
        """
        Get resolved config based on the `file_path` for the configuration file,
        `config_env` targeted inside the config file and corresponding `cmd_name`
        as denoted by `click`.

        Parameters
        ----------
        config_path: Path
            The path of configuration file.
        config_env: str
            The name of the sectional config_env within configuration file.
        cmd_names: List[str]
            The sam command name as defined by click.

        Returns
        -------
        dict
            A dictionary containing the configuration parameters under specified config_env.
        """

        resolved_config: dict = {}

        # Use default sam config file name if config_path only contain the directory
        config_file_path = (
            Path(os.path.abspath(config_path))
            if config_path
            else Path(os.getcwd(), SamConfig.get_default_file(os.getcwd()))
        )
        config_file_name = config_file_path.name
        config_file_dir = config_file_path.parents[0]

        samconfig = SamConfig(config_file_dir, config_file_name)

        # Enable debug level logging by environment variable "SAM_DEBUG"
        if os.environ.get("SAM_DEBUG", "").lower() == "true":
            LOG.setLevel(logging.DEBUG)

        LOG.debug("Config file location: %s", samconfig.path())

        if not samconfig.exists():
            LOG.debug("Config file '%s' does not exist", samconfig.path())
            return resolved_config

        if not self.cmd_names:
            self.cmd_names = cmd_names

        try:
            LOG.debug(
                "Loading configuration values from [%s.%s.%s] (env.command_name.section) in config file at '%s'...",
                config_env,
                self.cmd_names,
                self.section,
                samconfig.path(),
            )

            # NOTE(TheSriram): change from tomlkit table type to normal dictionary,
            # so that click defaults work out of the box.
            resolved_config = dict(samconfig.get_all(self.cmd_names, self.section, env=config_env).items())
            LOG.debug("Configuration values successfully loaded.")
            LOG.debug("Configuration values are: %s", resolved_config)

        except KeyError as ex:
            LOG.debug(
                "Error reading configuration from [%s.%s.%s] (env.command_name.section) "
                "in configuration file at '%s' with : %s",
                config_env,
                self.cmd_names,
                self.section,
                samconfig.path(),
                str(ex),
            )

        except Exception as ex:
            LOG.debug("Error reading configuration file: %s %s", samconfig.path(), str(ex))
            raise ConfigException(f"Error reading configuration: {ex}") from ex

        return resolved_config


def configuration_callback(
    cmd_name: str,
    option_name: str,
    saved_callback: Optional[Callable],
    provider: Callable,
    ctx: click.Context,
    param: click.Parameter,
    value,
):
    """
    Callback for reading the config file.

    Also takes care of calling user specified custom callback afterwards.

    Parameters
    ----------
    cmd_name: str
        The `sam` command name derived from click.
    option_name: str
        The name of the option. This is used for error messages.
    saved_callback: Optional[Callable]
        User-specified callback to be called later.
    provider: Callable
        A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)`.
    ctx: click.Context
        Click context
    param: click.Parameter
        Click parameter
    value
        Specified value for config_env

    Returns
    -------
    The specified callback or the specified value for config_env.
    """

    # ctx, param and value are default arguments for click specified callbacks.
    ctx.default_map = ctx.default_map or {}
    cmd_name = cmd_name or str(ctx.info_name)
    param.default = None
    config_env_name = ctx.params.get("config_env") or DEFAULT_ENV

    config_dir = getattr(ctx, "samconfig_dir", None) or os.getcwd()
    config_file = (  # If given by default, check for other `samconfig` extensions first. Else use user-provided value
        SamConfig.get_default_file(config_dir=config_dir)
        if getattr(ctx.get_parameter_source("config_file"), "name", "") == ParameterSource.DEFAULT.name
        else ctx.params.get("config_file") or SamConfig.get_default_file(config_dir=config_dir)
    )
    # If --config-file is an absolute path, use it, if not, start from config_dir
    config_file_path = config_file if os.path.isabs(config_file) else os.path.join(config_dir, config_file)
    if (
        config_file
        and config_file != DEFAULT_CONFIG_FILE_NAME
        and not (Path(config_file_path).absolute().is_file() or Path(config_file_path).absolute().is_fifo())
    ):
        error_msg = f"Config file {config_file} does not exist or could not be read!"
        LOG.debug(error_msg)
        raise ConfigException(error_msg)

    config = get_ctx_defaults(
        cmd_name,
        provider,
        ctx,
        config_env_name=config_env_name,
        config_file=config_file_path,
    )
    ctx.default_map.update(config)

    return saved_callback(ctx, param, config_env_name) if saved_callback else config_env_name


def get_ctx_defaults(
    cmd_name: str, provider: Callable, ctx: click.Context, config_env_name: str, config_file: Optional[str] = None
) -> Any:
    """
    Get the set of the parameters that are needed to be set into the click command.

    This function also figures out the command name by looking up current click context's parent
    and constructing the parsed command name that is used in default configuration file.
    If a given cmd_name is start-api, the parsed name is "local_start_api".
    provider is called with `config_file`, `config_env_name` and `parsed_cmd_name`.

    Parameters
    ----------
    cmd_name: str
        The `sam` command name.
    provider: Callable
        The provider to be called for reading configuration file.
    ctx: click.Context
        Click context
    config_env_name: str
        The config-env within configuration file, sam configuration file will be relative to the
        supplied original template if its path is not specified.
    config_file: Optional[str]
        The configuration file name.

    Returns
    -------
    Any
        A dictionary of defaults for parameters.
    """

    return provider(config_file, config_env_name, get_cmd_names(cmd_name, ctx))


def configuration_option(*param_decls, **attrs):
    # pylint does not understand the docstring with the presence of **attrs
    # pylint: disable=missing-param-doc,differing-param-doc
    """
    Adds configuration file support to a click application.

    This will create a hidden click option whose callback function loads configuration parameters from default
    configuration environment [default] in default configuration file [samconfig.toml] in the template file
    directory.

    Note
    ----
    This decorator should be added to the top of parameter chain, right below click.command, before
    any options are declared.

    Example
    -------
    >>> @click.command("hello")
        @configuration_option(provider=ConfigProvider(section="parameters"))
        @click.option('--name', type=click.String)
        def hello(name):
            print("Hello " + name)

    Parameters
    ----------
    preconfig_decorator_list: list
        A list of click option decorator which need to place before this function. For
        example, if we want to add option "--config-file" and "--config-env" to allow customized configuration file
        and configuration environment, we will use configuration_option as below:
        @configuration_option(
            preconfig_decorator_list=[decorator_customize_config_file, decorator_customize_config_env],
            provider=ConfigProvider(section=CONFIG_SECTION),
        )
        By default, we enable these two options.
    provider: Callable
        A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)`
    """

    def decorator_configuration_setup(f):
        configuration_setup_params = ()
        configuration_setup_attrs = {}
        configuration_setup_attrs[
            "help"
        ] = "This is a hidden click option whose callback function loads configuration parameters."
        configuration_setup_attrs["is_eager"] = True
        configuration_setup_attrs["expose_value"] = False
        configuration_setup_attrs["hidden"] = True
        configuration_setup_attrs["type"] = click.STRING
        provider = attrs.pop("provider")
        saved_callback = attrs.pop("callback", None)
        partial_callback = functools.partial(configuration_callback, None, None, saved_callback, provider)
        configuration_setup_attrs["callback"] = partial_callback
        return click.option(*configuration_setup_params, **configuration_setup_attrs)(f)

    def composed_decorator(decorators):
        def decorator(f):
            for deco in decorators:
                f = deco(f)
            return f

        return decorator

    # Compose decorators here to make sure the context parameters are updated before callback function
    decorator_list = [decorator_configuration_setup]
    pre_config_decorators = attrs.pop(
        "preconfig_decorator_list", [decorator_customize_config_file, decorator_customize_config_env]
    )
    for decorator in pre_config_decorators:
        decorator_list.append(decorator)
    return composed_decorator(decorator_list)


def decorator_customize_config_file(f: Callable) -> Callable:
    """
    CLI option to customize configuration file name. By default it is 'samconfig.toml' in project directory.
    Ex: --config-file samconfig.toml

    Parameters
    ----------
    f: Callable
        Callback function passed by Click

    Returns
    -------
    Callable
        A Callback function
    """
    config_file_attrs: Dict[str, Any] = {}
    config_file_param_decls = ("--config-file",)
    config_file_attrs["help"] = "Configuration file containing default parameter values."
    config_file_attrs["default"] = DEFAULT_CONFIG_FILE_NAME
    config_file_attrs["show_default"] = True
    config_file_attrs["is_eager"] = True
    config_file_attrs["required"] = False
    config_file_attrs["type"] = click.STRING
    return click.option(*config_file_param_decls, **config_file_attrs)(f)


def decorator_customize_config_env(f: Callable) -> Callable:
    """
    CLI option to customize configuration environment name. By default it is 'default'.
    Ex: --config-env default

    Parameters
    ----------
    f: Callable
        Callback function passed by Click

    Returns
    -------
    Callable
        A Callback function
    """
    config_env_attrs: Dict[str, Any] = {}
    config_env_param_decls = ("--config-env",)
    config_env_attrs["help"] = "Environment name specifying default parameter values in the configuration file."
    config_env_attrs["default"] = DEFAULT_ENV
    config_env_attrs["show_default"] = True
    config_env_attrs["is_eager"] = True
    config_env_attrs["required"] = False
    config_env_attrs["type"] = click.STRING
    return click.option(*config_env_param_decls, **config_env_attrs)(f)


# End section copied from
# [click_config_file](https://github.com/phha/click_config_file/blob/master/click_config_file.py)
