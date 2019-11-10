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
DEFAULT_CONFIG_FILE_NAME = "sam-config"
DEFAULT_IDENTIFER = "default"


class TomlProvider:
    """
    A parser for toml configuration files
    :param cmd: sam command name as defined by click
    :param section: section defined in the configuration file nested within `cmd`
    """

    def __init__(self, cmd=None, section=None):
        self.cmd = cmd
        self.section = section

    def __call__(self, file_path, identifier, cmd_name):
        """
        :param file_path: The path to the configuration file
        :param identifier: The name of the sectional identifier within configuration file.
        :param cmd_name: sam command name as defined by click
        :returns dictionary containing the configuration parameters under specified identifier
        """
        config = toml.load(file_path)
        resolved_config = {}
        if self.section:
            try:
                resolved_config = self._get_identifier(config, identifier)[self.cmd][self.section]
            except KeyError:
                LOG.debug(
                    "Error reading configuration file at %s with identifier %s, command %s, section %s",
                    file_path,
                    identifier,
                    self.cmd,
                    self.section,
                )
        return resolved_config

    def _get_identifier(self, config, identifier):
        """

        :param config: loaded TOML configuration file into dictionary representation
        :param identifier: top level section defined within TOML configuration file
        :return:
        """
        return config.get(identifier)


def configuration_callback(cmd_name, option_name, identifier_name, saved_callback, provider, ctx, param, value):
    """
    Callback for reading the config file.

    Also takes care of calling user specified custom callback afterwards.

    :param cmd_name: `sam` command name derived from click.
    :param option_name: The name of the option. This is used for error messages.
    :param identifier_name: `top` level section within configuration file
    :param saved_callback: User-specified callback to be called later.
    :param provider:  A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, identifier, cmd_name)`.
    :param ctx: Click context
    :param param: Click parameter
    :param value: Specified value for identifier
    :returns specified callback or the specified value for identifier.
    """
    ctx.default_map = ctx.default_map or {}
    cmd_name = cmd_name or ctx.info_name

    config_file = os.getenv("SAM_CONFIG", os.path.abspath(os.path.join(".", DEFAULT_CONFIG_FILE_NAME)))

    param.default = DEFAULT_IDENTIFER
    identifier_name = value or identifier_name

    if os.path.isfile(config_file):
        try:
            LOG.debug("Config file location: %s", os.path.abspath(config_file))
            config = provider(config_file, identifier_name, cmd_name)

        except Exception as ex:

            raise click.BadOptionUsage(
                option_name,
                "Error reading configuration file: {} with identifier {}, {}".format(
                    config_file, identifier_name, str(ex)
                ),
                ctx,
            )
        ctx.default_map.update(config)

    return saved_callback(ctx, param, value) if saved_callback else value


def configuration_option(*param_decls, **attrs):
    """
    Adds configuration file support to a click application.

    This will create an option of type `STRING` expecting the identifier in the
    configuration file, by default this identifier is `default`. When specified,
    the requisite portion of the configuration file is considered as the
    source of truth.

    The default name of the option is `--identifier`.

    This decorator accepts the same arguments as `click.option`.
    In addition, the following keyword arguments are available:
    :param cmd_name: The command name. Default: `ctx.info_name`
    :param identifier_name: The identifier name. This is used to determine which part of the configuration
        needs to be read.
    :param provider:         A callable that parses the configuration file and returns a dictionary
        of the configuration parameters. Will be called as
        `provider(file_path, identifier, cmd_name)
    """
    param_decls = param_decls or ("--identifier",)
    option_name = param_decls[0]

    def decorator(f):

        attrs.setdefault("is_eager", True)
        attrs.setdefault("help", "Read identifier from Configuration File.")
        attrs.setdefault("expose_value", False)
        cmd_name = attrs.pop("cmd_name", None)
        identifier_name = attrs.pop("identifier_name", DEFAULT_IDENTIFER)
        provider = attrs.pop("provider", TomlProvider())
        attrs["type"] = click.STRING
        saved_callback = attrs.pop("callback", None)
        partial_callback = functools.partial(
            configuration_callback, cmd_name, option_name, identifier_name, saved_callback, provider
        )
        attrs["callback"] = partial_callback
        return click.option(*param_decls, **attrs)(f)

    return decorator


# End section copied from [[click_config_file][https://github.com/phha/click_config_file/blob/master/click_config_file.py]
