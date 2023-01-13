"""
click callback to validate importing a list of modules from a txt file
This is used to validate a freshly installed SAM CLI has all the hidden imports  
"""
import logging
from pathlib import Path

LOG = logging.getLogger(__name__)
txt_file = Path(__file__).parent.parent / "samcli_modules.txt"

def validate_imports() -> bool:
    """
    Validates installation by trying to import the list of modules in txt_file

    The txt_file should be refreshed in each run of installer build script (e.g. installer/pyinstaller/build-linux.sh)
    """
    try:
        with open(txt_file, "r") as f:
            modules = f.readlines()
    except FileNotFoundError:
        LOG.info("txt_file not found")
        return False

    if not modules:
        LOG.info("txt_file is empty")
        return False

    for module_name in modules:
        try:
            __import__(module_name.strip())
        except ImportError:
            LOG.info("ImportError: %s", module_name)
            return False

    return True
    