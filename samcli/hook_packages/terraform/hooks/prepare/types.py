""" Contains the data types used in the TF prepare hook"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union


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
    # root module address is None
    module_address: Optional[str]


@dataclass
class TFModule:
    # full path to the module, including parent modules
    full_address: Optional[str]
    parent_module: Optional["TFModule"]
    variables: Dict[str, Expression]
    resources: Dict[str, "TFResource"]
    child_modules: Dict[str, "TFModule"]
    outputs: Dict[str, Expression]

    # current module's + all child modules' resources
    def get_all_resources(self) -> List["TFResource"]:
        all_resources = [deepcopy(resource) for resource in self.resources.values()]
        for _, module in self.child_modules.items():
            all_resources += module.get_all_resources()

        return all_resources

    @property
    def module_name(self):
        return self.full_address if self.full_address else "root module"


@dataclass
class TFResource:
    address: str
    type: str
    # the module this resource is defined in
    module: TFModule
    attributes: Dict[str, Expression]

    @property
    def full_address(self) -> str:
        if self.module and self.module.full_address:
            return f"{self.module.full_address}.{self.address}"
        return self.address


PropertyBuilder = Callable[[dict, TFResource], Any]
PropertyBuilderMapping = Dict[str, PropertyBuilder]


@dataclass
class ResourceTranslator:
    cfn_name: str
    property_builder_mapping: PropertyBuilderMapping


@dataclass
class SamMetadataResource:
    current_module_address: Optional[str]
    resource: Dict
    config_resource: TFResource
