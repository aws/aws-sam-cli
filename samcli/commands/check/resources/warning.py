class Warning:
    def __init__(self):
        self.warning_type = None
        self.message = None

    def set_message(self, message):
        self.message = message

    def get_message(self):
        return self.message
