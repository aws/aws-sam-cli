"""
Contains CodeUri Related methods
"""

import logging
import os

LOG = logging.getLogger(__name__)

PRESENT_DIR = "."


def resolve_code_path(cwd, codeuri):
    """
    Returns path to the function code resolved based on current working directory.

    Parameters
    ----------
    cwd : str
        Current working directory
    codeuri : str
        CodeURI of the function. This should contain the path to the function code

    Returns
    -------
    str
        Absolute path to the function code

    """
    LOG.debug("Resolving code path. Cwd=%s, CodeUri=%s", cwd, codeuri)

    # First, let us figure out the current working directory.
    # If current working directory is not provided, then default to the directory where the CLI is running from
    if not cwd or cwd == PRESENT_DIR:
        cwd = os.getcwd()

    # Make sure cwd is an absolute path
    cwd = os.path.abspath(cwd)

    # Next, let us get absolute path of function code.
    # Codepath is always relative to current working directory
    # If the path is relative, then construct the absolute version
    if not os.path.isabs(codeuri):
        codeuri = os.path.normpath(os.path.join(cwd, codeuri))

    return codeuri
