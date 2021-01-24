"""
Exceptions that are raised by sam bootstrap
"""
from samcli.commands.exceptions import UserException


class ManagedStackError(UserException):
    def __init__(self, ex):
        self.ex = ex
        message_fmt = f"Failed to create managed resources: {ex}"
        super().__init__(message=message_fmt.format(ex=self.ex))
