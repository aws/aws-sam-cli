"""
Module for creating default samconfig.toml files after initialize a sample app
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, List

from samcli.lib.config.samconfig import DEFAULT_GLOBAL_CMDNAME, SamConfig
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
    command: List[str]


class DefaultSamconfig:
    def __init__(self, path, package_type, project_name):
        self._path = path
        self._package_type = package_type
        self._project_name = project_name
        self._config = SamConfig(path)
        self._defaults = [
            Default(
                writing_type=WritingType.Both,
                key="stack_name",
                value=f"{self._project_name}",
                command=[f"{DEFAULT_GLOBAL_CMDNAME}"],
            ),
            Default(writing_type=WritingType.ZIP, key="cached", value=True, command=["build"]),
            Default(writing_type=WritingType.Both, key="parallel", value=True, command=["build"]),
            Default(writing_type=WritingType.Both, key="lint", value=True, command=["validate"]),
            Default(writing_type=WritingType.Both, key="capabilities", value="CAPABILITY_IAM", command=["deploy"]),
            Default(writing_type=WritingType.Both, key="confirm_changeset", value=True, command=["deploy"]),
            # NOTE(sriram-mv): Template is still uploaded to s3 regardless of Package Type.
            Default(writing_type=WritingType.Both, key="resolve_s3", value=True, command=["package"]),
            Default(writing_type=WritingType.Both, key="resolve_s3", value=True, command=["deploy"]),
            Default(writing_type=WritingType.Image, key="resolve_image_repos", value=True, command=["deploy"]),
            Default(writing_type=WritingType.Both, key="watch", value=True, command=["sync"]),
            Default(
                writing_type=WritingType.Both, key="warm_containers", value="EAGER", command=["local", "start-api"]
            ),
            Default(
                writing_type=WritingType.Both, key="warm_containers", value="EAGER", command=["local", "start-lambda"]
            ),
        ]

    def create(self) -> None:
        """
        Create the default samconfig.toml file based on predefined defaults.
        """
        self._config.put_comment(MORE_INFO_COMMENT)
        self._write_defaults(self._defaults)
        self._config.flush()

    def _write_defaults(self, defaults: List[Default]) -> None:
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
            # TODO(sriram-mv): Comment and write the other default even if it's not currently applicable.
            if default.writing_type == WritingType.Both or default.writing_type.value == self._package_type:
                self._config.put(cmd_names=default.command, section="parameters", key=default.key, value=default.value)
