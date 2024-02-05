"""Hook Package Config"""

import json
from pathlib import Path
from typing import Dict, NamedTuple, Optional, cast

import jsonschema

from .exceptions import InvalidHookPackageConfigException


class HookFunctionality(NamedTuple):
    """
    A class to represent a hook functionality (e.g. prepare)
    """

    entry_method: Dict[str, str]

    @property
    def module(self) -> str:
        return self.entry_method["module"]

    @property
    def method(self) -> str:
        return self.entry_method["method"]


class HookPackageConfig:
    """
    A class to represent a hook package. Upon instantiation, it also validate the config against a json schema.
    """

    _package_dir: Path
    _config: Dict

    CONFIG_FILENAME = "Config.json"
    JSON_SCHEMA_PATH = Path(__file__).parent / "hook_config_schema.json"

    def __init__(self, package_dir: Path):
        """
        Parameters
        ----------
        package_dir: Path
            The path of the hook package directory
        """
        self._package_dir = package_dir
        config_loc = package_dir / self.CONFIG_FILENAME
        if not config_loc.is_file():
            raise InvalidHookPackageConfigException(f"{config_loc} is not a file or does not exist")

        with config_loc.open("r", encoding="utf-8") as f:
            config_dict = json.load(f)

        try:
            jsonschema.validate(config_dict, self.jsonschema)
        except jsonschema.ValidationError as e:
            raise InvalidHookPackageConfigException(f"Invalid Config.json - {e}") from e

        for func, func_dict in config_dict["functionalities"].items():
            config_dict["functionalities"][func] = HookFunctionality(func_dict["entry_method"])
        self._config = config_dict

    @property
    def jsonschema(self) -> Dict:
        with HookPackageConfig.JSON_SCHEMA_PATH.open("r", encoding="utf-8") as f:
            jsonschema_dict = json.load(f)
        return cast(Dict, jsonschema_dict)

    @property
    def name(self) -> str:
        return cast(str, self._config["hook_name"])

    @property
    def use_case(self) -> str:
        return cast(str, self._config["hook_use_case"])

    @property
    def version(self) -> str:
        return cast(str, self._config["version"])

    @property
    def specification(self) -> str:
        return cast(str, self._config["hook_specification"])

    @property
    def description(self) -> Optional[str]:
        return cast(str, self._config.get("description"))

    @property
    def functionalities(self) -> Dict[str, HookFunctionality]:
        return cast(Dict[str, HookFunctionality], self._config["functionalities"])

    @property
    def iac_framework(self) -> str:
        return cast(str, self._config.get("iac_framework", ""))
