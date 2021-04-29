"""
CDK Exceptions
"""
from typing import Optional

from samcli.commands.exceptions import UserException


class UnsupportedCloudAssemblySchemaVersionError(Exception):
    def __init__(self, cloud_assembly_schema_version: str):
        msg = (
            "Your cloud assembly schema version '{cloud_assembly_schema_version}' is not supported, "
            "probably because you are running an old version of CDK. Please upgrade your CDK."
        )
        Exception.__init__(self, msg.format(cloud_assembly_schema_version=cloud_assembly_schema_version))


class UnsupportedCdkFeatureError(Exception):
    def __init__(self, reason: str):
        msg = "You are using a CDK feature that is currently not supported by SAM CLI yet. Reason: '{reason}'"
        Exception.__init__(self, msg.format(reason=reason))


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
