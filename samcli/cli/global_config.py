"""
Provides global configuration helpers.
"""
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, cast, overload

import click

from samcli.lib.utils.hash import str_checksum

LOG = logging.getLogger(__name__)


@dataclass(frozen=True, eq=True)
class ConfigEntry:
    """Data class for storing configuration related keys"""

    config_key: Optional[str]
    env_var_key: Optional[str]
    persistent: bool = True


class DefaultEntry:
    """Set of default configuration entries integrated with GlobalConfig"""

    INSTALLATION_ID = ConfigEntry("installationId", None)
    LAST_VERSION_CHECK = ConfigEntry("lastVersionCheck", None)
    TELEMETRY = ConfigEntry("telemetryEnabled", "SAM_CLI_TELEMETRY")
    ACCELERATE_OPT_IN_STACKS = ConfigEntry("accelerateOptInStacks", None)


class Singleton(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cls.__instance = None

    def __call__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__call__(*args, **kwargs)
        return cls.__instance


class GlobalConfig(metaclass=Singleton):
    """
    A singleton for accessing configurations from environmental variables and
    configuration file. Singleton is used to enforce immutability, access locking,
    and rapid configuration modification.

    Generally uses '~/.aws-sam/' or 'C:\\Users\\<user>\\AppData\\Roaming\\AWS SAM' as
    the base directory, depending on platform.
    """

    DEFAULT_CONFIG_FILENAME: str = "metadata.json"

    # Env var for injecting dir in integration tests
    _DIR_INJECTION_ENV_VAR: str = "__SAM_CLI_APP_DIR"

    # Static singleton instance

    _access_lock: threading.RLock
    _config_dir: Optional[Path]
    _config_filename: Optional[str]
    # Dictionary storing config data mapped directly to the content of the config file
    _config_data: Optional[Dict[str, Any]]
    # config_keys that should be flushed to file
    _persistent_fields: List[str]

    def __init__(self):
        """__init__ should only be called once due to Singleton metaclass"""
        self._access_lock = threading.RLock()
        self._config_dir = None
        self._config_filename = None
        self._config_data = None
        self._persistent_fields = list()

    @property
    def config_dir(self) -> Path:
        """
        Returns
        -------
        Path
            Path object for the configuration directory.
        """
        if not self._config_dir:
            if GlobalConfig._DIR_INJECTION_ENV_VAR in os.environ:
                # Set dir to the one specified in _DIR_INJECTION_ENV_VAR environmental variable
                # This is used for existing integration tests
                env_var_path = os.environ.get(GlobalConfig._DIR_INJECTION_ENV_VAR)
                self._config_dir = Path(cast(str, env_var_path))
            else:
                self._config_dir = Path(click.get_app_dir("AWS SAM", force_posix=True))
        return self._config_dir

    @config_dir.setter
    def config_dir(self, dir_path: Path) -> None:
        """
        Parameters
        ----------
        dir_path : Path
            Directory path object for the configuration.

        Raises
        ------
        ValueError
            ValueError will be raised if the path is not a directory.
        """
        if not dir_path.is_dir():
            raise ValueError("config_dir must be a directory.")
        self._config_dir = dir_path
        self._config_data = None

    @property
    def config_filename(self) -> str:
        """
        Returns
        -------
        str
            Filename for the configuration.
        """
        if not self._config_filename:
            self._config_filename = GlobalConfig.DEFAULT_CONFIG_FILENAME
        return self._config_filename

    @config_filename.setter
    def config_filename(self, filename: str) -> None:
        self._config_filename = filename
        self._config_data = None

    @property
    def config_path(self) -> Path:
        """
        Returns
        -------
        Path
            Path object for the configuration file (config_dir + config_filename).
        """
        return Path(self.config_dir, self.config_filename)

    T = TypeVar("T")

    # Overloads are only used for type hinting.
    # Overload for case where is_flag is set
    @overload
    def get_value(
        self,
        config_entry: ConfigEntry,
        default: bool,
        value_type: Type[bool],
        is_flag: bool,
        reload_config: bool = False,
    ) -> bool:
        ...

    # Overload for case where type is specified
    @overload
    def get_value(
        self,
        config_entry: ConfigEntry,
        default: Optional[T] = None,
        value_type: Type[T] = T,  # type: ignore
        is_flag: bool = False,
        reload_config: bool = False,
    ) -> Optional[T]:
        ...

    # Overload for case where type is not specified and default to object
    @overload
    def get_value(
        self,
        config_entry: ConfigEntry,
        default: Any = None,
        value_type: object = object,
        is_flag: bool = False,
        reload_config: bool = False,
    ) -> Any:
        ...

    def get_value(
        self,
        config_entry,
        default=None,
        value_type=object,
        is_flag=False,
        reload_config=False,
    ) -> Any:
        """Get the corresponding value of a configuration entry.

        Parameters
        ----------
        config_entry : ConfigEntry
            Configuration entry for which the value will be loaded.
        default : value_type, optional
            The default value to be returned if the configuration does not exist,
            encountered an error, or in the incorrect type.
            By default None
        value_type : Type, optional
            The type of the value that should be expected.
            If the value is not this type, default will be returned.
            By default object
        is_flag : bool, optional
            If is_flag is True, then env var will be set to "1" or "0" instead of boolean values.
            This is useful for backward compatibility with the old configuration format where
            configuration file and env var has different values.
            By default False
        reload_config : bool, optional
            Whether configuration file should be reloaded before getting the value.
            By default False

        Returns
        -------
        [value_type]
            Value in the type specified by value_type
        """
        with self._access_lock:
            return self._get_value(config_entry, default, value_type, is_flag, reload_config)

    def _get_value(
        self,
        config_entry: ConfigEntry,
        default: Optional[T],
        value_type: Type[T],
        is_flag: bool,
        reload_config: bool,
    ) -> Optional[T]:
        """get_value without locking. Non-thread safe."""
        value: Any = None
        try:
            if config_entry.env_var_key:
                value = os.environ.get(config_entry.env_var_key)
                if value is not None and is_flag:
                    value = value == "1"

            if value is None and config_entry.config_key:
                if reload_config or self._config_data is None:
                    self._load_config()
                value = cast(dict, self._config_data).get(config_entry.config_key)

            if value is None or not isinstance(value, value_type):
                return default
        except (ValueError, OSError) as ex:
            LOG.debug(
                "Error when retrieving config_key: %s env_var_key: %s",
                config_entry.config_key,
                config_entry.env_var_key,
                exc_info=ex,
            )
            return default

        return value

    def set_value(self, config_entry: ConfigEntry, value: Any, is_flag: bool = False, flush: bool = True) -> None:
        """Set the value of a configuration. The associated env var will be updated as well.

        Parameters
        ----------
        config_entry : ConfigEntry
            Configuration entry to be set
        value : Any
            Value of the configuration
        is_flag : bool, optional
            If is_flag is True, then env var will be set to "1" or "0" instead of boolean values.
            This is useful for backward compatibility with the old configuration format where
            configuration file and env var has different values.
            By default False
        flush : bool, optional
            Should the value be written to configuration file, by default True
        """
        with self._access_lock:
            self._set_value(config_entry, value, is_flag, flush)

    def _set_value(self, config_entry: ConfigEntry, value: Any, is_flag: bool, flush: bool) -> None:
        """set_value without locking. Non-thread safe."""
        if config_entry.env_var_key:
            if is_flag:
                os.environ[config_entry.env_var_key] = "1" if value else "0"
            else:
                os.environ[config_entry.env_var_key] = value

        if config_entry.config_key:
            if self._config_data is None:
                self._load_config()
            cast(dict, self._config_data)[config_entry.config_key] = value

            if config_entry.persistent:
                self._persistent_fields.append(config_entry.config_key)
            elif config_entry.config_key in self._persistent_fields:
                self._persistent_fields.remove(config_entry.config_key)

            if flush:
                self._write_config()

    def _load_config(self) -> None:
        """Reload configurations from file and populate self._config_data"""
        if not self.config_path.exists():
            self._config_data = {}
            return
        try:
            body = self.config_path.read_text()
            json_body = json.loads(body)
            self._config_data = json_body
            # Default existing fields to be persistent
            # so that they will be kept when flushed back
            for key in json_body:
                self._persistent_fields.append(key)
        except (OSError, ValueError) as ex:
            LOG.warning(
                "Error when loading global config file: %s",
                self.config_path,
                exc_info=ex,
            )
            self._config_data = {}

    def _write_config(self) -> None:
        """Write configurations in self._config_data to file"""
        if not self._config_data:
            return
        config_data = {key: value for (key, value) in self._config_data.items() if key in self._persistent_fields}
        try:
            json_str = json.dumps(config_data, indent=4)
            if not self.config_dir.exists():
                self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.config_path.write_text(json_str)
        except (OSError, ValueError) as ex:
            LOG.warning(
                "Error when writing global config file: %s",
                self.config_path,
                exc_info=ex,
            )

    @property
    def installation_id(self):
        """
        Returns the installation UUID for this AWS SAM CLI installation. If the
        installation id has not yet been set, it will be set before returning.

        Examples
        --------

        >>> gc = GlobalConfig()
        >>> gc.installation_id
        "7b7d4db7-2f54-45ba-bf2f-a2cbc9e74a34"

        >>> gc = GlobalConfig()
        >>> gc.installation_id
        None

        Returns
        -------
        A string containing the installation UUID, or None in case of an error.
        """
        value = self.get_value(DefaultEntry.INSTALLATION_ID, default=None, value_type=str, reload_config=True)
        if not value:
            value = str(uuid.uuid4())
            self.set_value(DefaultEntry.INSTALLATION_ID, value)
        return value

    @property
    def telemetry_enabled(self) -> Optional[bool]:
        """
        Check if telemetry is enabled for this installation. Default value of
        False. It first tries to get value from SAM_CLI_TELEMETRY environment variable. If its not set,
        then it fetches the value from config file.

        To enable telemetry, set SAM_CLI_TELEMETRY environment variable equal to string '1'.
        All other values including words like 'True', 'true', 'false', 'False', 'abcd' etc will disable Telemetry

        Examples
        --------

        >>> gc = GlobalConfig()
        >>> gc.telemetry_enabled
        True

        Returns
        -------
        Boolean flag value. True if telemetry is enabled for this installation,
        False otherwise.
        """
        return self.get_value(DefaultEntry.TELEMETRY, default=None, value_type=bool, is_flag=True)

    @telemetry_enabled.setter
    def telemetry_enabled(self, value: bool) -> None:
        """
        Sets the telemetry_enabled flag to the provided boolean value.

        Examples
        --------
        >>> gc = GlobalConfig()
        >>> gc.telemetry_enabled
        False
        >>> gc.telemetry_enabled = True
        >>> gc.telemetry_enabled
        True

        Raises
        ------
        IOError
            If there are errors opening or writing to the global config file.

        JSONDecodeError
            If the config file exists, and is not valid JSON.
        """
        self.set_value(DefaultEntry.TELEMETRY, value, is_flag=True, flush=True)

    @property
    def last_version_check(self) -> Optional[float]:
        return self.get_value(DefaultEntry.LAST_VERSION_CHECK, value_type=float)

    @last_version_check.setter
    def last_version_check(self, value: float):
        self.set_value(DefaultEntry.LAST_VERSION_CHECK, value)

    def is_accelerate_opt_in_stack(self, template_file: str, stack_name: str) -> bool:
        """
        Returns True, if current folder with stack name is been accepted to use sam sync before.
        Returns False, if this is first time that user runs sam sync with current folder and given stack name.
        """
        accelerate_opt_in_stacks = (
            self.get_value(DefaultEntry.ACCELERATE_OPT_IN_STACKS, value_type=list, default=[]) or []
        )
        return str_checksum(template_file + stack_name) in accelerate_opt_in_stacks

    def set_accelerate_opt_in_stack(self, template_file: str, stack_name: str) -> None:
        """
        Stores current folder and stack name into config, so that next time that user runs sam sync, they don't need
        to accept warning message again.
        """
        accelerate_opt_in_stacks = (
            self.get_value(DefaultEntry.ACCELERATE_OPT_IN_STACKS, value_type=list, default=[]) or []
        )
        accelerate_opt_in_stacks.append(str_checksum(template_file + stack_name))
        self.set_value(DefaultEntry.ACCELERATE_OPT_IN_STACKS, accelerate_opt_in_stacks)
