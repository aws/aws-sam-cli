"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""
import logging
import re
from typing import Dict, List, Optional, Union

from samcli.hook_packages.terraform.hooks.prepare.exceptions import (
    InvalidResourceLinkingException,
    LocalVariablesLinkingLimitationException,
    OneLambdaLayerLinkingLimitationException,
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


def _link_lambda_function_to_layer(
    function_tf_resource: TFResource, cfn_functions: List[Dict], tf_layers: Dict[str, Dict]
) -> None:
    """
    Resolve the lambda layer for the input lambda function configuration resource, and then update the equivalent cfn
    lambda functions list.
    The Lambda configuration resource in Terraform can match multiple actual resources in case if it was defined using
    count or for_each pattern.

    Parameters
    ----------
    function_tf_resource: TFResource
        The input lambda function terraform configuration resource

    cfn_functions: List[Dict]
        A list of mapped lambda functions that are equivalent to the input terraform configuration lambda function

    tf_layers: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource
    """

    LOG.debug(
        "Link function configuration %s layer that has these instances %s.",
        function_tf_resource.full_address,
        cfn_functions,
    )
    resolved_layers = _resolve_resource_attribute(function_tf_resource, "layers")
    LOG.debug("The resolved layers for function %s are %s", function_tf_resource.full_address, resolved_layers)
    layers = _process_resolved_layers(function_tf_resource, resolved_layers, tf_layers)

    # The agreed limitation to support only 1 lambda layer reference.
    if len(layers) > 1:
        LOG.debug(
            "AWS SAM CLI does not support mapping the lambda function %s to more than one layer.",
            function_tf_resource.full_address,
        )
        raise OneLambdaLayerLinkingLimitationException(layers, function_tf_resource.full_address)
    if not layers:
        LOG.debug("There are no layers defined for lambda function %s", function_tf_resource.full_address)
    else:
        _update_mapped_lambda_function_with_resolved_layers(cfn_functions, layers, tf_layers)


def _process_resolved_layers(
    function_tf_resource: TFResource,
    resolved_layers: List[Union[ConstantValue, ResolvedReference]],
    tf_layers: Dict[str, Dict],
) -> List[Dict[str, str]]:
    """
    Process the resolved layers.

    Parameters
    ----------
    function_tf_resource: TFResource
        The input lambda function terraform configuration resource

    resolved_layers: List[Union[ConstantValue, ResolvedReference]]
        The resolved layers to be processed for the input lambda function.

    tf_layers: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource

    Returns
    --------
    List[Dict[str, str]]:
        The list of layers after processing

    """
    LOG.debug(
        "Map the resolved layers %s to configuration function %s.", resolved_layers, function_tf_resource.full_address
    )
    layers = []
    does_refer_to_constant_values = False
    does_refer_to_data_sources = False
    for resolved_layer in resolved_layers:
        # Skip ConstantValue layers reference, as it will be already handled by terraform plan command.
        if isinstance(resolved_layer, ConstantValue):
            does_refer_to_constant_values = True
        elif isinstance(resolved_layer, ResolvedReference):
            processed_layers = _process_reference_layer_value(function_tf_resource, resolved_layer, tf_layers)
            if not processed_layers:
                does_refer_to_data_sources = True
            layers += processed_layers

    if (does_refer_to_constant_values or does_refer_to_data_sources) and len(layers) > 0:
        LOG.debug(
            "Lambda function %s to is referring to layers using an expression mixing between constant value or data "
            "sources and other resources references. AWS SAM CLI could not determine this lambda functions layers.",
            function_tf_resource.full_address,
        )
        raise OneLambdaLayerLinkingLimitationException(resolved_layers, function_tf_resource.full_address)

    return layers


def _process_reference_layer_value(
    function_tf_resource: TFResource, resolved_layer: ResolvedReference, tf_layers: Dict[str, Dict]
) -> List[Dict[str, str]]:
    """
    Process the layer value of type ResolvedReference.

    Parameters
    ----------
    function_tf_resource: TFResource
        The input lambda function terraform configuration resource

    resolved_layer: ResolvedReference
        The layer reference.

    tf_layers: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource

    Returns
    -------
    List[Dict[str, str]]
        The resolved layers values that will be used as a value for the mapped CFN function Layers attribute.

    """
    LOG.debug("Process the reference layer %s.", resolved_layer.value)
    # skip processing the data source block, as it should be mapped while executing the terraform plan command.
    if resolved_layer.value.startswith(DATA_RESOURCE_ADDRESS_PREFIX):
        LOG.debug("Skip processing the reference layer %s, as it is referring to a data resource", resolved_layer.value)
        return []

    # resolved reference is a local variable
    if resolved_layer.value.startswith(TERRAFORM_LOCAL_VARIABLES_ADDRESS_PREFIX):
        LOG.debug("AWS SAM CLI could not process the Local variables %s", resolved_layer.value)
        raise LocalVariablesLinkingLimitationException(resolved_layer.value, function_tf_resource.full_address)

    # Valid Layer resource
    if resolved_layer.value.startswith(LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX):
        LOG.debug("Process the Layer version resource %s", resolved_layer.value)
        if not resolved_layer.value.endswith("arn"):
            LOG.debug("The used property in reference %s is not an ARN property", resolved_layer.value)
            raise InvalidResourceLinkingException(
                f"Could not use the value {resolved_layer.value} as a Layer for lambda function "
                f"{function_tf_resource.full_address}. Lambda Function Layer value should refer to valid "
                f"lambda layer ARN property"
            )

        tf_layer_res_name = resolved_layer.value[len(LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX) : -len(".arn")]
        if resolved_layer.module_address:
            tf_layer_full_address = (
                f"{resolved_layer.module_address}.{LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX}" f"{tf_layer_res_name}"
            )
        else:
            tf_layer_full_address = f"{LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX}{tf_layer_res_name}"
        cfn_layer_logical_id = build_cfn_logical_id(tf_layer_full_address)
        LOG.debug("The logical id of the resource referred by %s is %s", resolved_layer.value, cfn_layer_logical_id)

        # validate that the found layer is in mapped layers resources, which means that it is created.
        # The resource can be defined in the TF plan configuration, but will not be created.
        layers = []
        if cfn_layer_logical_id in tf_layers:
            LOG.debug("The resource referred by %s can be found in the mapped layers resources", resolved_layer.value)
            layers.append({"Ref": cfn_layer_logical_id})
        return layers
    # it means the Lambda function is referring to a wrong layer resource type
    LOG.debug("The used reference %s is not a Layer Version resource.", resolved_layer.value)
    raise InvalidResourceLinkingException(
        f"Could not use the value {resolved_layer.value} as a Layer for lambda function "
        f"{function_tf_resource.full_address}. Lambda Function Layer value should refer to valid lambda layer ARN "
        f"property"
    )


def _update_mapped_lambda_function_with_resolved_layers(
    cfn_functions: List[Dict],
    layers: List[Dict[str, str]],
    tf_layers: Dict[str, Dict],
) -> None:
    """
    Set The resolved layers list to the mapped lambda functions.

    Parameters
    ----------
    cfn_functions: List[Dict]
        A list of mapped lambda functions that are equivalent to the input terraform configuration lambda function

    layers: List
        The resolved layers values that will be used as a value for the mapped CFN function Layers attribute.

    tf_layers: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource
    """
    LOG.debug("Set the resolved layers %s to the cfn functions %s", layers, cfn_functions)
    for cfn_func in cfn_functions:
        LOG.debug("Process the Lambda function %s", cfn_func)
        # Add the resolved layers list as it is to the mapped function that does not have any layers defined
        if not cfn_func["Properties"].get("Layers"):
            LOG.debug("The Lambda function %s does not have any layers defined.", cfn_func)
            cfn_func["Properties"]["Layers"] = layers
            continue

        # Check if the the mapped function layers list contains any arn value for one of the resolved layers to replace
        # it.
        for layer in layers:
            # resolve the layer arn string to check if it is already there in the CFN func layer property
            # layer logical id will be always in tf_layers, as we do not consider the references to layers that does not
            # exist in the tf_layers list as it means that this layer will not be created.
            LOG.debug("Check if the layer %s is already defined in function % layers.", layer, cfn_func)
            layer_arn = tf_layers[layer["Ref"]].get("values", {}).get("arn")

            # The resolved layer is a reference to a layers which is not applied yet, so there is no ARN value yet.
            if not layer_arn:
                LOG.debug("The layer %s is not applied yet, and does not have ARN property.", layer)
                cfn_func["Properties"]["Layers"].append(layer)
                continue

            # try to find a layer arn that equals the resolved layer arn so we can replace it with Ref value.
            try:
                layer_index = cfn_func["Properties"].get("Layers", []).index(layer_arn)
                LOG.debug(
                    "The layer %s has the arn value %s that exists in function %s layers.", layer, layer_arn, cfn_func
                )
                cfn_func["Properties"]["Layers"][layer_index] = layer
            except ValueError:
                # there is no matching layer ARN.
                LOG.debug(
                    "The layer %s has the arn value %s that does not exist in function %s layers.",
                    layer,
                    layer_arn,
                    cfn_func,
                )
                cfn_func["Properties"]["Layers"].append(layer)
