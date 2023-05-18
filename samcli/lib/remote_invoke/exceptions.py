"""
Exceptions used by remote invoke executors
"""


class InvalidResourceBotoParameterException(Exception):
    msg: str

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(self.msg)


class InvalideBotoResponseException(Exception):
    msg: str

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(self.msg)
