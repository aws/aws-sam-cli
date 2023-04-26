"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Type, Union

from samcli.hook_packages.terraform.hooks.prepare.exceptions import (
    InvalidResourceLinkingException,
    LocalVariablesLinkingLimitationException,
    OneResourceLinkingLimitationException,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    Expression,
    References,
    ResolvedReference,
    TFModule,
    TFResource,
)
from samcli.hook_packages.terraform.lib.utils import build_cfn_logical_id

LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX = "aws_lambda_layer_version."
TERRAFORM_LOCAL_VARIABLES_ADDRESS_PREFIX = "local."
DATA_RESOURCE_ADDRESS_PREFIX = "data."

LOG = logging.getLogger(__name__)
COMPILED_REGULAR_EXPRESSION = re.compile(r"\[[^\[\]]*\]")


class LinkerIntrinsics(Enum):
    Ref = "Ref"
    GetAtt = "GetAtt"


@dataclass
class ResourcePairExceptions:
    multiple_resource_linking_exception: Type[OneResourceLinkingLimitationException]
    local_variable_linking_exception: Type[LocalVariablesLinkingLimitationException]


@dataclass
class ResourceLinkingPair:
    source_resource_cfn_resource: Dict[str, List]
    source_resource_tf_config: Dict[str, TFResource]
    destination_resource_tf: Dict[str, Dict]
    intrinsic_type: LinkerIntrinsics
    cfn_intrinsic_attribute: Optional[str]
    source_link_field_name: str
    terraform_link_field_name: str
    terraform_resource_type_prefix: str
    linking_exceptions: ResourcePairExceptions


