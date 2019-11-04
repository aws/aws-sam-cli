"""
CLI configuration decorator to use TOML configuration files for click commands.
"""

## This section contains code copied and modified from [click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
## SPDX-License-Identifier: MIT

import functools
import os
import logging

import click
import toml

__all__ = ("TomlProvider", "configuration_option")

LOG = logging.getLogger(__name__)
DEFAULT_CONFIG_FILE_NAME = "sam-app-config"


class TomlProvider:
    """
    A parser for toml configuration files

    Parameters
    ----------
    section : str
        If this is set to something other than the default of `None`, the
        provider will look for a corresponding section inside the
        configuration file and return only the values from that section.
    """

    def __init__(self, section=None):
        self.section = section

    def __call__(self, file_path, cmd_name):
        """
        Parse and return the configuration parameters.

        Parameters
        ----------
        file_path : str
            The path to the configuration file
        cmd_name : str
            The name of the click command

        Returns
        -------
        dict
            A dictionary containing the configuration parameters.
        """
        config = toml.load(file_path)
        if self.section:
            try:
                config = config[self.section]
            except KeyError:
                LOG.warning("Specified section: %s does not exist in the config file", self.section)
        return config


def configuration_callback(cmd_name, option_name, config_file_name, saved_callback, provider, ctx, param, value):
    """
    Callback for reading the config file.

    Also takes care of calling user specified custom callback afterwards.

    cmd_name : str
        The command name. This is used to determine the configuration directory.
    option_name : str
        The name of the option. This is used for error messages.
    config_file_name : str
        The name of the configuration file.
    saved_callback: callable
        User-specified callback to be called later.
    provider : callable
        A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, cmd_name)`. Default: `toml_provider()`
    ctx : object
        Click context.
    """
    ctx.default_map = ctx.default_map or {}
    cmd_name = cmd_name or ctx.info_name

    default_value = os.path.join(".aws-sam", config_file_name)

    param.default = default_value
    value = value or default_value

    if os.path.isfile(value):
        try:
            LOG.info("Config file location: %s", os.path.abspath(value))
            config = provider(value, cmd_name)

        except Exception as e:

            raise click.BadOptionUsage(option_name, "Error reading configuration file: {}".format(e), ctx)
        ctx.default_map.update(config)

    return saved_callback(ctx, param, value) if saved_callback else value


def configuration_option(*param_decls, **attrs):
    """
    Adds configuration file support to a click application.

    This will create an option of type `click.File` expecting the path to a
    configuration file. When specified, it overwrites the default values for
    all other click arguments or options with the corresponding value from the
    configuration file.

    The default name of the option is `--config`.

    This decorator accepts the same arguments as `click.option` and
    `click.Path`. In addition, the following keyword arguments are available:

    cmd_name : str
        The command name. This is used to determine the configuration
        directory. Default: `ctx.info_name`
    config_file_name : str
        The name of the configuration file. Default: `'sam-app-config'``
    provider : callable
        A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, cmd_name)`. Default: `toml_provider()`
        """
    param_decls = param_decls or ("--config",)
    option_name = param_decls[0]

    def decorator(f):

        attrs.setdefault("is_eager", True)
        attrs.setdefault("help", "Read configuration from FILE.")
        attrs.setdefault("expose_value", False)
        cmd_name = attrs.pop("cmd_name", None)
        config_file_name = attrs.pop("config_file_name", DEFAULT_CONFIG_FILE_NAME)
        provider = attrs.pop("provider", TomlProvider())
        path_default_params = {
            "exists": False,
            "file_okay": True,
            "dir_okay": False,
            "writable": False,
            "readable": True,
            "resolve_path": False,
        }
        path_params = {k: attrs.pop(k, v) for k, v in path_default_params.items()}
        attrs["type"] = click.Path(**path_params)
        saved_callback = attrs.pop("callback", None)
        partial_callback = functools.partial(
            configuration_callback, cmd_name, option_name, config_file_name, saved_callback, provider
        )
        attrs["callback"] = partial_callback
        return click.option(*param_decls, **attrs)(f)

    return decorator


# End section copied from [[click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
