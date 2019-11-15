import os
import logging
import tomlkit

from pathlib import Path

LOG = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE_NAME = "samconfig.toml"
DEFAULT_ENV = "default"


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
        """

        env = env or DEFAULT_ENV

        self._read()
        return self.document[env][self._to_key(cmd_names)][section]

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
        """

        self._read()
        self.document[env][self._to_key(cmd_names)][section][key] = value

    def flush(self):
        self._write()

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
        else:
            return os.getcwd()

    def _read(self):
        if self.document:
            return self.document

        txt = self.filepath.read_text()
        self.document = tomlkit.loads(txt)

    def _write(self):
        if not self.document:
            return

        self.filepath.write_text(tomlkit.dumps(self.document))

    @staticmethod
    def _to_key(cmd_names):
        # construct a parsed name that is of the format: a_b_c_d
        return "_".join(reversed([cmd.replace("-", "_").replace(" ", "_") for cmd in cmd_names]))
