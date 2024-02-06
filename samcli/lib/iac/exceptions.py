"""
IaC Exceptions
"""

from typing import Optional

from samcli.commands.exceptions import UserException


class InvalidIaCPluginException(UserException):
    def __init__(self, files: Optional[list] = None):
        if files is None:
            files = []
        msg = "Could not determine the plugin type from the provided files:\n\n{files}"
        UserException.__init__(self, msg.format(files=", ".join(files)))


class InvalidProjectTypeException(UserException):
    def __init__(self, msg):
        UserException.__init__(self, msg)
