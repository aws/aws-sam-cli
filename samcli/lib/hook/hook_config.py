"""Hook Package Config"""
import json
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional

import jsonschema
from .exceptions import InvalidHookPackageConfigException

class HookFunctionalityParam(NamedTuple):
    long_name: str
    short_name: str
    description: str
    mandatory: bool
    type: str


class HookFunctionality(NamedTuple):
    entry_script: str
    parameters: Optional[List[HookFunctionalityParam]]

    @property
    def mandatory_parameters(self) -> List[HookFunctionalityParam]:
        return [params for params in self.parameters if params.mandatory]


class HookPackageConfig:
    _package_dir: Path
    _config: Dict

    CONFIG_FILENAME = "Config.json"
    JSON_SCHEMA_PATH = Path(__file__).parent / "hook_config_schema.json"

    def __init__(self, package_dir: Path):
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
            params = [HookFunctionalityParam(**param) for param in func_dict.get("parameters", [])]
            config_dict["functionalities"][func] = HookFunctionality(func_dict["entry_script"], params)
        self._config = config_dict

    @property
    def jsonschema(self) -> Dict:
        with HookPackageConfig.JSON_SCHEMA_PATH.open("r", encoding="utf-8") as f:
            jsonschema_dict = json.load(f)
        return jsonschema_dict

    @property
    def package_dir(self) -> Path:
        return self._package_dir

    @property
    def package_id(self) -> str:
        return self._config["hook_package_id"]

    @property
    def use_case(self) -> str:
        return self._config["hook_use_case"]

    @property
    def version(self) -> str:
        return self._config["version"]

    @property
    def specification(self) -> str:
        return self._config["hook_specification"]

    @property
    def description(self) -> str:
        return self._config["description"]

    @property
    def functionalities(self) -> Dict[str, HookFunctionality]:
        return self._config["functionalities"]
