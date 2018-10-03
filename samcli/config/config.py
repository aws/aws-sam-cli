"""
Config module that reads .samrc definition
"""

import logging
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
        Schema for Configuration validation
        {
            "field_name": type
            "required": ["field_name"]
        }
    """

    def __init__(self, *schema):
        self.__user_config_file = None
        self.__project_config_file = None
        self.config_file = None
        self.config = None
        self.default_schema = {
            "aws_region": str,
            "aws_profile": str,
            "default_port": int,
            "debug_port": int,
            "template": str,
            "required": []
        }
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
            LOG.debug("Found more than one SAMRC")
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
            Schema to validate against

        Returns
        -------
        Boolean
        """

        if schema is not None and isinstance(schema, dict):
            if not self.__has_required_config(config, schema):
                return False
            if not self.__has_correct_values(config, schema):
                return False

        LOG.debug("SAMRC looks valid based on schema provided")
        LOG.debug("Schema: %s", schema)

        return True

    def __has_correct_values(self, config, schema):
        """Recursively check config against schema

        Parameters
        ----------
        config : dict
            SAMRC configuration
        schema : dict
            Schema to validate against

        Returns
        -------
        Boolean
        """
        LOG.debug("Ensuring SAMRC has values defined by schema provided")
        for key, value in schema.items():
            if isinstance(value, dict):  # if nested check on recursion
                return self.__has_correct_values(config[key], value)
            else:
                if key in config:  # Only check for value for those available
                    if not isinstance(config[key], value):
                        # Check for best course of action (ERR message upstream,custom Exception formatting, etc.)
                        LOG.debug("[!] SAMRC key %s has value %s. Expected %s", key, config[key], value)
                        return False

        return True

    def __has_required_config(self, config, schema):
        """Ensure explicit keys exist in configuration

        Parameters
        ----------
        config : dict
            SAMRC configuration
        schema : dict
            Schema to validate against

        Returns
        -------
        Boolean
        """

        LOG.debug("Confirming whether required configuration is in SAMRC")
        if 'required' in schema and schema['required']:
            required = schema.pop('required')
            if isinstance(required, list):
                for field in required:
                    if field not in config:
                        LOG.debug("[!] SAMRC key %s is missing and it is required.", field)
                        return False

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
