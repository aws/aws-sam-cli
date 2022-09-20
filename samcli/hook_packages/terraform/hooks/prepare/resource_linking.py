"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""
import re


def _get_configuration_address(address: str) -> str:
    """
    Cleans all addresses of indicies and returns a clean address

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
