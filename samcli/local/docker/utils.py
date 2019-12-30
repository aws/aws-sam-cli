"""
Helper methods that aid with changing the mount path to unix style.
"""

import os
import re
import posixpath
import pathlib


def to_posix_path(code_path):
    """Change the code_path to be of unix-style if running on windows when supplied with an absolute windows path.

    Parameters
    ----------
    code_path : str


    Returns
    -------
    str


    Examples
    --------
    >>> to_posix_path('/Users/UserName/sam-app')
    /Users/UserName/sam-app
    >>> to_posix_path('C:\\\\Users\\\\UserName\\\\AppData\\\\Local\\\\Temp\\\\mydir')
    /c/Users/UserName/AppData/Local/Temp/mydir
    """

    return (
        re.sub(
            "^([A-Za-z])+:",
            lambda match: posixpath.sep + match.group().replace(":", "").lower(),
            pathlib.PureWindowsPath(code_path).as_posix(),
        )
        if os.name == "nt"
        else code_path
    )
