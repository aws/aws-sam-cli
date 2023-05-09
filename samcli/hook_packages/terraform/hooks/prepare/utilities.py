""" Maintain the utilities functions used in prepare hook """
from samcli.hook_packages.terraform.hooks.prepare.constants import COMPILED_REGULAR_EXPRESSION


def get_configuration_address(address: str) -> str:
    """
    Cleans all addresses of indices and returns a clean address

    Parameters
    ----------
    address : str
        The address to clean

    Returns
    -------
    str
        The address clean of indices
    """
    return COMPILED_REGULAR_EXPRESSION.sub("", address)