class ResourceLinker:
    _resource_pair: ResourceLinkingPair

    def __init__(self, resource_pair):
        self._resource_pair = resource_pair

    def link_resources(self):
        """
        Validate the ResourceLinkingPair object and link the corresponding source resource to destination resource
        """
        for config_address, resource in self._resource_pair.source_resource_tf_config.items():
            if config_address in self._resource_pair.source_resource_cfn_resource:
                LOG.debug("Linking destination resource for source resource: %s", resource.full_address)
                self._handle_linking(
                    resource,
                    self._resource_pair.source_resource_cfn_resource[config_address],
                )

    def _handle_linking(self, source_tf_resource: TFResource, cfn_source_resources: List[Dict]) -> None:
        """
        Resolve the destinations resource for the input source configuration resource,
        and then update the equivalent cfn source resource list.
        The source resource configuration resource in Terraform can match
        multiple actual resources in case if it was defined using count or for_each pattern.

        Parameters
        ----------
        source_tf_resource: TFResource
            The source resource Terraform configuration resource

        cfn_source_resources: List[Dict]
            A list of mapped source resources that are equivalent to the input terraform configuration source resource
        """

        LOG.debug(
            "Link resource configuration %s that has these instances %s.",
            source_tf_resource.full_address,
            cfn_source_resources,
        )
        resolved_dest_resources = _resolve_resource_attribute(
            source_tf_resource, self._resource_pair.terraform_link_field_name
        )
        LOG.debug(
            "The resolved destination resources for source resource %s are %s",
            source_tf_resource.full_address,
            resolved_dest_resources,
        )
        dest_resources = self._process_resolved_resources(source_tf_resource, resolved_dest_resources)

        # The agreed limitation to support only 1 destination resource.
        if len(dest_resources) > 1:
            LOG.debug(
                "AWS SAM CLI does not support mapping the source resources %s to more than one destination resource.",
                source_tf_resource.full_address,
            )
            raise self._resource_pair.linking_exceptions.multiple_resource_linking_exception(
                dest_resources, source_tf_resource.full_address
            )
        if not dest_resources:
            LOG.debug(
                "There are destination resources defined for for the source resource %s",
                source_tf_resource.full_address,
            )
        else:
            self._update_mapped_parent_resource_with_resolved_child_resources(cfn_source_resources, dest_resources)

    def _process_resolved_resources(
        self,
        source_tf_resource: TFResource,
        resolved_destination_resource: List[Union[ConstantValue, ResolvedReference]],
    ):
        """
        Process the resolved destination resources.

        Parameters
        ----------
        source_tf_resource: TFResource
            The source Terraform resource.
        resolved_destination_resource: List[Union[ConstantValue, ResolvedReference]]
            The resolved destination resources to be processed for the input source resource.

        Returns
        --------
        List[Dict[str, str]]:
            The list of destination resources after processing
        """
        LOG.debug(
            "Map the resolved destination resources %s to configuration source resource %s.",
            resolved_destination_resource,
            source_tf_resource.full_address,
        )
        destination_resources = []
        does_refer_to_constant_values = False
        does_refer_to_data_sources = False
        for resolved_dest_resource in resolved_destination_resource:
            # Skip ConstantValue destination reference, as it will be already handled by terraform plan command.
            if isinstance(resolved_dest_resource, ConstantValue):
                does_refer_to_constant_values = True
            elif isinstance(resolved_dest_resource, ResolvedReference):
                processed_dest_resources = self._process_reference_resource_value(
                    source_tf_resource, resolved_dest_resource
                )
                if not processed_dest_resources:
                    does_refer_to_data_sources = True
                destination_resources += processed_dest_resources

        if (does_refer_to_constant_values or does_refer_to_data_sources) and len(destination_resources) > 0:
            LOG.debug(
                "Source resource %s to is referring to destination resource using an "
                "expression mixing between constant value or data "
                "sources and other resources references. AWS SAM CLI "
                "could not determine this source resources destination.",
                source_tf_resource.full_address,
            )
            raise self._resource_pair.linking_exceptions.multiple_resource_linking_exception(
                resolved_destination_resource, source_tf_resource.full_address
            )

        return destination_resources

    def _update_mapped_parent_resource_with_resolved_child_resources(
        self, cfn_source_resources: List[Dict], destination_resources: List
    ):
        """
        Set the resolved destination resource list to the mapped source resources.

        Parameters
        ----------
        cfn_source_resources: TFResource
            The source CloudFormation resource to be updated.
        destination_resources: List
            The resolved destination resource values that will be used as a value for the mapped CFN resource attribute.
        """
        LOG.debug(
            "Set the resolved destination resources %s to the cfn source resources %s",
            destination_resources,
            cfn_source_resources,
        )
        for cfn_source_resource in cfn_source_resources:
            LOG.debug("Process the source resource %s", cfn_source_resource)
            # Add the resolved dest resource list as it is to the mapped
            # source resource that does not have any dest resources defined
            if not cfn_source_resource["Properties"].get(self._resource_pair.source_link_field_name):
                LOG.debug("The source %s does not have any destination resources defined.", cfn_source_resource)
                cfn_source_resource["Properties"][self._resource_pair.source_link_field_name] = destination_resources
                continue

            # Check if the the mapped destination resource list contains any
            # arn value for one of the resolved destination resource to replace it.
            for dest_resource in destination_resources:
                # resolve the destination arn string to check if it is already there
                # in the CFN source resource destination property logical id will be always in terraform values, as we
                # do not consider the references to destination resources that do not exist in the
                # terraform planned values list as it means that this destination resource will not be created.
                LOG.debug(
                    "Check if the destination resource %s is already defined in source resource % property.",
                    dest_resource,
                    cfn_source_resource,
                )
                dest_arn = (
                    self._resource_pair.destination_resource_tf[dest_resource["Ref"]].get("values", {}).get("arn")
                )

                # The resolved dest resource is a reference to a dest resource
                # which has not yet been applied, so there is no ARN value yet.
                if not dest_arn:
                    LOG.debug(
                        "The destination resource %s is not applied yet, and does not have ARN property.", dest_resource
                    )
                    cfn_source_resource["Properties"][self._resource_pair.source_link_field_name].append(dest_resource)
                    continue

                # try to find a destination resource arn that equals the resolved
                # destination resource arn so we can replace it with Ref value.
                try:
                    dest_resource_index = (
                        cfn_source_resource["Properties"]
                        .get(self._resource_pair.source_link_field_name, [])
                        .index(dest_arn)
                    )
                    LOG.debug(
                        "The destination resource %s has the arn value %s that exists in source resource %s property.",
                        dest_resource,
                        dest_arn,
                        cfn_source_resource,
                    )
                    cfn_source_resource["Properties"][self._resource_pair.source_link_field_name][
                        dest_resource_index
                    ] = dest_resource
                except ValueError:
                    # there is no matching destination resource ARN.
                    LOG.debug(
                        "The destination resource %s has the arn value %s that "
                        "does not exist in source resource %s property.",
                        dest_resource,
                        dest_arn,
                        cfn_source_resource,
                    )
                    cfn_source_resource["Properties"][self._resource_pair.source_link_field_name].append(dest_resource)

    def _process_reference_resource_value(
        self, source_tf_resource: TFResource, resolved_destination_resource: ResolvedReference
    ):
        """
        Process the a reference destination resource value of type ResolvedReference.

        Parameters
        ----------
        source_tf_resource: TFResource
            The source Terraform resource.
        resolved_destination_resource: ResolvedReference
            The resolved destination resource reference.

        Returns
        -------
        List[Dict[str, str]]
            The resolved values that will be used as a value for the mapped CFN resource attribute.
        """
        LOG.debug("Process the reference destination resources %s.", resolved_destination_resource.value)
        # skip processing the data source block, as it should be mapped while executing the terraform plan command.
        if resolved_destination_resource.value.startswith(DATA_RESOURCE_ADDRESS_PREFIX):
            LOG.debug(
                "Skip processing the reference destination resource %s, as it is referring to a data resource",
                resolved_destination_resource.value,
            )
            return []

        # resolved reference is a local variable
        if resolved_destination_resource.value.startswith(TERRAFORM_LOCAL_VARIABLES_ADDRESS_PREFIX):
            LOG.debug("AWS SAM CLI could not process the Local variables %s", resolved_destination_resource.value)
            raise self._resource_pair.linking_exceptions.local_variable_linking_exception(
                resolved_destination_resource.value, source_tf_resource.full_address
            )

        # Valid destination resource
        if resolved_destination_resource.value.startswith(self._resource_pair.terraform_resource_type_prefix):
            LOG.debug("Process the destination resource %s", resolved_destination_resource.value)
            if not resolved_destination_resource.value.endswith("arn"):
                LOG.debug(
                    "The used property in reference %s is not an ARN property", resolved_destination_resource.value
                )
                raise InvalidResourceLinkingException(
                    f"Could not use the value {resolved_destination_resource.value} as a "
                    f"destination resource for the source resource "
                    f"{source_tf_resource.full_address}. The source resource "
                    f"value should refer to valid destination resource ARN property."
                )

            tf_dest_res_name = resolved_destination_resource.value[
                len(self._resource_pair.terraform_resource_type_prefix) : -len(".arn")
            ]
            if resolved_destination_resource.module_address:
                tf_dest_resource_full_address = (
                    f"{resolved_destination_resource.module_address}."
                    f"{self._resource_pair.terraform_resource_type_prefix}"
                    f"{tf_dest_res_name}"
                )
            else:
                tf_dest_resource_full_address = (
                    f"{self._resource_pair.terraform_resource_type_prefix}{tf_dest_res_name}"
                )
            cfn_dest_resource_logical_id = build_cfn_logical_id(tf_dest_resource_full_address)
            LOG.debug(
                "The logical id of the resource referred by %s is %s",
                resolved_destination_resource.value,
                cfn_dest_resource_logical_id,
            )

            # validate that the found dest resource is in mapped dest resources, which means that it is created.
            # The resource can be defined in the TF plan configuration, but will not be created.
            dest_resources = []
            if cfn_dest_resource_logical_id in self._resource_pair.destination_resource_tf:
                LOG.debug(
                    "The resource referred by %s can be found in the mapped destination resources",
                    resolved_destination_resource.value,
                )
                dest_resources.append({"Ref": cfn_dest_resource_logical_id})
            return dest_resources
        # it means the source resource is referring to a wrong destination resource type
        LOG.debug(
            "The used reference %s is not the correct destination resource type.", resolved_destination_resource.value
        )
        raise InvalidResourceLinkingException(
            f"Could not use the value {resolved_destination_resource.value} as a destination for the source resource "
            f"{source_tf_resource.full_address}. The source resource value should refer to valid destination ARN "
            f"property."
        )


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
    module = TFModule(None, None, {}, {}, {}, {})

    module.full_address = _build_module_full_address(module_name, parent_module_address)
    LOG.debug("Parsing module:` %s", module.full_address or "root")

    if not module_configuration:
        raise InvalidResourceLinkingException(f"No module configuration for module: {module.full_address or 'root'}")

    LOG.debug("Parsing module variables")
    module.variables = _build_module_variables_from_configuration(module_configuration, input_variables)

    LOG.debug("Parsing module resources")
    module.resources = _build_module_resources_from_configuration(module_configuration, module)

    LOG.debug("Parsing module outputs")
    module.outputs = _build_module_outputs_from_configuration(module_configuration)

    LOG.debug("Parsing module calls")
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


