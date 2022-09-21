"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TFValue:
    constant_value: Any
    references: List[str]


@dataclass
class TFModule:
    # full path to the module, including parent modules
    full_address: Optional[str]
    parent_module: Optional["TFModule"]
    variables: Dict[str, TFValue]
    resources: Dict[str, "TFResource"]
    children_modules: Dict[str, "TFModule"]
    outputs: Dict[str, TFValue]

    # current module's + all child modules' resources
    def get_all_resources(self) -> List["TFResource"]:
        # TODO
        pass


@dataclass
class TFResource:
    address: str
    type: str
    # the module this resource is defined in
    module: TFModule
    attributes: Dict[str, TFValue]

    @property
    def full_address(self) -> str:
        if self.module.full_address:
            return f"{self.module.full_address}.{self.address}"
        return self.address
