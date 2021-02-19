"""
Class representing the samconfig.toml
"""

import os
import logging

from pathlib import Path
from typing import Any, Iterable

import tomlkit

from samcli.lib.config.version import SAM_CONFIG_VERSION, VERSION_KEY
from samcli.lib.config.exceptions import SamConfigVersionException

LOG = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE_NAME = "samconfig.toml"
DEFAULT_ENV = "default"
DEFAULT_GLOBAL_CMDNAME = "global"


class SamConfig:
    """
    Class to interface with `samconfig.toml` file.
    """

    document = None

    def __init__(self, config_dir, filename=None):
        """
        Initialize the class

        Parameters
        ----------
        config_dir : string
            Directory where the configuration file needs to be stored

        filename : string
            Optional. Name of the configuration file. It is recommended to stick with default so in the future we
            could automatically support auto-resolving multiple config files within same directory.
        """
        self.filepath = Path(config_dir, filename or DEFAULT_CONFIG_FILE_NAME)

    def get_all(self, cmd_names, section, env=DEFAULT_ENV):
        """
        Gets a value from the configuration file for the given environment, command and section

        Parameters
        ----------
        cmd_names : list(str)
            List of representing the entire command. Ex: ["local", "generate-event", "s3", "put"]

        section : str
            Specific section within the command to look into Ex: `parameters`

        env : str
            Optional, Name of the environment

        Returns
        -------
        dict
            Dictionary of configuration options in the file. None, if the config doesn't exist.

        Raises
        ------
        KeyError
            If the config file does *not* have the specific section

        tomlkit.exceptions.TOMLKitError
            If the configuration file is invalid
        """

        env = env or DEFAULT_ENV

        self._read()
        if isinstance(self.document, dict):
            params = self.document.get(env, {}).get(self._to_key(cmd_names), {}).get(section, {})
            if DEFAULT_GLOBAL_CMDNAME in self.document.get(env, {}):
                global_params = self.document.get(env, {}).get(DEFAULT_GLOBAL_CMDNAME, {}).get(section, {})
                global_params.update(params.copy())
                params = global_params.copy()
            return params
        return {}

    def put(self, cmd_names, section, key, value, env=DEFAULT_ENV):
        """
        Writes the `key=value` under the given section. You have to call the `flush()` method after `put()` in
        order to write the values back to the config file. Otherwise they will be just saved in-memory, available
        for future access, but never saved back to the file.

        Parameters
        ----------
        cmd_names : list(str)
            List of representing the entire command. Ex: ["local", "generate-event", "s3", "put"]

        section : str
            Specific section within the command to look into Ex: `parameters`

        key : str
            Key to write the data under

        value
            Value to write. Could be any of the supported TOML types.

        env : str
            Optional, Name of the environment

        Raises
        ------
        tomlkit.exceptions.TOMLKitError
            If the data is invalid
        """

        if not self.document:
            self._read()
        # Empty document prepare the initial structure.
        # self.document is a nested dict, we need to check each layer and add new tables, otherwise duplicated key
        # in parent layer will override the whole child layer
        if self.document.get(env, None):
            if self.document[env].get(self._to_key(cmd_names), None):
                if self.document[env][self._to_key(cmd_names)].get(section, None):
                    self.document[env][self._to_key(cmd_names)][section].update({key: value})
                else:
                    self.document[env][self._to_key(cmd_names)].update({section: {key: value}})
            else:
                self.document[env].update({self._to_key(cmd_names): {section: {key: value}}})
        else:
            self.document.update({env: {self._to_key(cmd_names): {section: {key: value}}}})

        self._deduplicate_global_parameters(cmd_names, section, key, value, env)

    def flush(self):
        """
        Write the data back to file

        Raises
        ------
        tomlkit.exceptions.TOMLKitError
            If the data is invalid

        """
        self._write()

    def sanity_check(self):
        """
        Sanity check the contents of samconfig
        """
        try:
            self._read()
        except tomlkit.exceptions.TOMLKitError:
            return False
        else:
            return True

    def exists(self):
        return self.filepath.exists()

    def path(self):
        return str(self.filepath)

    @staticmethod
    def config_dir(template_file_path=None):
        """
        SAM Config file is always relative to the SAM Template. If it the template is not
        given, then it is relative to cwd()
        """
        if template_file_path:
            return os.path.dirname(template_file_path)

        return os.getcwd()

    def _read(self):
        if not self.document:
            try:
                txt = self.filepath.read_text()
                self.document = tomlkit.loads(txt)
                self._version_sanity_check(self._version())
            except OSError:
                self.document = tomlkit.document()

        if self.document.body:
            self._version_sanity_check(self._version())
        return self.document

    def _write(self):
        if not self.document:
            return
        if not self.exists():
            open(self.filepath, "a+").close()

        current_version = self._version() if self._version() else SAM_CONFIG_VERSION
        try:
            self.document.add(VERSION_KEY, current_version)
        except tomlkit.exceptions.KeyAlreadyPresent:
            # NOTE(TheSriram): Do not attempt to re-write an existing version
            pass
        self.filepath.write_text(tomlkit.dumps(self.document))

    def _version(self):
        return self.document.get(VERSION_KEY, None)

    def _deduplicate_global_parameters(self, cmd_names, section, key, value, env=DEFAULT_ENV):
        """
        In case the global parameters contains the same key-value with command parameters,
        we remove the entry in command parameters

        Parameters
        ----------
        cmd_names : list(str)
            List of representing the entire command. Ex: ["local", "generate-event", "s3", "put"]

        section : str
            Specific section within the command to look into Ex: `parameters`

        key : str
            Key to write the data under

        value
            Value to write. Could be any of the supported TOML types.

        env : str
            Optional, Name of the environment
        """
        cmd_name = self._to_key(cmd_names)
        global_params = self.document.get(env, {}).get(DEFAULT_GLOBAL_CMDNAME, {}).get(section, {})
        command_params = self.document.get(env, {}).get(cmd_name, {}).get(section, {})
        if (
            cmd_name != DEFAULT_GLOBAL_CMDNAME
            and global_params
            and command_params
            and global_params.get(key)
            and global_params.get(key) == command_params.get(key)
        ):
            value = command_params.get(key)
            save_global_message = (
                f'\n\tParameter "{key}={value}" in [{env}.{cmd_name}.{section}] is defined as a global '
                f"parameter [{env}.{DEFAULT_GLOBAL_CMDNAME}.{section}].\n\tThis parameter will be only saved "
                f"under [{env}.{DEFAULT_GLOBAL_CMDNAME}.{section}] in {self.filepath}."
            )
            LOG.info(save_global_message)
            # Only keep the global parameter
            items = self.document[env][cmd_name][section].copy()
            items.pop(key)
            self.document[env][cmd_name][section] = items

    @staticmethod
    def _version_sanity_check(version: Any) -> None:
        if not isinstance(version, float):
            raise SamConfigVersionException(f"'{VERSION_KEY}' key is not present or is in unrecognized format. ")

    @staticmethod
    def _to_key(cmd_names: Iterable[str]) -> str:
        # construct a parsed name that is of the format: a_b_c_d
        return "_".join([cmd.replace("-", "_").replace(" ", "_") for cmd in cmd_names])
