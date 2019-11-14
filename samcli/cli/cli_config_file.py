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

__all__ = ("TomlProvider", "configuration_option", "get_ctx_defaults")

LOG = logging.getLogger("samcli")
DEFAULT_CONFIG_FILE_NAME = "samconfig.toml"
DEFAULT_IDENTIFER = "default"


class TomlProvider:
    """
    A parser for toml configuration files
    :param cmd: sam command name as defined by click
    :param section: section defined in the configuration file nested within `cmd`
    """

    def __init__(self, section=None):
        self.section = section

    def __call__(self, file_path, config_env, cmd_name):
        """
        Get resolved config based on the `file_path` for the configuration file,
        `config_env` targeted inside the config file and corresponding `cmd_name`
        as denoted by `click`.

        :param file_path: The path to the configuration file
        :param config_env: The name of the sectional config_env within configuration file.
        :param cmd_name: sam command name as defined by click
        :returns dictionary containing the configuration parameters under specified config_env
        """
        resolved_config = {}
        try:
            config = toml.load(file_path)
        except Exception as ex:
            LOG.error("Error reading configuration file :%s %s", file_path, str(ex))
            return resolved_config
        if self.section:
            try:
                resolved_config = self._get_config_env(config, config_env)[cmd_name][self.section]
            except KeyError:
                LOG.debug(
                    "Error reading configuration file at %s with config_env %s, command %s, section %s",
                    file_path,
                    config_env,
                    cmd_name,
                    self.section,
                )
        return resolved_config

    def _get_config_env(self, config, config_env):
        """

        :param config: loaded TOML configuration file into dictionary representation
        :param config_env: top level section defined within TOML configuration file
        :return:
        """
        return config.get(config_env, config.get(DEFAULT_IDENTIFER, {}))


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
    param.default = DEFAULT_IDENTIFER
    config_env_name = value or config_env_name
    config = get_ctx_defaults(cmd_name, provider, ctx, config_env_name=config_env_name)
    ctx.default_map.update(config)

    return saved_callback(ctx, param, value) if saved_callback else value


def get_ctx_defaults(cmd_name, provider, ctx, config_env_name=DEFAULT_IDENTIFER):
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
    config_file = os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE_NAME)
    config = {}
    if os.path.isfile(config_file):
        LOG.debug("Config file location: %s", os.path.abspath(config_file))

        # Find parent of current context
        _parent = ctx.parent
        _cmd_names = []
        # Need to find the total set of commands that current command is part of.
        if cmd_name != ctx.info_name:
            _cmd_names = [cmd_name]
        _cmd_names.append(ctx.info_name)
        # Go through all parents till a parent of a context exists.
        while _parent.parent:
            info_name = _parent.info_name
            _cmd_names.append(info_name)
            _parent = _parent.parent

        # construct a parsed name that is of the format: a_b_c_d
        parsed_cmd_name = "_".join(reversed([cmd.replace("-", "_").replace(" ", "_") for cmd in _cmd_names]))

        config = provider(config_file, config_env_name, parsed_cmd_name)

    return config


def configuration_option(*param_decls, **attrs):
    """
    Adds configuration file support to a click application.

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
        config_env_name = attrs.pop("config_env_name", DEFAULT_IDENTIFER)
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
