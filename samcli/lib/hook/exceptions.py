"""Hooks Exceptions"""

from samcli.commands.exceptions import UserException


class InvalidHookWrapperException(UserException):
    pass


class InvalidHookPackageException(UserException):
    pass


class HookPackageExecuteFunctionalityException(UserException):
    pass


class InvalidHookPackageConfigException(UserException):
    pass


class PrepareHookException(UserException):
    pass


class TerraformCloudException(UserException):
    pass


class UnallowedEnvironmentVariableArgumentException(UserException):
    pass
