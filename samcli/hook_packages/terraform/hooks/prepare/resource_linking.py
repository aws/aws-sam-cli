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


def _build_module(
    module_name: Optional[str],
    module_configuration: Dict,
    input_variables: Dict[str, Expression],
    parent_module_address: Optional[str],
) -> TFModule:
    """
    Builds and returns a TFModule

    Parameters
    ==========
    module_name: Optional[str]
        The module's name, if any
    module_configuration: Dict
        The module object from the terraform configuration
    input_variables: Dict[str, Expression]
        The input variables sent into the module
    parent_module_address: Optional[str]
        The module's parent address, if any

    Returns
    =======
    TFModule
        The constructed TFModule
    """
    module = TFModule(None, None, {}, [], {}, {})

    module.full_address = _build_module_full_address(module_name, parent_module_address)
    module.variables = _build_module_variables_from_configuration(module_configuration, input_variables)
    module.resources = _build_module_resources_from_configuration(module_configuration, module)
    module.outputs = _build_module_outputs_from_configuration(module_configuration)
    module.child_modules = _build_child_modules_from_configuration(module_configuration, module)

    return module


def _build_module_full_address(module_name: Optional[str], parent_module_address: Optional[str]) -> Optional[str]:
    """
    Returns the full address of a module, depending on whether it has a module name and a parent module address.

    Parameters
    ==========
    module_name: Optional[str]
        The module's name, if any
    parent_module_address: Optional[str]
        The module's parent address, if any

    Returns
    =======
    Optional[str]
        Returns None if no module_name is provided (e.g. root module).
        Returns module.<module_name> if a module_name is provided
        Returns <parent_module_address>.module.<module_name> if both module_name and
            parent_module_address are provided
    """
    full_address = None
    if module_name:
        full_address = f"module.{module_name}"
        if parent_module_address:
            full_address = f"{parent_module_address}.{full_address}"

    return full_address


def _build_module_variables_from_configuration(
    module_configuration: Dict, input_variables: Dict[str, Expression]
) -> Dict[str, Expression]:
    """
    Builds and returns module variables as Expressions using a module terraform configuration

    Parameters
    ==========
    module_configuration: dict
        The module object from the terraform configuration
    input_variables: Dict[str, Expression]
        The input variables sent into the module to override default variables

    Returns
    =======
    Dict[str, Expression]
        Dictionary with the variable names as keys and parsed Expression as values.
    """
    module_variables: Dict[str, Expression] = {}

    default_variables = module_configuration.get("variables", {})
    for variable_name, variable_value in default_variables.items():
        module_variables[variable_name] = ConstantValue(variable_value.get("default"))
    module_variables.update(input_variables)

    return module_variables


def _build_module_resources_from_configuration(module_configuration: Dict, module: TFModule) -> List[TFResource]:
    """
    Builds and returns module TFResources using a module terraform configuration

    Parameters
    ==========
    module_configuration: dict
        The module object from the terraform configuration

    Returns
    =======
    List[TFResource]
        List of TFResource for the parsed resources from the config
    module: TFModule
        The TFModule whose resources we're parsing
    """
    module_resources = []

    config_resources = module_configuration.get("resources", [])
    for config_resource in config_resources:
        resource_attributes: Dict[str, Expression] = {}

        expressions = config_resource.get("expressions", {})
        print(expressions)
        for expression_name, expression_value in expressions.items():
            parsed_expression = _build_expression_from_configuration(expression_value)
            resource_attributes[expression_name] = parsed_expression

        resource_address = config_resource.get("address")
        resource_type = config_resource.get("type")
        module_resources.append(TFResource(resource_address, resource_type, module, resource_attributes))

    return module_resources


def _build_module_outputs_from_configuration(module_configuration: Dict) -> Dict[str, Expression]:
    """
    Builds and returns module outputs as Expressions using a module terraform configuration

    Parameters
    ==========
    module_configuration: dict
        The module object from the terraform configuration

    Returns
    =======
    Dict[str, Expression]
        Dictionary with the output names as keys and parsed Expression as values.
    """
    module_outputs = {}

    config_outputs = module_configuration.get("outputs", {})
    for output_name, output_value in config_outputs.items():
        expression = output_value.get("expression", {})
        parsed_expression = _build_expression_from_configuration(expression)
        module_outputs[output_name] = parsed_expression

    return module_outputs


def _build_child_modules_from_configuration(module_configuration: Dict, module: TFModule) -> Dict[str, TFModule]:
    """
    Builds and returns child TFModules using a module terraform configuration

    Parameters
    ==========
    module_configuration: dict
        The module object from the terraform configuration
    module: TFModule
        The TFModule whose child modules we're building

    Returns
    =======
    Dict[str, TFModule]
        Dictionary with the module names as keys and parsed TFModule as values.
    """
    child_modules = {}

    module_calls = module_configuration.get("module_calls", {})
    for module_call_name, module_call_value in module_calls.items():
        module_call_input_variables: Dict[str, Expression] = {}

        expressions = module_call_value.get("expressions", {})
        for expression_name, expression_value in expressions.items():
            parsed_expression = _build_expression_from_configuration(expression_value)
            module_call_input_variables[expression_name] = parsed_expression

        module_call_module_config = module_call_value.get("module", {})
        module_call_built_module = _build_module(
            module_call_name, module_call_module_config, module_call_input_variables, module.full_address
        )

        module_call_built_module.parent_module = module
        child_modules[module_call_name] = module_call_built_module

    return child_modules


def _build_expression_from_configuration(expression_configuration: Dict) -> Expression:
    """
    Parses an Expression from an expression terraform configuration.

    Parameters
    ==========
    expression_configuration: dict
        The expression object from the terraform configuration

    Returns
    =======
    Expression
        The parsed expression
    """
    constant_value = expression_configuration.get("constant_value")
    references = expression_configuration.get("references")

    parsed_expression: Expression

    if constant_value:
        parsed_expression = ConstantValue(constant_value)
    elif references:
        parsed_expression = References(references)

    return parsed_expression


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
                config_var_name = _get_configuration_address(reference[len("var.") :])
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
