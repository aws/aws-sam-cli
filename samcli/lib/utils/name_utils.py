"""
Utilities for normalizing function names and identifiers
"""

import re

from samcli.lib.utils.arn_utils import ARNParts, InvalidArnValue

# Constants for ARN parsing
PARTIAL_ARN_MIN_PARTS = 3
FUNCTION_ALIAS_PARTS = 2

# AWS Lambda function name validation pattern (same as AWS Lambda service)
LAMBDA_FUNCTION_NAME_PATTERN = (
    r"^(arn:(aws[a-zA-Z-]*)?:lambda:)?((eusc-)?[a-z]{2}((-gov)|(-iso([a-z]?)))?-[a-z]+-\d{1}:)?"
    r"(\d{12}:)?(function:)?([a-zA-Z0-9-_\.]+)(:(\$LATEST(\.PUBLISHED)?|[a-zA-Z0-9-_]+))?$"
)


class InvalidFunctionNameException(Exception):
    """Exception raised when function name doesn't match AWS Lambda validation pattern"""

    pass


def normalize_lambda_function_name(function_identifier: str) -> str:
    """
    Normalize a Lambda function identifier by extracting the function name from various formats.

    AWS Lambda supports multiple function identifier formats as documented in the AWS CLI/SDK:

    Name formats:
    - Function name: my-function (name-only), my-function:v1 (with alias)
    - Function ARN: arn:aws:lambda:us-west-2:123456789012:function:my-function
    - Partial ARN: 123456789012:function:my-function

    This function normalizes all these formats to extract just the function name portion,
    which is what SAM CLI uses internally for function lookup.

    Parameters
    ----------
    function_identifier : str
        The function identifier in any of the supported formats

    Returns
    -------
    str
        The normalized function name

    Raises
    ------
    InvalidFunctionNameException
        If the function identifier doesn't match AWS Lambda's validation pattern

    Examples
    --------
    >>> normalize_lambda_function_name("my-function")
    "my-function"
    >>> normalize_lambda_function_name("my-function:v1")
    "my-function"
    >>> normalize_lambda_function_name("arn:aws:lambda:us-east-1:123456789012:function:my-function")
    "my-function"
    >>> normalize_lambda_function_name("arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST")
    "my-function"
    >>> normalize_lambda_function_name("123456789012:function:my-function")
    "my-function"
    """
    if not re.match(LAMBDA_FUNCTION_NAME_PATTERN, function_identifier):
        raise InvalidFunctionNameException(
            f"1 validation error detected: Value '{function_identifier}' at 'functionName' "
            f"failed to satisfy constraint: Member must satisfy regular expression pattern: "
            f"{LAMBDA_FUNCTION_NAME_PATTERN}"
        )

    # Handle full ARN format: arn:aws:lambda:region:account-id:function:function-name[:version]
    if function_identifier.startswith("arn:"):
        try:
            arn_parts = ARNParts(function_identifier)
            # Check if it's a Lambda ARN with function resource type
            if arn_parts.service == "lambda" and arn_parts.resource_type == "function":
                # For Lambda ARNs, the function name is in resource_id
                # Handle versioned functions by splitting on ':'
                function_name = arn_parts.resource_id.split(":")[0] if arn_parts.resource_id else ""
                return function_name if function_name else function_identifier
        except InvalidArnValue:
            # If ARN parsing fails, return the original input
            pass

    # Handle partial ARN format: account-id:function:function-name[:version]
    # This format has at least 3 parts separated by colons
    elif ":" in function_identifier and len(function_identifier.split(":")) >= PARTIAL_ARN_MIN_PARTS:
        parts = function_identifier.split(":")
        # Check if it matches the partial ARN pattern: account-id:function:function-name[:version]
        if len(parts) >= PARTIAL_ARN_MIN_PARTS and parts[1] == "function" and parts[2]:
            # Extract function name (3rd part) and remove any version suffix
            function_name = parts[2]
            return function_name if function_name else function_identifier

    # Handle function name with alias: my-function:alias
    # This is a simple function name with a single colon for alias/version
    # But exclude partial ARN patterns like "account:function" (missing function name)
    elif ":" in function_identifier:
        parts = function_identifier.split(":")
        if len(parts) == FUNCTION_ALIAS_PARTS and parts[1] != "function" and parts[0]:
            # Return just the function name part (before the colon) if it's not empty
            return parts[0]

    # Handle plain function name: my-function
    return function_identifier
