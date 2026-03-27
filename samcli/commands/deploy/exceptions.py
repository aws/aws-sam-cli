"""
Exceptions that are raised by sam deploy
"""

import re
from typing import Optional, Tuple

from samcli.commands.exceptions import UserException

# Pattern to match CloudFormation's Fn::FindInMap error message
# Example: "Fn::FindInMap - Key 'Products' not found in Mapping 'SAMCodeUriServices'"
# The pattern handles:
# - Single quotes: Key 'Products'
# - Double quotes: Key "Products"
# - No quotes: Key Products
FINDMAP_KEY_NOT_FOUND_PATTERN = re.compile(
    r"Fn::FindInMap.*Key\s+"
    r"(?:'([^']+)'|\"([^\"]+)\"|(\S+))"
    r"\s+not found in Mapping\s+"
    r"(?:'([^']+)'|\"([^\"]+)\"|(\S+))"
)


def parse_findmap_error(error_message: str) -> Optional[Tuple[str, str]]:
    """
    Parse a CloudFormation error message to extract missing Mapping key information.

    Args:
        error_message: The error message from CloudFormation

    Returns:
        A tuple of (missing_key, mapping_name) if the error is a FindInMap key not found error,
        None otherwise.
    """
    match = FINDMAP_KEY_NOT_FOUND_PATTERN.search(error_message)
    if match:
        # Groups 1, 2, 3 are for the key (single-quoted, double-quoted, unquoted)
        # Groups 4, 5, 6 are for the mapping name (single-quoted, double-quoted, unquoted)
        key = match.group(1) or match.group(2) or match.group(3)
        mapping = match.group(4) or match.group(5) or match.group(6)
        if key and mapping:
            return (key, mapping)
    return None


class ChangeEmptyError(UserException):
    def __init__(self, stack_name):
        self.stack_name = stack_name
        message_fmt = "No changes to deploy. Stack {stack_name} is up to date"
        super().__init__(message=message_fmt.format(stack_name=self.stack_name))


class ChangeSetError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg
        message_fmt = "Failed to create changeset for the stack: {stack_name}, {msg}"
        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=self.msg))


class DeployFailedError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message_fmt = "Failed to create/update the stack: {stack_name}, {msg}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=msg))


class GuidedDeployFailedError(UserException):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(message=msg)


class DeployStackOutPutFailedError(UserException):
    def __init__(self, stack_name, msg):
        self.stack_name = stack_name
        self.msg = msg

        message_fmt = "Failed to get outputs from stack: {stack_name}, {msg}"

        super().__init__(message=message_fmt.format(stack_name=self.stack_name, msg=msg))


class DeployBucketInDifferentRegionError(UserException):
    def __init__(self, msg):
        self.msg = msg

        message_fmt = "{msg} : deployment s3 bucket is in a different region, try sam deploy --guided"

        super().__init__(message=message_fmt.format(msg=self.msg))


class DeployBucketRequiredError(UserException):
    def __init__(self):
        message_fmt = (
            "Templates with a size greater than 51,200 bytes must be deployed "
            "via an S3 Bucket. Please add the --s3-bucket parameter to your "
            "command. The local template will be copied to that S3 bucket and "
            "then deployed."
        )

        super().__init__(message=message_fmt)


class DeployResolveS3AndS3SetError(UserException):
    def __init__(self):
        message_fmt = (
            "Cannot use both --resolve-s3 and --s3-bucket parameters in non-guided deployments."
            " Please use only one or use the --guided option for a guided deployment."
        )

        super().__init__(message=message_fmt)


class DeployStackStatusMissingError(UserException):
    def __init__(self, stack_name):
        message_fmt = "Was not able to find a stack with the name: {msg}, please check your parameters and try again."
        super().__init__(message=message_fmt.format(msg=stack_name))


class MissingMappingKeyError(UserException):
    """
    Error raised when CloudFormation deployment fails due to a missing key in a Mapping.

    This typically occurs when a template was packaged with certain parameter values
    (e.g., ServiceNames="Users,Orders") but deployed with different values
    (e.g., ServiceNames="Users,Orders,Products"). The Mappings generated during
    packaging only contain entries for the values known at package time.
    """

    def __init__(self, stack_name: str, missing_key: str, mapping_name: str, original_error: str):
        self.stack_name = stack_name
        self.missing_key = missing_key
        self.mapping_name = mapping_name
        self.original_error = original_error

        message = f"""Failed to create/update the stack: {stack_name}

Error: Fn::FindInMap - Key '{missing_key}' not found in Mapping '{mapping_name}'

This error typically occurs when:
  - The template was packaged with certain parameter values
  - You are deploying with different parameter values that include '{missing_key}'
  - The Mappings generated during packaging don't include an entry for '{missing_key}'

To fix this issue:
  1. Re-run 'sam package' with the same parameter values you want to use for deployment
  2. Then run 'sam deploy' with those same parameter values

Example:
  sam package --parameter-overrides YourParamName="value1,value2,{missing_key}" ...
  sam deploy --parameter-overrides YourParamName="value1,value2,{missing_key}" ...

Note: When using Fn::ForEach with dynamic artifact properties (like CodeUri: ./services/${{Name}}),
the collection values are fixed at package time. Any new values added at deploy time
will not have corresponding artifacts in S3.

Original CloudFormation error: {original_error}"""

        super().__init__(message=message)
