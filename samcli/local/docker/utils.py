"""
Helper methods that aid with changing the mount path to unix style.
"""

import os
import posixpath
import re
try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib


def to_posix_path(code_path):
    """
    Change the code_path to be of unix-style if running on windows when supplied with an absolute windows path.

    Parameters
    ----------
    code_path : str
        Directory in the host operating system that should be mounted within the container.
    Returns
    -------
    str
        Posix equivalent of absolute windows style path.
    Examples
    --------
    >>> to_posix_path('/Users/UserName/sam-app')
    /Users/UserName/sam-app
    >>> to_posix_path('C:\\\\Users\\\\UserName\\\\AppData\\\\Local\\\\Temp\\\\mydir')
    /c/Users/UserName/AppData/Local/Temp/mydir
    """

    return re.sub("^([A-Za-z])+:",
                  lambda match: posixpath.sep + match.group().replace(":", "").lower(),
                  pathlib.PureWindowsPath(code_path).as_posix()) if os.name == "nt" else code_path
