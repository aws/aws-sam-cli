"""
Provides global configuration helpers.
"""
import json
import logging
import uuid
import os
import threading

from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Type, TypeVar, overload
from dataclasses import dataclass

import click


LOG = logging.getLogger(__name__)


@dataclass(frozen=True, eq=True)
class ConfigEntry:
    config_key: Optional[str]
    env_var_key: Optional[str]


class DefaultEntry:
    INSTALLATION_ID = ConfigEntry("installationId", None)
    LAST_VERSION_CHECK = ConfigEntry("lastVersionCheck", None)
    TELEMETRY = ConfigEntry("telemetryEnabled", "SAM_CLI_TELEMETRY")


class GlobalConfig:
    """
    Contains helper methods for global configuration files and values. Handles
    configuration file creation, updates, and fetching in a platform-neutral way.

    Generally uses '~/.aws-sam/' or 'C:\\Users\\<user>\\AppData\\Roaming\\AWS SAM' as
    the base directory, depending on platform.
    """

    DEFAULT_CONFIG_FILENAME: str = "metadata.json"
    _DIR_INJECT_ENV_VAR: str = "__SAM_CLI_APP_DIR"

    # Static singleton instance
    __instance: Optional["GlobalConfig"] = None

    _access_lock: threading.Lock
    _config_dir: Optional[Path]
    _config_filename: Optional[str]
    _config_data: Dict[str, Any]

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = cls._instance = super().__new__(cls, *args, **kwargs)

        return GlobalConfig.__instance

    def __init__(self, config_dir: Optional[Path] = None, config_filename: Optional[str] = None):
        """
        Initializes the class, with options provided to assist with testing.

        :param config_dir: Optional, overrides the default config directory path.
        """
        self._access_lock = threading.RLock()
        self._config_dir = config_dir
        self._config_filename = config_filename
        self._load_config()

    @property
    def config_dir(self) -> Path:
        if not self._config_dir:
            if GlobalConfig._DIR_INJECT_ENV_VAR in os.environ:
                self._config_dir = Path(os.environ.get(GlobalConfig._DIR_INJECT_ENV_VAR))
            else:
                self._config_dir = Path(click.get_app_dir("AWS SAM", force_posix=True))
        return self._config_dir

    @config_dir.setter
    def config_dir(self, dir_path: Path) -> None:
        if not dir_path.is_dir():
            raise ValueError("config_dir must be a directory.")
        self._config_dir = dir_path

    @property
    def config_filename(self) -> str:
        if not self._config_filename:
            self._config_filename = GlobalConfig.DEFAULT_CONFIG_FILENAME
        return self._config_filename

    @config_filename.setter
    def config_filename(self, filename: str) -> None:
        self._config_filename = filename

    @property
    def config_path(self) -> Path:
        return Path(self.config_dir, self.config_filename)

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
        value = self.get_value(
            DefaultEntry.INSTALLATION_ID,
            default=None,
            value_type=str,
        )
        if not value:
            value = str(uuid.uuid4())
            self.set_value(DefaultEntry.INSTALLATION_ID, value)
        return value

    @property
    def telemetry_enabled(self) -> bool:
        """
        Check if telemetry is enabled for this installation. Default value of
        False. It first tries to get value from SAM_CLI_TELEMETRY environment variable. If its not set,
        then it fetches the value from config file.

        To enable telemetry, set SAM_CLI_TELEMETRY environment variable equal to integer 1 or string '1'.
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
        return self.get_value(DefaultEntry.TELEMETRY, default=None, value_type=object, is_flag=True)

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

    def set_value(self, config_entry: ConfigEntry, value: Any, is_flag: bool = False, flush: bool = True) -> None:
        with self._access_lock:
            self._set_value(config_entry, value, is_flag, flush)

    def _set_value(self, config_entry: ConfigEntry, value: Any, is_flag: bool, flush: bool) -> None:
        if config_entry.env_var_key:
            if is_flag:
                os.environ[config_entry.env_var_key] = "1" if value else "0"
            else:
                os.environ[config_entry.env_var_key] = value

        if config_entry.config_key:
            self._config_data[config_entry.config_key] = value

            if flush:
                self._flush_config()

    T = TypeVar("T")

    @overload
    def get_value(
        self,
        config_entry: ConfigEntry,
        default: T,
        value_type: Type[T],
        is_flag: bool,
        reload_config: bool,
    ) -> T:
        ...

    @overload
    def get_value(
        self,
        config_entry: ConfigEntry,
        default: None = None,
        # Defaulting to T for typing hack.
        # This default is not actually used.
        # https://github.com/python/mypy/issues/3737
        value_type: Type[T] = T,
        is_flag: bool = False,
        reload_config: bool = False,
    ) -> Optional[T]:
        ...

    def get_value(self, config_entry: ConfigEntry, default=None, value_type=object, is_flag=False, reload_config=False):
        with self._access_lock:
            return self._get_value(config_entry, default, value_type, is_flag, reload_config)

    def _get_value(
        self, config_entry: ConfigEntry, default: Optional[T], value_type: Type[T], is_flag: bool, reload_config: bool
    ) -> Optional[T]:
        value = None
        try:
            if config_entry.env_var_key:
                value = os.environ.get(config_entry.env_var_key)
                if is_flag:
                    value = value in ("1", 1)

            if value is None and config_entry.config_key:
                if reload_config:
                    self._load_config()
                value = self._config_data.get(config_entry.config_key)

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

    def _load_config(self) -> None:
        if not self.config_path.exists():
            self._config_data = {}
            return

        body = self.config_path.read_text()
        json_body = json.loads(body)
        self._config_data = json_body

    def _flush_config(self) -> None:
        json_str = json.dumps(self._config_data, indent=4)
        if not self.config_dir.exists():
            self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.config_path.write_text(json_str)
