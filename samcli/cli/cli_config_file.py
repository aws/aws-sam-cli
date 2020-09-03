"""
CLI configuration decorator to use TOML configuration files for click commands.
"""

## This section contains code copied and modified from [click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
## SPDX-License-Identifier: MIT

import os
import functools
import logging

import click

from samcli.commands.exceptions import ConfigException
from samcli.lib.config.exceptions import SamConfigVersionException
from samcli.cli.context import get_cmd_names
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV, DEFAULT_CONFIG_FILE_NAME

__all__ = ("TomlProvider", "configuration_option", "get_ctx_defaults")

LOG = logging.getLogger(__name__)


class TomlProvider:
    """
    A parser for toml configuration files
    :param cmd: sam command name as defined by click
    :param section: section defined in the configuration file nested within `cmd`
    """

    def __init__(self, section=None):
        self.section = section

    def __call__(self, config_path, config_env, cmd_names):
        """
        Get resolved config based on the `file_path` for the configuration file,
        `config_env` targeted inside the config file and corresponding `cmd_name`
        as denoted by `click`.

        :param config_path: The path of configuration file.
        :param config_env: The name of the sectional config_env within configuration file.
        :param cmd_names list(str): sam command name as defined by click
        :returns dictionary containing the configuration parameters under specified config_env
        """

        resolved_config = {}

        # Use default sam config file name if config_path only contain the directory

        samconfig = (
            SamConfig(config_path)
            if os.path.isdir(config_path)
            else SamConfig(os.path.split(config_path)[0], os.path.split(config_path)[1])
        )
        LOG.debug("Config file location: %s", samconfig.path())

        if not samconfig.exists():
            LOG.debug("Config file '%s' does not exist", samconfig.path())
            return resolved_config

        try:
            LOG.debug(
                "Loading configuration values from [%s.%s.%s] (env.command_name.section) in config file at '%s'...",
                config_env,
                cmd_names,
                self.section,
                samconfig.path(),
            )

            # NOTE(TheSriram): change from tomlkit table type to normal dictionary,
            # so that click defaults work out of the box.
            samconfig.sanity_check()
            resolved_config = {k: v for k, v in samconfig.get_all(cmd_names, self.section, env=config_env).items()}
            LOG.debug("Configuration values successfully loaded.")
            LOG.debug("Configuration values are: %s", resolved_config)

        except KeyError as ex:
            LOG.debug(
                "Error reading configuration from [%s.%s.%s] (env.command_name.section) "
                "in configuration file at '%s' with : %s",
                samconfig.path(),
                config_env,
                cmd_names,
                self.section,
                str(ex),
            )

        except SamConfigVersionException as ex:
            LOG.debug("%s %s", samconfig.path(), str(ex))
            raise ConfigException(f"Syntax invalid in samconfig.toml: {str(ex)}")

        except Exception as ex:
            LOG.info("Error reading configuration file: %s %s", samconfig.path(), str(ex))

        return resolved_config


def configuration_callback(cmd_name, option_name, saved_callback, provider, ctx, param, value):
    """
    Callback for reading the config file.

    Also takes care of calling user specified custom callback afterwards.

    :param cmd_name: `sam` command name derived from click.
    :param option_name: The name of the option. This is used for error messages.
    :param saved_callback: User-specified callback to be called later.
    :param provider:  A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)`.
    :param ctx: Click context
    :param param: Click parameter
    :param value: Specified value for config_env
    :returns specified callback or the specified value for config_env.
    """

    # ctx, param and value are default arguments for click specified callbacks.
    ctx.default_map = ctx.default_map or {}
    cmd_name = cmd_name or ctx.info_name
    param.default = None
    config_env_name = ctx.params.get("config_env") or DEFAULT_ENV
    config_file_name = ctx.params.get("config_file") or DEFAULT_CONFIG_FILE_NAME
    config = get_ctx_defaults(
        cmd_name, provider, ctx, config_env_name=config_env_name, config_file_name=config_file_name
    )
    ctx.default_map.update(config)

    return saved_callback(ctx, param, config_env_name) if saved_callback else config_env_name


