"""
Config module that reads .samrc definition
"""

import logging
import json

import jsonschema
import yaml

# This is an attempt to do a controlled import. pathlib is in the
# Python standard library starting at 3.4. This will import pathlib2,
# which is a backport of the Python Standard Library pathlib
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

LOG = logging.getLogger(__name__)


class Config(object):
    """ Class for SAM Run control (.samrc) Configuration

    At the moment, .samrc can either be found at user's home directory
    or at the project level (current dir). It also provides methods
    to merge configurations if both are found in place.

    Config exposes config_file (attribute) that is being used for configuration
    and load (method) that can also be used to refresh configuration
    if already initialized.

    Example
    -------

        > config = Config().load()
        > schema = {
            "field_name": str,
            "field_name2": int,
            "required": ["field_name2"]
        }
        > config = Config().load(schema=schema)

    Attributes
    ----------
    __user_config_file : Path
        User configuration file path (.samrc).
    __project_config_file : Path
        Project configuration file path (current dir/.samrc).
    config_file : dict
        Path to configuration file chosen.
    config: dict
        SAMRC configuration
    schema: dict
        JSONSchema for Configuration validation
    """

    def __init__(self, *schema):
        self.__user_config_file = None
        self.__project_config_file = None
        self.config_file = None
        self.config = None
        self.default_schema_file = Path(__file__).parent.joinpath('schema.json')
        self.default_schema = json.load(Path.open(self.default_schema_file))
        self.schema = self.default_schema if not schema else schema

    def load(self):
        """Load configuration file and expose as a dictionary

        Returns
        -------
        Dict
            SAMRC configuration
        """

        LOG.debug("Looking for SAMRC before attempting to load")
        possible_configs = self.__find_config()
        if possible_configs is not None and isinstance(possible_configs, tuple):
            config_to_be_merged = [self.__read_config(config) for config in possible_configs]
            LOG.debug("Found more than one SAMRC; Merging...")
            LOG.debug("%s", possible_configs)
            self.config = self.merge_config(*config_to_be_merged)
        elif possible_configs is not None:
            LOG.debug("Found one SAMRC")
            LOG.debug("%s", possible_configs)
            self.config = self.__read_config(possible_configs)

        if self.config is not None:
            LOG.debug("SAMRC is ready to be validated")
            LOG.debug("%s", self.config)
            if not self.validate_config(self.config, self.schema):
                raise ValueError("[!] Configuration is invalid!!")

        return self.config

    def validate_config(self, config, schema):
        """Validate configuration against schema

        Parameters
        ----------
        config : dict
            SAMRC configuration
        schema : dict
            JSONSchema to validate against

        Returns
        -------
        Boolean
        """

        if schema is not None and isinstance(schema, dict):
            LOG.debug("Validating SAMRC config with given JSONSchema")
            jsonschema.validate(config, schema)

        LOG.debug("SAMRC looks valid!")
        LOG.debug("Schema used: %s", schema)
        LOG.debug("Config used: %s", config)

        return True

    def __find_config(self):
        """Looks up for user and project level config

        Returns
        -------
        [Tuple, String]
            Tuple if multiple config files are found otherwise a String
        """

        self.__user_config_file = Path.home().joinpath('.samrc')
        self.__project_config_file = Path.cwd().joinpath('.samrc')

        if self.__has_user_config() and self.__has_project_config():
            self.config_file = (self.__project_config_file,
                                self.__user_config_file)
        elif self.__has_project_config():
            self.config_file = self.__project_config_file
        elif self.__has_user_config():
            self.config_file = self.__user_config_file

        return self.config_file

    def merge_config(self, project_config, user_config):
        """Merge project and user configuration into a single dictionary

        Creates a new configuration with both configuration merged
        it favours project level over user configuration if keys are duplicated

        Parameters
        ----------
        project_config : Dict
            Project configuration (.samrc) found at current directory
        user_config : Dict
            User configuration (~/.samrc) found at user's home directory

        Returns
        -------
        Dict
            Merged configuration
        """

        new_config = user_config.copy()
        new_config.update(project_config)

        return new_config

    def __has_user_config(self):
        """Confirm whether user configuration exists

        Returns
        -------
        Boolean
        """

        return Path(self.__user_config_file).is_file()

    def __has_project_config(self):
        """Confirm whether project configuration exists

        Returns
        -------
        Boolean
        """

        return Path(self.__project_config_file).is_file()

    def __read_config(self, config):
        """Parse given YAML configuration

        Returns
        -------
        Dict
            Parsed YAML configuration as dictionary
        """
        config = Path(config)

        return yaml.safe_load(config.read_text())


samrc = Config().load()
app_folder = Path.home()
app_folder_project = Path.cwd()
