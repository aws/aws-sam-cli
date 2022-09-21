"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""

import re
from typing import List


def _clean_references_list(references: List[str]) -> List[str]:
    """
    Return a new copy of the complete references list.

    e.g. given a list of references like
    [
        'aws_lambda_layer_version.layer1[0].arn',
        'aws_lambda_layer_version.layer1[0]',
        'aws_lambda_layer_version.layer1',
    ]
    We want only the first complete reference ('aws_lambda_layer_version.layer1[0].arn')

    Parameters
    ----------
    references: List[str]
        A list of reference strings

    Returns
    -------
    List[str]
        A copy of a cleaned list of reference strings
    """
    cleaned_references = []
    copied_references = sorted(references, reverse=True)
    if not references:
        return []
    cleaned_references.append(copied_references[0])
    for i in range(1, len(copied_references)):
        if not cleaned_references[-1].startswith(copied_references[i]):
            cleaned_references.append(copied_references[i])
    return cleaned_references


def _get_configuration_address(address: str) -> str:
    """
    Cleans all addresses of indices and returns a clean address

    Parameters
    ==========
    address : str
        The address to clean

    Returns
    =======
    str
        The address clean of indices
    """
    return re.sub(r"\[[^\[\]]*\]", "", address)
