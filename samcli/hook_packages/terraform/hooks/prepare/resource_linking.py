"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import re


@dataclass
class ConstantValue:
    value: Any


@dataclass
class References:
    value: List[str]


Expression = Union[ConstantValue, References]


@dataclass
class ResolvedReference:
    value: str
    module_address: str


@dataclass
class TFModule:
    # full path to the module, including parent modules
    full_address: Optional[str]
    parent_module: Optional["TFModule"]
    variables: Dict[str, Expression]
    resources: List["TFResource"]
    child_modules: Dict[str, "TFModule"]
    outputs: Dict[str, Expression]

    # current module's + all child modules' resources
    def get_all_resources(self) -> List["TFResource"]:
        all_resources = self.resources.copy()
        for _, module in self.child_modules.items():
            all_resources += module.get_all_resources()

        return all_resources


@dataclass
class TFResource:
    address: str
    type: str
    # the module this resource is defined in
    module: TFModule
    attributes: Dict[str, Expression]

    @property
    def full_address(self) -> str:
        if self.module.full_address:
            return f"{self.module.full_address}.{self.address}"
        return self.address


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
