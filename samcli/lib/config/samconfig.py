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

    def __init__(self, config_dir, filename=None):  # type: ignore[no-untyped-def]
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

    def get_stage_configuration_names(self):  # type: ignore[no-untyped-def]
        self._read()  # type: ignore[no-untyped-call]
        if isinstance(self.document, dict):
            return [stage for stage, value in self.document.items() if isinstance(value, dict)]
        return []

    def get_all(self, cmd_names, section, env=DEFAULT_ENV):  # type: ignore[no-untyped-def]
        """
        Gets a value from the configuration file for the given environment, command and section

        Parameters
        ----------
        cmd_names : list(str)
            List of representing the entire command. Ex: ["local", "generate-event", "s3", "put"]
        section : str
            Specific section within the command to look into. e.g. `parameters`
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

        self._read()  # type: ignore[no-untyped-call]
        if isinstance(self.document, dict):
            toml_content = self.document.get(env, {})
            params = toml_content.get(self._to_key(cmd_names), {}).get(section, {})
            if DEFAULT_GLOBAL_CMDNAME in toml_content:
                global_params = toml_content.get(DEFAULT_GLOBAL_CMDNAME, {}).get(section, {})
                global_params.update(params.copy())
                params = global_params.copy()
            return params
        return {}

    def put(self, cmd_names, section, key, value, env=DEFAULT_ENV):  # type: ignore[no-untyped-def]
        """
        Writes the `key=value` under the given section. You have to call the `flush()` method after `put()` in
        order to write the values back to the config file. Otherwise they will be just saved in-memory, available
        for future access, but never saved back to the file.

        Parameters
        ----------
        cmd_names : list(str)
            List of representing the entire command. Ex: ["local", "generate-event", "s3", "put"]
        section : str
            Specific section within the command to look into. e.g. `parameters`
        key : str
            Key to write the data under
        value : Any
            Value to write. Could be any of the supported TOML types.
        env : str
            Optional, Name of the environment

        Raises
        ------
        tomlkit.exceptions.TOMLKitError
            If the data is invalid
        """

        if not self.document:
            self._read()  # type: ignore[no-untyped-call]
        # Empty document prepare the initial structure.
        # self.document is a nested dict, we need to check each layer and add new tables, otherwise duplicated key
        # in parent layer will override the whole child layer
        cmd_name_key = self._to_key(cmd_names)
        env_content = self.document.get(env, {})  # type: ignore[attr-defined]
        cmd_content = env_content.get(cmd_name_key, {})
        param_content = cmd_content.get(section, {})
        if param_content:
            param_content.update({key: value})
        elif cmd_content:
            cmd_content.update({section: {key: value}})
        elif env_content:
            env_content.update({cmd_name_key: {section: {key: value}}})
        else:
            self.document.update({env: {cmd_name_key: {section: {key: value}}}})  # type: ignore[attr-defined]
        # If the value we want to add to samconfig already exist in global section, we don't put it again in
        # the special command section
        self._deduplicate_global_parameters(cmd_name_key, section, key, env)  # type: ignore[no-untyped-call]

    def flush(self):  # type: ignore[no-untyped-def]
        """
        Write the data back to file

        Raises
        ------
        tomlkit.exceptions.TOMLKitError
            If the data is invalid

        """
        self._write()  # type: ignore[no-untyped-call]

    def sanity_check(self):  # type: ignore[no-untyped-def]
        """
        Sanity check the contents of samconfig
        """
        try:
            self._read()  # type: ignore[no-untyped-call]
        except tomlkit.exceptions.TOMLKitError:
            return False
        else:
            return True

    def exists(self):  # type: ignore[no-untyped-def]
        return self.filepath.exists()

    def _ensure_exists(self):  # type: ignore[no-untyped-def]
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.touch()

    def path(self):  # type: ignore[no-untyped-def]
        return str(self.filepath)

    @staticmethod
    def config_dir(template_file_path=None):  # type: ignore[no-untyped-def]
        """
        SAM Config file is always relative to the SAM Template. If it the template is not
        given, then it is relative to cwd()
        """
        if template_file_path:
            return os.path.dirname(template_file_path)

        return os.getcwd()

    def _read(self):  # type: ignore[no-untyped-def]
        if not self.document:
            try:
                txt = self.filepath.read_text()
                self.document = tomlkit.loads(txt)  # type: ignore[attr-defined]
                self._version_sanity_check(self._version())  # type: ignore[no-untyped-call]
            except OSError:
                self.document = tomlkit.document()  # type: ignore[attr-defined]

        if self.document.body:
            self._version_sanity_check(self._version())  # type: ignore[no-untyped-call]
        return self.document

    def _write(self):  # type: ignore[no-untyped-def]
        if not self.document:
            return

        self._ensure_exists()  # type: ignore[no-untyped-call]

        current_version = self._version() if self._version() else SAM_CONFIG_VERSION  # type: ignore[no-untyped-call]
        try:
            self.document.add(VERSION_KEY, current_version)
        except tomlkit.exceptions.KeyAlreadyPresent:
            # NOTE(TheSriram): Do not attempt to re-write an existing version
            pass
        self.filepath.write_text(tomlkit.dumps(self.document))  # type: ignore[attr-defined]

    def _version(self):  # type: ignore[no-untyped-def]
        return self.document.get(VERSION_KEY, None)  # type: ignore[union-attr]

    def _deduplicate_global_parameters(self, cmd_name_key, section, key, env=DEFAULT_ENV):  # type: ignore[no-untyped-def]
        """
        In case the global parameters contains the same key-value pair with command parameters,
        we only keep the entry in global parameters

        Parameters
        ----------
        cmd_name_key : str
            key of command name

        section : str
            Specific section within the command to look into. e.g. `parameters`

        key : str
            Key to write the data under

        env : str
            Optional, Name of the environment
        """
        global_params = self.document.get(env, {}).get(DEFAULT_GLOBAL_CMDNAME, {}).get(section, {})  # type: ignore[union-attr]
        command_params = self.document.get(env, {}).get(cmd_name_key, {}).get(section, {})  # type: ignore[union-attr]
        if (
            cmd_name_key != DEFAULT_GLOBAL_CMDNAME
            and global_params
            and command_params
            and global_params.get(key)
            and global_params.get(key) == command_params.get(key)
        ):
            value = command_params.get(key)
            save_global_message = (
                f'\n\tParameter "{key}={value}" in [{env}.{cmd_name_key}.{section}] is defined as a global '
                f"parameter [{env}.{DEFAULT_GLOBAL_CMDNAME}.{section}].\n\tThis parameter will be only saved "
                f"under [{env}.{DEFAULT_GLOBAL_CMDNAME}.{section}] in {self.filepath}."
            )
            LOG.info(save_global_message)
            # Only keep the global parameter
            del self.document[env][cmd_name_key][section][key]  # type: ignore[index]

    @staticmethod
    def _version_sanity_check(version: Any) -> None:
        if not isinstance(version, float):
            raise SamConfigVersionException(f"'{VERSION_KEY}' key is not present or is in unrecognized format. ")

    @staticmethod
    def _to_key(cmd_names: Iterable[str]) -> str:
        # construct a parsed name that is of the format: a_b_c_d
        return "_".join([cmd.replace("-", "_").replace(" ", "_") for cmd in cmd_names])
