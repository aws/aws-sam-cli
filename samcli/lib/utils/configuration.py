""" Read info from config.json file"""

import json
from pathlib import Path

CONFIG_FILE = Path(Path(__file__).resolve().parents[2], "config.json")


def get_configuration(key):
    """

    Parameters
    ----------
    key: the name of a specific filed in the config file

    Returns
    -------
    the value of specific filed

    """
    with open(CONFIG_FILE) as config:
        config = json.load(config)
    return config.get(key, "")
