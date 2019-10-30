"""
Exceptions that are raised by sam deploy
"""
from samcli.commands.exceptions import UserException


class ChangeEmptyError(UserException):
    def __init__(self, stack_name):
        self.stack_name = stack_name
        message_fmt = "No changes to deploy.Stack {stack_name} is up to date"
        super(ChangeEmptyError, self).__init__(message=message_fmt.format(stack_name=self.stack_name))


class InvalidKeyValuePairArgumentError(UserException):
    def __init__(self, value, argname):
        self.value = value
        self.argname = argname

        message_fmt = "{value} value passed to --{argname} must be of format " "Key=Value"
        super(InvalidKeyValuePairArgumentError, self).__init__(
            message=message_fmt.format(value=self.value, argname=self.argname)
        )


class DeployFailedError(UserException):
    def __init__(self, stack_name):
        self.stack_name = stack_name

        message_fmt = (
            "Failed to create/update the stack. Run the following command"
            "\n"
            "to fetch the list of events leading up to the failure"
            "\n"
            "aws cloudformation describe-stack-events --stack-name {stack_name}"
        )

        super(DeployFailedError, self).__init__(message=message_fmt.format(stack_name=self.stack_name))


class DeployBucketRequiredError(UserException):
    def __init__(self):

        message_fmt = (
            "Templates with a size greater than 51,200 bytes must be deployed "
            "via an S3 Bucket. Please add the --s3-bucket parameter to your "
            "command. The local template will be copied to that S3 bucket and "
            "then deployed."
        )

        super(DeployBucketRequiredError, self).__init__(message=message_fmt)
