"""
Exceptions for SAM list
"""


from samcli.commands.exceptions import UserException


class SamListError(UserException):
    """
    Base exception for the 'sam list' command
    """

    def __init__(self, msg):
        self.msg = msg

        message_fmt = "{msg}"

        super().__init__(message=message_fmt.format(msg=msg))


class SamListUnknownClientError(SamListError):
    """
    Used when boto3 API call raises an unexpected ClientError
    """


class SamListUnknownBotoCoreError(SamListError):
    """
    Used when boto3 API call raises an unexpected BotoCoreError
    """


class SamListLocalResourcesNotFoundError(SamListError):
    """
    Used when unable to retrieve local resources after performing a transform
    """


class NoOutputsForStackError(UserException):
    def __init__(self, stack_name, region):
        self.stack_name = stack_name
        self.region = region

        message_fmt = f"Outputs do not exist for the input stack {stack_name} on Cloudformation in the region {region}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, region=self.region))


class StackDoesNotExistInRegionError(UserException):
    def __init__(self, stack_name, region):
        self.stack_name = stack_name
        self.region = region

        message_fmt = f"The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, region=self.region))
