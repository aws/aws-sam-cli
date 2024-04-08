"""
All-in-one metadata about runtimes
"""

import itertools
import os
import pathlib
import re
from typing import List

from samcli.lib.runtimes.base import (
    Runtime,
    init_runtimes,
    lambda_images_runtimes_map,
    provided_runtimes,
    runtime_dependency_template_mapping,
    sam_runtime_to_schemas_code_lang_mapping,
)

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent.parent)
_templates = os.path.join(_init_path, "lib", "init", "templates")
_lambda_images_templates = os.path.join(_init_path, "lib", "init", "image_templates")

RUNTIME_DEP_TEMPLATE_MAPPING = runtime_dependency_template_mapping(list(Runtime))


def get_local_manifest_path():
    return pathlib.Path(_init_path, "lib", "init", "local_manifest.json")


def get_local_lambda_images_location(mapping, runtime):
    dir_name = os.path.basename(mapping["init_location"])
    if dir_name.endswith("-lambda-image"):
        return os.path.join(_lambda_images_templates, runtime, dir_name)

    return os.path.join(_lambda_images_templates, runtime, dir_name + "-lambda-image")


SUPPORTED_DEP_MANAGERS: List[str] = sorted(
    list(
        set(
            {
                c.get("dependency_manager")  # type: ignore
                for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
                if c.get("dependency_manager")
            }
        )
    )
)

INIT_RUNTIMES = init_runtimes(list(Runtime))
LAMBDA_IMAGES_RUNTIMES_MAP = lambda_images_runtimes_map(list(Runtime))
LAMBDA_IMAGES_RUNTIMES: List = sorted(list(set(LAMBDA_IMAGES_RUNTIMES_MAP.values())))
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = sam_runtime_to_schemas_code_lang_mapping(list(Runtime))
PROVIDED_RUNTIMES = provided_runtimes(list(Runtime))


def is_custom_runtime(runtime):
    """
    validated if a runtime is custom or not
    Parameters
    ----------
    runtime : str
        runtime to be
    Returns
    -------
    _type_
        _description_
    """
    if not runtime:
        return False
    provided_runtime = get_provided_runtime_from_custom_runtime(runtime)
    return runtime in PROVIDED_RUNTIMES or bool(provided_runtime in PROVIDED_RUNTIMES)


def get_provided_runtime_from_custom_runtime(runtime):
    """
    Gets the base lambda runtime for which a custom runtime is based on
    Example:
    rust (provided.al2) --> provided.al2
    java11 --> None

    Parameters
    ----------
    runtime : str
        Custom runtime or Lambda runtime

    Returns
    -------
    str
        returns the base lambda runtime for which a custom runtime is based on
    """
    base_runtime_list = re.findall(r"\(([^()]+)\)", runtime)
    return base_runtime_list[0] if base_runtime_list else None
