"""
CDK Exceptions
"""
from typing import Optional

from samcli.commands.exceptions import UserException


class InvalidCloudAssemblyError(Exception):
    def __init__(self, missing_files: Optional[list] = None):
        if missing_files is None:
            missing_files = []
        msg = "Invalid Cloud Assembly. Missing files: {files}"
        Exception.__init__(self, msg.format(files=", ".join(missing_files)))


class CdkPluginError(UserException):
    pass


class CdkToolkitNotInstalledError(UserException):
    pass


class CdkSynthError(UserException):
    def __init__(self, stack_traces: str):
        msg = "When synthesizing your CDK app, the following error occurs:\n\n{stack_traces}"
        UserException.__init__(self, msg.format(stack_traces=stack_traces))
