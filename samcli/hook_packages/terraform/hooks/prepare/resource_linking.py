"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import re
import logging

from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidResourceLinkingException

LOG = logging.getLogger(__name__)


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


def _resolve_module_output(module, output_name):
    pass


def _resolve_module_variable(module: TFModule, variable_name: str) -> List[Union[ConstantValue, ResolvedReference]]:
    # return a list of the values that resolve the passed variable
    # name in the input module.
    results: List[Union[ConstantValue, ResolvedReference]] = []

    LOG.debug("Resolving module variable for module (%s) and variable (%s)", module.module_name, variable_name)

    var_value = module.variables.get(variable_name)

    if not var_value:
        raise InvalidResourceLinkingException(
            message=f"The variable {variable_name} could not be found in module {module.module_name}."
        )

    # check the possible constant value for this variable
    if isinstance(var_value, ConstantValue) and var_value is not None:
        LOG.debug("Found a constant value (%s) in module (%s)", var_value.value, module.module_name)
        results.append(ConstantValue(var_value.value))

    # check the possible references value for this variable
    if isinstance(var_value, References) and var_value is not None:
        LOG.debug("Found references (%s) in module (%s)", var_value.value, module.module_name)
        cleaned_references = _clean_references_list(var_value.value)
        for reference in cleaned_references:
            LOG.debug("Resolving reference: %s", reference)
            # refer to a variable passed to this module from its parent module
            if reference.startswith("var."):
                config_var_name = _get_configuration_address(reference[4:])
                if module.parent_module:
                    results += _resolve_module_variable(module.parent_module, config_var_name)
            # refer to another module output. This module will be defined in the same level as this module
            elif reference.startswith("module."):
                module_name = reference[reference.find(".") + 1 : reference.rfind(".")]
                config_module_name = _get_configuration_address(module_name)
                output_name = reference[reference.rfind(".") + 1 :]
                if (
                    module.parent_module
                    and module.parent_module.child_modules
                    and module.parent_module.child_modules.get(config_module_name)
                ):
                    child_module = module.parent_module.child_modules.get(config_module_name)
                    results += _resolve_module_output(child_module, output_name)
                else:
                    raise InvalidResourceLinkingException(f"Couldn't find child module {config_module_name}.")
            # this means either a resource, data source, or local.variables.
            elif module.parent_module and module.parent_module.full_address is not None:
                results.append(ResolvedReference(reference, module.parent_module.full_address))
            else:
                raise InvalidResourceLinkingException("Resource linking entered an invalid state.")

    return results
