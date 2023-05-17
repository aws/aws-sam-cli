"""
Exceptions used by remote invoke executors
"""
from samcli.commands.exceptions import UserException


class InvalidResourceBotoParameterException(UserException):
    msg: str

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(self.msg)
