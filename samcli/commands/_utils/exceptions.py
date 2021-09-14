"""
Class containing error conditions that are exposed to the user.
"""

from samcli.commands.exceptions import UserException


class PackageResolveS3AndS3SetError(UserException):
    def __init__(self):
        message_fmt = "Cannot use both --resolve-s3 and --s3-bucket parameters. Please use only one."

        super().__init__(message=message_fmt)


class PackageResolveS3AndS3NotSetError(UserException):
    def __init__(self):
        message_fmt = "Cannot skip both --resolve-s3 and --s3-bucket parameters. Please provide one of these arguments."

        super().__init__(message=message_fmt)
