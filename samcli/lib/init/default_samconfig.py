"""
Module for creating default samconfig.toml files after initialize a sample app
"""
from enum import Enum
from dataclasses import dataclass
from typing import Any, List

from samcli.lib.config.samconfig import SamConfig
from samcli.lib.utils.packagetype import IMAGE, ZIP

MORE_INFO_COMMENT = """More information about the configuration file can be found here:
# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html"""


class WritingType(Enum):
    ZIP = ZIP
    Image = IMAGE
    Both = "BOTH"


@dataclass
class Default:
    writing_type: WritingType
    key: str
    value: Any


class DefaultSamconfig:
    def __init__(self, path, package_type, project_name):
        self._path = path
        self._package_type = package_type
        self._project_name = project_name
        self._config = SamConfig(path)

    def create(self) -> None:
        """
        Create the default samconfig.toml file based on predefined defaults.
        """
        self._config.put_comment(MORE_INFO_COMMENT)
        self._write_global()
        self._write_build()
        self._write_sync()
        self._write_local_start_api()
        self._write_local_start_lambda()
        self._write_deploy()
        self._config.flush()

    def _write(self, defaults: List[Default], command: List[str]) -> None:
        """
        Helper method to create a default samconfig property.

        Parameters
        ----------
        defaults: List[Default]
            A list of default properties for a specific command to be written to the samconfig file
        command: List[str]
            List of strings representing the command to be added to the samconfig file
        """
        for default in defaults:
            if default.writing_type == WritingType.Both or default.writing_type.value == self._package_type:
                self._config.put(cmd_names=command, section="parameters", key=default.key, value=default.value)

    def _write_global(self) -> None:
        """
        Write global default properties to samconfig.toml
        """
        defaults = [Default(writing_type=WritingType.Both, key="stack_name", value=f"sam-app-{self._project_name}")]
        self._write(defaults=defaults, command=["global"])

    def _write_build(self) -> None:
        """
        Write build default properties to samconfig.toml
        """
        defaults = [
            Default(writing_type=WritingType.ZIP, key="cached", value=True),
            Default(writing_type=WritingType.Both, key="parallel", value=True),
        ]
        self._write(defaults=defaults, command=["build"])

    def _write_deploy(self) -> None:
        """
        Write deploy default properties to samconfig.toml
        """
        defaults = [
            Default(writing_type=WritingType.Both, key="capabilities", value="CAPABILITY_IAM"),
            Default(writing_type=WritingType.Both, key="confirm_changeset", value=True),
            Default(writing_type=WritingType.ZIP, key="resolve_s3", value=True),
            Default(writing_type=WritingType.Image, key="resolve_image_repos", value=True),
        ]
        self._write(defaults=defaults, command=["deploy"])

    def _write_sync(self) -> None:
        """
        Write sync default properties to samconfig.toml
        """
        defaults = [Default(writing_type=WritingType.Both, key="watch", value=True)]
        self._write(defaults=defaults, command=["sync"])

    def _write_local_start_api(self) -> None:
        """
        Write local start-api default properties to samconfig.toml
        """
        defaults = [Default(writing_type=WritingType.Both, key="warm_containers", value="EAGER")]
        self._write(defaults=defaults, command=["local", "start-api"])

    def _write_local_start_lambda(self) -> None:
        """
        Write local start-lambda default properties to samconfig.toml
        """
        defaults = [Default(writing_type=WritingType.Both, key="warm_containers", value="EAGER")]
        self._write(defaults=defaults, command=["local", "start-lambda"])