def get_ctx_defaults(cmd_name, provider, ctx, config_env_name, config_file_name=DEFAULT_CONFIG_FILE_NAME):
    """
    Get the set of the parameters that are needed to be set into the click command.
    This function also figures out the command name by looking up current click context's parent
    and constructing the parsed command name that is used in default configuration file.
    If a given cmd_name is start-api, the parsed name is "local_start_api".
    provider is called with `config_file`, `config_env_name` and `parsed_cmd_name`.

    :param cmd_name: `sam` command name
    :param provider: provider to be called for reading configuration file
    :param ctx: Click context
    :param config_env_name: config-env within configuration file, sam configuration file should always be relative
                            to the supplied original template
    :param config_file: configuration file name
    :return: dictionary of defaults for parameters
    """

    config_path = getattr(ctx, "samconfig_dir", None) or os.getcwd()
    config_file = os.path.join(config_path, config_file_name)

    return provider(config_file, config_env_name, get_cmd_names(cmd_name, ctx))


# pylint: disable=too-many-statements
def configuration_option(*param_decls, **attrs):
    """
    Adds configuration file support to a click application.

    NOTE: This decorator should be added to the top of parameter chain, right below click.command, before
          any options are declared.

    Example:
        >>> @click.command("hello")
            @configuration_option(provider=TomlProvider(section="parameters"))
            @click.option('--name', type=click.String)
            def hello(name):
                print("Hello " + name)

    By default, this will create a hidden click option whose callback function loads configuration parameters from
    default configuration environment [default] in default configuration file [samconfig.toml] in the template file
    directory.
    :param enable_custom_config_file: If this is True, an additional click option of type `STRING` expecting the
     customized configuration file name as '--config_file' will be enabled.
    :param enable_custom_config_env: If this is True, an additional click option of type `STRING` expecting the
     customized configuration environment as '--config_env' will be enabled.
    :param provider: A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)
    """
    enable_custom_config_file = attrs.pop("enable_custom_config_file", False)
    enable_custom_config_env = attrs.pop("enable_custom_config_env", False)

    def decorator_customize_config_file(f):
        config_file_attrs = {}
        config_file_param_decls = ("--config-file",)
        config_file_attrs["help"] = "Read config-file from Configuration File."
        config_file_attrs["default"] = "samconfig.toml"
        config_file_attrs["is_eager"] = True
        config_file_attrs["required"] = False
        config_file_attrs["type"] = click.STRING
        return click.option(*config_file_param_decls, **config_file_attrs)(f)

    def decorator_customize_config_env(f):
        config_env_attrs = {}
        config_env_param_decls = ("--config-env",)
        config_env_attrs["help"] = "Read config-file from Configuration File."
        config_env_attrs["default"] = "default"
        config_env_attrs["is_eager"] = True
        config_env_attrs["required"] = False
        config_env_attrs["type"] = click.STRING
        return click.option(*config_env_param_decls, **config_env_attrs)(f)

    def decorator_read_configs(f):
        read_config_attrs = {}
        read_config_param_decls = ("--read_config",)
        read_config_attrs["help"] = "Read configurations from Configuration File."
        read_config_attrs["is_eager"] = True
        read_config_attrs["expose_value"] = False
        read_config_attrs["hidden"] = True
        read_config_attrs["type"] = click.STRING
        provider = attrs.pop("provider")
        saved_callback = attrs.pop("callback", None)
        partial_callback = functools.partial(configuration_callback, None, None, saved_callback, provider)
        read_config_attrs["callback"] = partial_callback
        return click.option(*read_config_param_decls, **read_config_attrs)(f)

    def composed_decorator(decorators):
        def decorator(f):
            for deco in decorators:
                f = deco(f)
            return f

        return decorator

    # Compose decorators here to make sure the context parameters are updated before callback function of option
    # "--read_config" is evaluated.
    decorator_list = [decorator_read_configs]
    if enable_custom_config_file:
        decorator_list.append(decorator_customize_config_file)
    if enable_custom_config_env:
        decorator_list.append(decorator_customize_config_env)
    return composed_decorator(decorator_list)


# End section copied from [[click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
