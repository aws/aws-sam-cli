"""
Module for preloading values from toml file
so a question can use one of the preloaded values by specifying a key path in its "default" attribute.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

import tomlkit

LOG = logging.getLogger(__name__)

PRELOAD_KEY = "$PRELOAD"


def preload_values_from_toml_file(toml_file_path: Path, context: Dict) -> Dict:
    """
    Read and parse the content of the toml file specified with toml_file_path,
    loads its all value under "key_path" into the context object under the key "$PRELOAD."

    For example, if the toml file contains:
    (root):
      - Env0
          - SectionA
            - SubSectionB
              - KeyC: a-string-value-c
              - KeyD: a-string-value-d
          - SectionE
            - SubSectionF
              - KeyG: a-string-value-g

    and key_path = ["Env0", "SectionA"]

    preload() will return a new dict combining "context" dict and this:
    {
        "$PRELOAD": {
            "Env0": {
                "SectionA": {
                    "SubSectionB": {
                        "KeyC": "a-string-value-c",
                        "KeyD": "a-string-value-d",
                    }
                }
                "SectionE": ...
            }
        }
    }


    Parameters
    ----------
    toml_file_path
        toml file path
    context
        The cookiecutter context

    Returns
    -------
    A dictionary combining context & { "$PRELOAD": <preload values> }
    """
    try:
        txt = toml_file_path.read_text()
        document = tomlkit.loads(txt)
    except OSError:
        LOG.debug("Toml file %s does not exist, no values will be preloaded.", toml_file_path)
        document = tomlkit.document()

    combined_context = context.copy()
    combined_context.update({PRELOAD_KEY: document})
    return combined_context


def get_preload_value(context: Dict, key_path: Optional[List[str]]) -> Optional[Any]:
    """
    Get preload value from the cookiecutter context object (with preloaded values)
    if the key path does not exist in the context object, return None

    Parameters
    ----------
    context
        The cookiecutter context
    key_path
        The key path for looking up the value

    Returns
    -------
    The value, None if no value is found
    """
    preload_values = context.get(PRELOAD_KEY, {})

    node = preload_values
    for key in key_path or []:
        node = node.get(key)
        if node is None:
            return None

    return node
