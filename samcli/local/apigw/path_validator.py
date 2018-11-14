"""
Validator class that checks Api Gateway paths are valid

By validating the paths here, we guarantee paths created with SAM don't result in an error
on a later stage, when deploying the template.
"""

import re

# This is the error the Api Gateway returns when the path is not valid:
# "Resource's path part only allow a-zA-Z0-9._- and curly braces at the beginning and the end."

# Note that this message refers to a specific resource, therefore the curly braces rule
# (the specific restriction of having them at the beginning and end) shouldn't apply to the
# path (which is a composition of resources).
ALLOWED_PATH_CHARS = r"[A-Za-z0-9_-{}\/\.]*$"

PATH_VALIDATOR_REGEX = re.compile(ALLOWED_PATH_CHARS)

class PathValidator(object):

  @staticmethod
  def is_valid(path):
    """
    Validates the Api Gateway Path is valid (only includes a-zA-Z0-9._- and curly braces)

    Examples:

    '/path/to/something' => true
    '/path/to/~something' => false
    """

    return bool(PATH_VALIDATOR_REGEX.match(path))
            