def _build_module_resources_from_configuration(module_configuration: Dict, module: TFModule) -> Dict[str, TFResource]:
    """
    Builds and returns module TFResources using a module terraform configuration

    Parameters
    ==========
    module_configuration: dict
        The module object from the terraform configuration
    module: TFModule
        The TFModule whose resources we're parsing

    Returns
    =======
    Dict[TFResource]
        Dictionary of TFResource for the parsed resources from the config, and the key is the resource address
    """
    module_resources = {}

    config_resources = module_configuration.get("resources", [])
    for config_resource in config_resources:
        resource_attributes: Dict[str, Expression] = {}

        expressions = config_resource.get("expressions", {})
        for expression_name, expression_value in expressions.items():
            # we do not process the attributes of type dictionary
            # Todo add dictionary type attributes post beta
            if isinstance(expression_value, list):
                LOG.debug("Skip processing the attribute %s as its value is a map.", expression_name)
                continue

            parsed_expression = _build_expression_from_configuration(expression_value)
            if parsed_expression:
                resource_attributes[expression_name] = parsed_expression

        resource_address = config_resource.get("address")
        resource_type = config_resource.get("type")
        module_resources[resource_address] = TFResource(resource_address, resource_type, module, resource_attributes)

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
        if parsed_expression:
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
            if parsed_expression:
                module_call_input_variables[expression_name] = parsed_expression

        module_call_module_config = module_call_value.get("module", {})
        module_call_built_module = _build_module(
            module_call_name, module_call_module_config, module_call_input_variables, module.full_address
        )

        module_call_built_module.parent_module = module
        child_modules[module_call_name] = module_call_built_module

    return child_modules


