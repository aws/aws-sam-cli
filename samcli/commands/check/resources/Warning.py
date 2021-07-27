"""
Class object for warnings. Warning messages, as well as the warning type is stored here
"""


class CheckWarning:
    def __init__(self):
        self._warning_type = None
        self._message = None

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, message: str):
        self._message = message
