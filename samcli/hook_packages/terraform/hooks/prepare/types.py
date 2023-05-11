""" Contains the data types used in the TF prepare hook"""
from abc import ABC
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union

from samcli.hook_packages.terraform.hooks.prepare.utilities import get_configuration_address


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


class LinkingPairCaller(NamedTuple):
    source: str
    dest: str
    linking_func: Callable[[Dict[str, TFResource], Dict[str, List], Dict[str, Dict]], None]


class ResourceTranslationValidator:
    """
    Base class for a validation class to be used when translating Terraform resources to a metadata file
    """

    resource: Dict
    config_resource: TFResource

    def __init__(self, resource, config_resource):
        self.resource = resource
        self.config_resource = config_resource

    def validate(self):
        """
        Function to be called for resources of a given type used for validating
        the AWS SAM CLI transformation logic for the given resource
        """
        raise NotImplementedError


@dataclass
class ResourceTranslationProperties:
    """
    These are a collection of properties useful for defining a
    translation from Terraform to CFN for a given resource
    """

    resource: Dict
    translated_resource: Dict
    config_resource: TFResource
    logical_id: str
    resource_full_address: str


class ResourceProperties(ABC):
    """
    Interface definition for a resource type to handle collecting and storing properties specific to it's type.
    These properties are then used for handling specific resource-based logic, such as linking to other resources.
    """

    def __init__(self):
        self.terraform_resources: Dict[str, Dict] = {}
        self.terraform_config: Dict[str, TFResource] = {}
        self.cfn_resources: Dict[str, List] = {}

    def collect(self, properties: ResourceTranslationProperties):
        """
        Collect any properties required for future resource processing after traversing the Terraform modules.

        In parent class we collect all the required properties. This logic can be customized in the children classes.

        Parameters
        ----------
        properties: ResourceTranslationProperties
            Properties acquired specific to an AWS resource when iterating through a Terraform module
        """
        resolved_config_address = get_configuration_address(properties.resource_full_address)
        matched_gateway_methods = self.cfn_resources.get(resolved_config_address, [])
        matched_gateway_methods.append(properties.translated_resource)
        self.cfn_resources[resolved_config_address] = matched_gateway_methods
        self.terraform_config[resolved_config_address] = properties.config_resource
        self.terraform_resources[properties.logical_id] = properties.resource


class CodeResourceProperties(ResourceProperties, ABC):
    """
    This interface extends ResourceProperties. In addition to resource properties, `CodeResourceProperties`
    expects the implementing class to define a `add_lambda_resources_to_code_map` used for resolving
    the code-specific properties of that resource type.
    """

    def add_lambda_resources_to_code_map(
        self,
        properties: ResourceTranslationProperties,
        translated_properties: Dict,
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
    ):
        """
        Resolves the relevant code properties for an CFN resource from a Terraform resource
        and then stores that property in the lambda_resources_to_code_map.

        Parameters
        ----------
        properties: ResourceTranslationProperties
            Properties acquired specific to the resource being translated when iterating through a Terraform module
        translated_properties: Dict
            A dictionary of CloudFormation properties that were translated by the hook from the Terraform plan file
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]]
            A map storing all the Lambda code properties
        """
        raise NotImplementedError
