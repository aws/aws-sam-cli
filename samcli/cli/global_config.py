"""
Provides global configuration helpers.
"""

import json
import logging
import uuid
import os
from pathlib import Path
from typing import Optional, Dict, Any

import click


LOG = logging.getLogger(__name__)

CONFIG_FILENAME = "metadata.json"
INSTALLATION_ID_KEY = "installationId"
TELEMETRY_ENABLED_KEY = "telemetryEnabled"
LAST_VERSION_CHECK_KEY = "lastVersionCheck"


class GlobalConfig:
    """
    Contains helper methods for global configuration files and values. Handles
    configuration file creation, updates, and fetching in a platform-neutral way.

    Generally uses '~/.aws-sam/' or 'C:\\Users\\<user>\\AppData\\Roaming\\AWS SAM' as
    the base directory, depending on platform.
    """

    def __init__(self, config_dir=None, installation_id=None, telemetry_enabled=None, last_version_check=None):
        """
        Initializes the class, with options provided to assist with testing.

        :param config_dir: Optional, overrides the default config directory path.
        :param installation_id: Optional, will use this installation id rather than checking config values.
        :param last_version_check: Optional, will be used to check if there is a newer version of SAM CLI available
        """
        self._config_dir = config_dir
        self._installation_id = installation_id
        self._telemetry_enabled = telemetry_enabled
        self._last_version_check = last_version_check

    @property
    def config_dir(self) -> Path:
        if not self._config_dir:
            # Internal Environment variable to customize SAM CLI App Dir. Currently used only by integ tests.
            app_dir = os.getenv("__SAM_CLI_APP_DIR")
            self._config_dir = Path(app_dir) if app_dir else Path(click.get_app_dir("AWS SAM", force_posix=True))
        return Path(self._config_dir)

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
        if self._installation_id:
            return self._installation_id
        try:
            self._installation_id = self._get_or_set_uuid(INSTALLATION_ID_KEY)
            return self._installation_id
        except (ValueError, IOError, OSError):
            return None

    @property
    def telemetry_enabled(self):
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
        if self._telemetry_enabled is not None:
            return self._telemetry_enabled

        # If environment variable is set, its value takes precedence over the value from config file.
        env_name = "SAM_CLI_TELEMETRY"
        if env_name in os.environ:
            return os.getenv(env_name) in ("1", 1)

        try:
            self._telemetry_enabled = self._get_value(TELEMETRY_ENABLED_KEY)
            return self._telemetry_enabled
        except (ValueError, IOError, OSError) as ex:
            LOG.debug("Error when retrieving telemetry_enabled flag", exc_info=ex)
            return False

    @telemetry_enabled.setter
    def telemetry_enabled(self, value):
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
        self._set_value("telemetryEnabled", value)
        self._telemetry_enabled = value

    @property
    def last_version_check(self):
        if self._last_version_check is not None:
            return self._last_version_check

        try:
            self._last_version_check = self._get_value(LAST_VERSION_CHECK_KEY)
            return self._last_version_check
        except (ValueError, IOError, OSError) as ex:
            LOG.debug("Error when retrieving _last_version_check flag", exc_info=ex)
            return None

    @last_version_check.setter
    def last_version_check(self, value):
        self._set_value(LAST_VERSION_CHECK_KEY, value)
        self._last_version_check = value

    def _get_value(self, key: str) -> Optional[Any]:
        cfg_path = self._get_config_file_path(CONFIG_FILENAME)
        if not cfg_path.exists():
            return None
        with open(str(cfg_path)) as fp:
            body = fp.read()
            json_body = json.loads(body)
            return json_body.get(key)

    def _set_value(self, key: str, value: Any) -> Any:
        cfg_path = self._get_config_file_path(CONFIG_FILENAME)
        if not cfg_path.exists():
            return self._set_json_cfg(cfg_path, key, value)
        with open(str(cfg_path)) as fp:
            body = fp.read()
            try:
                json_body = json.loads(body)
            except ValueError as ex:
                LOG.debug("Failed to decode JSON in {cfg_path}", exc_info=ex)
                raise ex
            return self._set_json_cfg(cfg_path, key, value, json_body)

    def _create_dir(self):
        """
        Creates configuration directory if it does not already exist, otherwise does nothing.
        May raise an OSError if we do not have permissions to create the directory.
        """
        self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _get_config_file_path(self, filename):
        self._create_dir()
        filepath = self.config_dir.joinpath(filename)
        return filepath

    def _get_or_set_uuid(self, key):
        """
        Special logic method for when we want a UUID to always be present, this
        method behaves as a getter with side effects. Essentially, if the value
        is not present, we will set it with a generated UUID.

        If we have multiple such values in the future, a possible refactor is
        to just be _get_or_set_value, where we also take a default value as a
        parameter.
        """
        cfg_value = self._get_value(key)
        if cfg_value is not None:
            return cfg_value
        return self._set_value(key, str(uuid.uuid4()))

    @staticmethod
    def _set_json_cfg(filepath: Path, key: str, value: Any, json_body: Optional[Dict] = None) -> Any:
        """
        Special logic method to add a value to a JSON configuration file. This
        method will write a new version of the file in question, so it will
        either write a new file with only the first config value, or if a JSON
        body is provided, it will upsert starting from that JSON body.
        """
        json_body = json_body or {}
        json_body[key] = value
        file_body = json.dumps(json_body, indent=4) + "\n"
        try:
            with open(str(filepath), "w") as f:
                f.write(file_body)
        except IOError as ex:
            LOG.debug("Error writing to {filepath}", exc_info=ex)
            raise ex
        return value
