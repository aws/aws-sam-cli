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
try:  # pragma: no cover
    from pathlib import Path
except ImportError:  # pragma: no cover
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
    default_schema_file: Path
        Path to default SAMRC JSONSchema file
    default_schema: Dict
        Default JSONSchema for SAMRC validation
    """

    def __init__(self, schema=None):
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
        user_config, project_config = self.__find_config()

        user_config = self.__read_config(user_config)
        LOG.debug("Validating User SAMRC")
        self.validate_config(user_config, self.schema)

        project_config = self.__read_config(project_config)
        LOG.debug("Validating Project SAMRC")
        self.validate_config(project_config, self.schema)

        LOG.debug("User configuration loaded as")
        LOG.debug("%s", user_config)
        LOG.debug("Project configuration loaded as")
        LOG.debug("%s", project_config)

        LOG.debug("Merging configurations...")
        self.config = self.merge_config(user_config, project_config)

        return self.config

    def validate_config(self, config, schema):
        """Validate configuration against schema

        Parameters
        ----------
        config : dict
            SAMRC configuration
        schema : dict
            JSONSchema to validate against

        Raises
        -------
        jsonschema.exceptions.ValidationError
            Returned when samrc doesn't match schema provided
        """

        LOG.debug("Validating SAMRC config with given JSONSchema")
        LOG.debug("Schema used: %s", schema)
        LOG.debug("Config used: %s", config)

        jsonschema.validate(config, schema)
        LOG.debug("SAMRC looks valid!")

    def __find_config(self):
        """Looks up for user and project level config

        Returns
        -------
        Tuple
            Tuple with both configs and whether they were found

        Example
        -------
            > user_config, project_config = self.__find_config()
        """

        self.__user_config_file = Path.home().joinpath('.samrc')
        self.__project_config_file = Path.cwd().joinpath('.samrc')

        if self.__has_user_config() and self.__has_project_config():
            self.config_file = (self.__user_config_file,
                                self.__project_config_file)
        elif self.__has_project_config():
            self.config_file = None, self.__project_config_file
        elif self.__has_user_config():
            self.config_file = self.__user_config_file, None
        else:
            self.config_file = None, None

        return self.config_file

    def merge_config(self, user_config, project_config):
        """Merge project and user configuration into a single dictionary

        Creates a new configuration with both configuration merged
        it favours project level over user configuration if keys are duplicated

        NOTE
        ----
            It takes any number of nested dicts
            It overrides lists found in user_config with project_config

        Parameters
        ----------
        user_config : Dict
            User configuration (~/.samrc) found at user's home directory
        project_config : Dict
            Project configuration (.samrc) found at current directory

        Returns
        -------
        Dict
            Merged configuration
        """
        # Recursively override User config with Project config
        for key in user_config:
            if key in project_config:
                # If both keys are the same, let's check whether they have nested keys
                if isinstance(user_config[key], dict) and isinstance(project_config[key], dict):
                    self.merge_config(user_config[key], project_config[key])
                else:
                    user_config[key] = project_config[key]
                    LOG.debug("Overriding User's key %s with Project's specific value %s.", key, project_config[key])

        # Project may have unique config we need to copy over too
        # so that we can have user+project config available as one
        for key in project_config:
            if key not in user_config:
                user_config[key] = project_config[key]

        return user_config

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
        config_template = None

        if config.exists():
            config_template = yaml.safe_load(config.read_text())

        if not config_template:
            config_template = {}

        return config_template


samrc = Config().load()
app_folder = Path.home()
app_folder_project = Path.cwd()
