"""Terraform utilities"""

from typing import List

from samcli.lib.utils.hash import str_checksum

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247


def build_cfn_logical_id(tf_address: str) -> str:
    """
    Builds a CloudFormation logical ID out of a terraform resource address

    Parameters
    ----------
    tf_address: str
        terraform resource address

    Returns
    -------
    str
        CloudFormation logical ID
    """
    # ignores non-alphanumericals, makes uppercase the first alphanumerical char and the
    # alphanumerical char right after a non-alphanumerical char
    chars: List[str] = []
    nextCharUppercase = True
    for char in tf_address:
        if len(chars) == LOGICAL_ID_MAX_HUMAN_LEN:
            break
        if not char.isalnum():
            nextCharUppercase = True
            continue
        if nextCharUppercase:
            chars.append(char.upper())
            nextCharUppercase = False
        else:
            chars.append(char)

    # Add a hash to avoid naming conflicts
    human_part = "".join(chars)
    hash_part = str_checksum(tf_address)[:LOGICAL_ID_HASH_LEN].upper()

    return human_part + hash_part
