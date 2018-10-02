"""
Config module that reads .samrc definition
"""

import yaml

# This is an attempt to do a controlled import. pathlib is in the
# Python standard library starting at 3.4. This will import pathlib2,
# which is a backport of the Python Standard Library pathlib
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


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

    """

    def __init__(self):
        self.__user_config_file = ""
        self.__project_config_file = ""
        self.config_file = ()
        self.config = {}

    def load(self):
        """Load configuration file and expose as a dictionary

        Returns
        -------
        Dict
            SAMRC configuration
        """

        possible_configs = self.__find_config()

        if isinstance(possible_configs, tuple):
            config_to_be_merged = [self.__read_config(config)
                                   for config in possible_configs]
            self.config = self.merge_config(*config_to_be_merged)
        else:
            self.config = self.__read_config(possible_configs)

        return self.config

    def validate_config(self, config, schema):
        """ Validate config against schema - Not implemented yet"""
        raise Exception("Not implemented yet")

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
            self.config_file = self.__project_config_file, self.__user_config_file
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

        _config = Path(config)

        return yaml.safe_load(_config.read_text())


samrc = Config().load()
