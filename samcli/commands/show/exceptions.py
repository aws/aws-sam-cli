"""
Exceptions that are raised by showing deployed stack output
"""
from samcli.commands.exceptions import UserException


class ShowStackOutputFailedError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message_fmt = "Failed to get outputs from stack: {stack_name}, {msg}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=msg))
