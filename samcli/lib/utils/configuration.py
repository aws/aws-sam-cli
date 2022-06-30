""" Read info from runtime_config.json file"""

import json
from pathlib import Path
import logging

from click import ClickException

LOG = logging.getLogger(__name__)

CONFIG_FILE = Path(Path(__file__).resolve().parents[2], "runtime_config.json")
config = json.loads(CONFIG_FILE.read_text())


def get_app_template_repo_commit():
    """
    Returns
    -------
    the value of app_template_repo_commit

    """
    commit_hash = config.get("app_template_repo_commit", None)
    if not commit_hash:
        raise ClickException(
            message="Error when retrieving app_template_repo_commit, runtime_config.json file maybe invalid"
        )
    return commit_hash
