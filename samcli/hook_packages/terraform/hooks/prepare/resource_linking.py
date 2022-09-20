"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Value:
    constant_value: Any
    references: List[str]


@dataclass
class Module:
    # full path to the module, including parent modules
    full_address: str
    parent_module: Optional["Module"]
    variables: Dict[str, Value]
    resources: Dict[str, "Resource"]
    children_modules: Dict[str, "Module"]
    outputs: Dict[str, Value]

    # current module's + all child modules' resources
    def get_all_resources(self) -> List["Resource"]:
        # TODO
        pass


@dataclass
class Resource:
    address: str
    type: str
    # the module this resource is defined in
    module: "Module"
    attributes: Dict[str, Value]

    @property
    def full_address(self) -> str:
        return f"{self.module.full_address}.{self.address}"