def _build_expression_from_configuration(expression_configuration: Dict) -> Optional[Expression]:
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

    parsed_expression: Optional[Expression] = None

    if constant_value is not None:
        parsed_expression = ConstantValue(constant_value)
    elif references is not None:
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
    ----------
    address : str
        The address to clean

    Returns
    -------
    str
        The address clean of indices
    """
    return COMPILED_REGULAR_EXPRESSION.sub("", address)


def _resolve_module_output(module: TFModule, output_name: str) -> List[Union[ConstantValue, ResolvedReference]]:
    """
    Resolves any references in the output section of the module

    Parameters
    ----------
    module : Module
        The module with outputs to search
    output_name : str
        The value to resolve

    Returns
    -------
    List[Union[ConstantValue, ResolvedReference]]
        A list of resolved values
    """
    results: List[Union[ConstantValue, ResolvedReference]] = []

    output = module.outputs.get(output_name)

    if not output:
        raise InvalidResourceLinkingException(f"Output {output_name} was not found in module {module.full_address}")

    output_value = output.value

    LOG.debug("Resolving output {%s} for module {%s}", output_name, module.full_address)

    if isinstance(output, ConstantValue):
        LOG.debug(
            "Resolved constant value {%s} for module {%s} for output {%s}",
            output.value,
            module.full_address,
            output_name,
        )

        results.append(output)
    elif isinstance(output, References):
        LOG.debug("Found references for module {%s} for output {%s}", module.full_address, output_name)

        cleaned_references = _clean_references_list(output_value)

        for reference in cleaned_references:
            if reference.startswith("var."):
                LOG.debug(
                    "Resolving variable reference {%s} for module {%s} for output {%s}",
                    reference,
                    module.full_address,
                    output_name,
                )

                stripped_reference = _get_configuration_address(reference[reference.find(".") + 1 :])
                results += _resolve_module_variable(module, stripped_reference)
            elif reference.startswith("module."):
                LOG.debug(
                    "Resolving module reference {%s} for module {%s} for output {%s}",
                    reference,
                    module.full_address,
                    output_name,
                )

                # validate that the reference is in the format: module.name.output
                if re.fullmatch(r"module(?:\.[^\.]+){2}", reference) is None:
                    raise InvalidResourceLinkingException(
                        f"Module {module.full_address} contains an invalid reference {reference}"
                    )

                # module.bbb.ccc => bbb
                module_name = reference[reference.find(".") + 1 : reference.rfind(".")]
                # module.bbb.ccc => ccc
                output_name = reference[reference.rfind(".") + 1 :]

                stripped_reference = _get_configuration_address(module_name)

                if not module.child_modules:
                    raise InvalidResourceLinkingException(
                        f"Module {module.full_address} does not have child modules defined"
                    )

                child_module = module.child_modules.get(stripped_reference)

                if not child_module:
                    raise InvalidResourceLinkingException(
                        f"Module {module.full_address} does not have {stripped_reference} as a child module"
                    )

                results += _resolve_module_output(child_module, output_name)
            else:
                LOG.debug(
                    "Resolved reference {%s} for module {%s} for output {%s}",
                    reference,
                    module.full_address,
                    output_name,
                )

                results.append(ResolvedReference(reference, module.full_address))

    return results


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
                    # using .get() gives us Optional[TFModule], if conditional already validates child module exists
                    # access list directly instead
                    child_module = module.parent_module.child_modules[config_module_name]
                    results += _resolve_module_output(child_module, output_name)
                else:
                    raise InvalidResourceLinkingException(f"Couldn't find child module {config_module_name}.")
            # this means either a resource, data source, or local.variables.
            elif module.parent_module:
                results.append(ResolvedReference(reference, module.parent_module.full_address))
            else:
                raise InvalidResourceLinkingException("Resource linking entered an invalid state.")

    return results


def _resolve_resource_attribute(
    resource: TFResource, attribute_name: str
) -> List[Union[ConstantValue, ResolvedReference]]:
    """
    Return a list of the values that resolve the passed attribute name in the input terraform resource configuration

    Parameters
    ----------
    resource: TFResource
        A terraform resource

    attribute_name: str
        The attribute name that needs to be resolved.

    Returns
    -------
    List[Union[ConstantValue, ResolvedReference]]
        A list of combination of constant values and/or references to other terraform resources attributes.
    """

    results: List[Union[ConstantValue, ResolvedReference]] = []
    LOG.debug(
        "Resolving resource attribute for resource (%s) and attribute (%s)", resource.full_address, attribute_name
    )

    attribute_value = resource.attributes.get(attribute_name)
    if attribute_value is None:
        LOG.debug("The value of the attribute %s is None for resource %s", attribute_name, resource.full_address)
        return results

    if not isinstance(attribute_value, ConstantValue) and not isinstance(attribute_value, References):
        raise InvalidResourceLinkingException(
            message=f"The attribute {attribute_name} has unexpected type in resource {resource.full_address}."
        )

    # check the possible constant value for this attribute
    if isinstance(attribute_value, ConstantValue):
        LOG.debug(
            "Found a constant value (%s) for attribute (%s) in resource (%s)",
            attribute_value.value,
            attribute_name,
            resource.full_address,
        )
        results.append(ConstantValue(attribute_value.value))
        return results

    # resolve the attribute reference value
    LOG.debug(
        "Found references (%s) for attribute (%s) in resource (%s)",
        attribute_value.value,
        attribute_name,
        resource.full_address,
    )
    cleaned_references = _clean_references_list(attribute_value.value)

    for reference in cleaned_references:
        # refer to a variable passed to this resource module from its parent module
        if reference.startswith("var."):
            config_var_name = _get_configuration_address(reference[len("var.") :])
            LOG.debug("Traversing a variable reference: %s to variable named %s", reference, config_var_name)
            results += _resolve_module_variable(resource.module, config_var_name)

        # refer to another module output. This module will be defined in the same level as the resource
        elif reference.startswith("module."):
            # validate that the reference is in the format: module.name.output
            if re.fullmatch(r"module(?:\.[^\.]+){2}", reference) is None:
                LOG.debug("Could not traverse the module output reference: %s", reference)
                raise InvalidResourceLinkingException(
                    f"The attribute {attribute_name} in Resource {resource.full_address} has an invalid reference "
                    f"{reference} value"
                )

            module_name = reference[reference.find(".") + 1 : reference.rfind(".")]
            config_module_name = _get_configuration_address(module_name)
            output_name = reference[reference.rfind(".") + 1 :]
            LOG.debug(
                "Traversing the module output reference: %s to the output named %s in module %s",
                reference,
                output_name,
                config_module_name,
            )

            if not resource.module.child_modules or resource.module.child_modules.get(config_module_name) is None:
                raise InvalidResourceLinkingException(
                    f"The input resource {resource.full_address} does not have a parent module, or we could not "
                    f"find the child module {config_module_name}."
                )

            results += _resolve_module_output(resource.module.child_modules[config_module_name], output_name)

        # this means either a resource, data source, or local.variables.
        else:
            results.append(ResolvedReference(reference, resource.module.full_address))
    return results
