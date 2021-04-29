import json
from collections import OrderedDict
from typing import Any, Optional


def resolve_parameter(res: Any, parameter: str, value: str) -> Any:
    if isinstance(res, str):
        res = res.replace(parameter, value)
    elif isinstance(res, list):
        for item in res:
            resolve_parameter(item, parameter, value)
    elif isinstance(res, dict):
        for key, v in res.items():
            res[key] = resolve_parameter(v, parameter, value)
    return res


def read_json_file(filepath: str, parameter: Optional[str] = None, value: Optional[str] = None) -> Any:
    with open(filepath, "r") as f:
        # res = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(f.read())
        res = json.loads(f.read())
        if parameter is not None and value is not None:
            resolve_parameter(res, parameter, value)
        return res
