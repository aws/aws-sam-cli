"""
Class object for warnings. Warning messages, as well as the warning type is stored here
"""


class CheckWarning:
    def __init__(self):
        self.warning_type: str = ""
        self.message: str = ""
