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
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV

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

    def __call__(self, config_dir, config_env, cmd_names):
        """
        Get resolved config based on the `file_path` for the configuration file,
        `config_env` targeted inside the config file and corresponding `cmd_name`
        as denoted by `click`.

        :param config_env: The name of the sectional config_env within configuration file.
        :param cmd_names list(str): sam command name as defined by click
        :returns dictionary containing the configuration parameters under specified config_env
        """

        resolved_config = {}

        samconfig = SamConfig(config_dir)
        LOG.debug("Config file location: %s", samconfig.path())

        if not samconfig.exists():
            LOG.debug("Config file does not exist")
            return resolved_config

        try:
            LOG.debug("Getting configuration value for %s %s %s", cmd_names, self.section, config_env)

            # NOTE(TheSriram): change from tomlkit table type to normal dictionary,
            # so that click defaults work out of the box.
            samconfig.sanity_check()
            resolved_config = {k: v for k, v in samconfig.get_all(cmd_names, self.section, env=config_env).items()}
            LOG.debug("Configuration values read from the file: %s", resolved_config)

        except KeyError as ex:
            LOG.debug(
                "Error reading configuration file at %s with config_env=%s, command=%s, section=%s %s",
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
            LOG.debug("Error reading configuration file: %s %s", samconfig.path(), str(ex))

        return resolved_config


def configuration_callback(cmd_name, option_name, config_env_name, saved_callback, provider, ctx, param, value):
    """
    Callback for reading the config file.

    Also takes care of calling user specified custom callback afterwards.

    :param cmd_name: `sam` command name derived from click.
    :param option_name: The name of the option. This is used for error messages.
    :param config_env_name: `top` level section within configuration file
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
    # explicitly ignore values passed to --config-env, can be opened up in the future.
    config_env_name = DEFAULT_ENV
    config = get_ctx_defaults(cmd_name, provider, ctx, config_env_name=config_env_name)
    ctx.default_map.update(config)

    return saved_callback(ctx, param, config_env_name) if saved_callback else config_env_name


def get_ctx_defaults(cmd_name, provider, ctx, config_env_name):
    """
    Get the set of the parameters that are needed to be set into the click command.
    This function also figures out the command name by looking up current click context's parent
    and constructing the parsed command name that is used in default configuration file.
    If a given cmd_name is start-api, the parsed name is "local_start_api".
    provider is called with `config_file`, `config_env_name` and `parsed_cmd_name`.

    :param cmd_name: `sam` command name
    :param provider: provider to be called for reading configuration file
    :param ctx: Click context
    :param config_env_name: config-env within configuration file
    :return: dictionary of defaults for parameters
    """

    # `config_dir` will be a directory relative to SAM template, if it is available. If not it's relative to cwd
    config_dir = getattr(ctx, "samconfig_dir", None) or os.getcwd()
    return provider(config_dir, config_env_name, get_cmd_names(cmd_name, ctx))


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

    This will create an option of type `STRING` expecting the config_env in the
    configuration file, by default this config_env is `default`. When specified,
    the requisite portion of the configuration file is considered as the
    source of truth.

    The default name of the option is `--config-env`.

    This decorator accepts the same arguments as `click.option`.
    In addition, the following keyword arguments are available:
    :param cmd_name: The command name. Default: `ctx.info_name`
    :param config_env_name: The config_env name. This is used to determine which part of the configuration
        needs to be read.
    :param provider:         A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)
    """
    param_decls = param_decls or ("--config-env",)
    option_name = param_decls[0]

    def decorator(f):

        attrs.setdefault("is_eager", True)
        attrs.setdefault("help", "Read config-env from Configuration File.")
        attrs.setdefault("expose_value", False)
        # --config-env is hidden and can potentially be opened up in the future.
        attrs.setdefault("hidden", True)
        # explicitly ignore values passed to --config-env, can be opened up in the future.
        config_env_name = DEFAULT_ENV
        provider = attrs.pop("provider")
        attrs["type"] = click.STRING
        saved_callback = attrs.pop("callback", None)
        partial_callback = functools.partial(
            configuration_callback, None, option_name, config_env_name, saved_callback, provider
        )
        attrs["callback"] = partial_callback
        return click.option(*param_decls, **attrs)(f)

    return decorator


# End section copied from [[click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
