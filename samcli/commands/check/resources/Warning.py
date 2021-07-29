"""
Class object for warnings. Warning messages, as well as the warning type is stored here
"""


class CheckWarning:
    message: str

    def __init__(self, message: str):
        self.message: str = message
