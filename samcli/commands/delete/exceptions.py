"""
Exceptions that are raised by sam delete
"""

from samcli.commands.exceptions import UserException


class DeleteFailedError(UserException):
    def __init__(self, stack_name, msg, stack_status=None):
        self.stack_name = stack_name
        self.msg = msg
        self.stack_status = stack_status

        message = f"Failed to delete the stack: {stack_name}, msg: {msg}"
        if self.stack_status:
            message += f", status: {self.stack_status}"

        super().__init__(message=message)


class CfDeleteFailedStatusError(UserException):
    def __init__(self, stack_name, msg, stack_status=None):
        self.stack_name = stack_name
        self.msg = msg
        self.stack_status = stack_status

        message = f"Stack {stack_name} could not be deleted as it encountered DELETE_FAILED, " f"msg: {msg}"
        if self.stack_status:
            message += f", status: {self.stack_status}"

        super().__init__(message=message)


class FetchTemplateFailedError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message = f"Failed to fetch the template for the stack: {stack_name}, {msg}"

        super().__init__(message=message)


class FetchChangeSetError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message = f"Failed to fetch change sets for stack: {stack_name}, {msg}"

        super().__init__(message=message)


class NoChangeSetFoundError(UserException):
    def __init__(self, stack_name):
        self.stack_name = stack_name

        message = f"Stack {stack_name} does not contain any change sets"

        super().__init__(message=message)


class StackFetchError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message = f"Failed to complete an API call to fetch stack information for {stack_name}: {msg}"
        super().__init__(message=message)


class StackProtectionEnabledError(UserException):
    def __init__(self, stack_name):
        self.stack_name = stack_name

        message = f"Stack {stack_name} cannot be deleted while TerminationProtection is enabled."
        super().__init__(message=message)
