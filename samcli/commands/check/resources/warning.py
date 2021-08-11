"""
Class object for warnings. Warning messages are stored here
"""


class CheckWarning:
    message: str

    def __init__(self, message: str):
        self.message = message
