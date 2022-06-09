"""
Exceptions for SAM list
"""


from samcli.commands.exceptions import UserException


class StackOutputsError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message_fmt = "{msg}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=msg))


class NoOutputsForStackError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message_fmt = f"Outputs do not exist for the input stack {stack_name} on Cloudformation in the region {msg}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=msg))
