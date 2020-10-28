"""
CLI configuration decorator to use TOML configuration files for click commands.
"""

## This section contains code copied and modified from [click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
## SPDX-License-Identifier: MIT

import os
import functools
import logging

from pathlib import Path
import click

from samcli.commands.exceptions import ConfigException
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
        config_file_path = (
            Path(os.path.abspath(config_path)) if config_path else Path(os.getcwd(), DEFAULT_CONFIG_FILE_NAME)
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
            resolved_config = dict(samconfig.get_all(cmd_names, self.section, env=config_env).items())
            LOG.debug("Configuration values successfully loaded.")
            LOG.debug("Configuration values are: %s", resolved_config)

        except KeyError as ex:
            LOG.debug(
                "Error reading configuration from [%s.%s.%s] (env.command_name.section) "
                "in configuration file at '%s' with : %s",
                config_env,
                cmd_names,
                self.section,
                samconfig.path(),
                str(ex),
            )

        except Exception as ex:
            LOG.debug("Error reading configuration file: %s %s", samconfig.path(), str(ex))
            raise ConfigException(f"Error reading configuration: {ex}") from ex

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
    config_file = ctx.params.get("config_file") or DEFAULT_CONFIG_FILE_NAME
    config_dir = getattr(ctx, "samconfig_dir", None) or os.getcwd()
    # If --config-file is an absolute path, use it, if not, start from config_dir
    config_file_name = config_file if os.path.isabs(config_file) else os.path.join(config_dir, config_file)
    config = get_ctx_defaults(
        cmd_name,
        provider,
        ctx,
        config_env_name=config_env_name,
        config_file=config_file_name,
    )
    ctx.default_map.update(config)

    return saved_callback(ctx, param, config_env_name) if saved_callback else config_env_name


def get_ctx_defaults(cmd_name, provider, ctx, config_env_name, config_file=None):
    """
    Get the set of the parameters that are needed to be set into the click command.
    This function also figures out the command name by looking up current click context's parent
    and constructing the parsed command name that is used in default configuration file.
    If a given cmd_name is start-api, the parsed name is "local_start_api".
    provider is called with `config_file`, `config_env_name` and `parsed_cmd_name`.

    :param cmd_name: `sam` command name
    :param provider: provider to be called for reading configuration file
    :param ctx: Click context
    :param config_env_name: config-env within configuration file, sam configuration file will be relative to the
                            supplied original template if its path is not specified
    :param config_file: configuration file name
    :return: dictionary of defaults for parameters
    """

    return provider(config_file, config_env_name, get_cmd_names(cmd_name, ctx))


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

    This will create a hidden click option whose callback function loads configuration parameters from default
    configuration environment [default] in default configuration file [samconfig.toml] in the template file
    directory.
    :param preconfig_decorator_list: A list of click option decorator which need to place before this function. For
        exmple, if we want to add option "--config-file" and "--config-env" to allow customized configuration file
        and configuration environment, we will use configuration_option as below:
        @configuration_option(
            preconfig_decorator_list=[decorator_customize_config_file, decorator_customize_config_env],
            provider=TomlProvider(section=CONFIG_SECTION),
        )
        By default, we enable these two options.
    :param provider: A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, config_env, cmd_name)
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


def decorator_customize_config_file(f):
    """
    CLI option to customize configuration file name. By default it is 'samconfig.toml' in project directory.
    Ex: --config-file samconfig.toml
    :param f: Callback function passed by Click
    :return: Callback function
    """
    config_file_attrs = {}
    config_file_param_decls = ("--config-file",)
    config_file_attrs["help"] = (
        "The path and file name of the configuration file containing default parameter values to use. "
        "Its default value is 'samconfig.toml' in project directory. For more information about configuration files, "
        "see: "
        "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html."
    )
    config_file_attrs["default"] = "samconfig.toml"
    config_file_attrs["is_eager"] = True
    config_file_attrs["required"] = False
    config_file_attrs["type"] = click.STRING
    return click.option(*config_file_param_decls, **config_file_attrs)(f)


def decorator_customize_config_env(f):
    """
    CLI option to customize configuration environment name. By default it is 'default'.
    Ex: --config-env default
    :param f: Callback function passed by Click
    :return: Callback function
    """
    config_env_attrs = {}
    config_env_param_decls = ("--config-env",)
    config_env_attrs["help"] = (
        "The environment name specifying the default parameter values in the configuration file to use. "
        "Its default value is 'default'. For more information about configuration files, see: "
        "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html."
    )
    config_env_attrs["default"] = "default"
    config_env_attrs["is_eager"] = True
    config_env_attrs["required"] = False
    config_env_attrs["type"] = click.STRING
    return click.option(*config_env_param_decls, **config_env_attrs)(f)


# End section copied from [[click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
