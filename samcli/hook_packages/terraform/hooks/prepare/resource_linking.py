"""
Use Terraform plan to link resources together
e.g. linking layers to functions
"""
import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Type, Union

from samcli.hook_packages.terraform.hooks.prepare.exceptions import (
    FunctionLayerLocalVariablesLinkingLimitationException,
    GatewayAuthorizerToLambdaFunctionLocalVariablesLinkingLimitationException,
    GatewayAuthorizerToRestApiLocalVariablesLinkingLimitationException,
    GatewayMethodToGatewayAuthorizerLocalVariablesLinkingLimitationException,
    GatewayResourceToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    GatewayResourceToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException,
    GatewayResourceToApiGatewayMethodLocalVariablesLinkingLimitationException,
    GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
    InvalidResourceLinkingException,
    LambdaFunctionToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    LocalVariablesLinkingLimitationException,
    OneGatewayAuthorizerToLambdaFunctionLinkingLimitationException,
    OneGatewayAuthorizerToRestApiLinkingLimitationException,
    OneGatewayMethodToGatewayAuthorizerLinkingLimitationException,
    OneGatewayResourceToApiGatewayIntegrationLinkingLimitationException,
    OneGatewayResourceToApiGatewayIntegrationResponseLinkingLimitationException,
    OneGatewayResourceToApiGatewayMethodLinkingLimitationException,
    OneGatewayResourceToRestApiLinkingLimitationException,
    OneLambdaFunctionResourceToApiGatewayIntegrationLinkingLimitationException,
    OneLambdaLayerLinkingLimitationException,
    OneResourceLinkingLimitationException,
    OneRestApiToApiGatewayIntegrationLinkingLimitationException,
    OneRestApiToApiGatewayIntegrationResponseLinkingLimitationException,
    OneRestApiToApiGatewayMethodLinkingLimitationException,
    OneRestApiToApiGatewayStageLinkingLimitationException,
    RestApiToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    RestApiToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException,
    RestApiToApiGatewayMethodLocalVariablesLinkingLimitationException,
    RestApiToApiGatewayStageLocalVariablesLinkingLimitationException,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import INVOKE_ARN_FORMAT
from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    Expression,
    References,
    ResolvedReference,
    TFModule,
    TFResource,
)
from samcli.hook_packages.terraform.hooks.prepare.utilities import get_configuration_address
from samcli.hook_packages.terraform.lib.utils import build_cfn_logical_id

LAMBDA_FUNCTION_RESOURCE_ADDRESS_PREFIX = "aws_lambda_function."
LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX = "aws_lambda_layer_version."
API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX = "aws_api_gateway_rest_api."
API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX = "aws_api_gateway_resource."
API_GATEWAY_AUTHORIZER_RESOURCE_ADDRESS_PREFIX = "aws_api_gateway_authorizer."
TERRAFORM_LOCAL_VARIABLES_ADDRESS_PREFIX = "local."
DATA_RESOURCE_ADDRESS_PREFIX = "data."

LOG = logging.getLogger(__name__)


@dataclass
class ReferenceType:
    """
    This class is used to pass the linking attributes values to the callback functions.
    """

    value: str


@dataclass
class ExistingResourceReference(ReferenceType):
    """
    This class is used to pass the linking attributes values to the callback functions when the values are static values
    which means they are for an existing resources in AWS, and there is no matching resource in the customer TF Project.
    """

    value: str


@dataclass
class LogicalIdReference(ReferenceType):
    """
    This class is used to pass the linking attributes values to the callback functions when the values are Logical Ids
    for the destination resources defined in the customer TF project.
    """

    value: str


@dataclass
class ResourcePairExceptions:
    multiple_resource_linking_exception: Type[OneResourceLinkingLimitationException]
    local_variable_linking_exception: Type[LocalVariablesLinkingLimitationException]


@dataclass
class ResourceLinkingPair:
    source_resource_cfn_resource: Dict[str, List]
    source_resource_tf_config: Dict[str, TFResource]
    destination_resource_tf: Dict[str, Dict]
    tf_destination_attribute_name: str  # arn or id
    terraform_link_field_name: str
    cfn_link_field_name: str
    terraform_resource_type_prefix: str
    cfn_resource_update_call_back_function: Callable[[Dict, List[ReferenceType]], None]
    linking_exceptions: ResourcePairExceptions


class ResourceLinker:
    _resource_pair: ResourceLinkingPair

    def __init__(self, resource_pair):
        self._resource_pair = resource_pair

    def link_resources(self) -> None:
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

        This method determines first which resources can be linked using the terraform config approach, and the linking
        fields approach based on if the resource's dependencies are applied or not.

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

        # the config TF resource can map to different CFN resources like in case of using Count to define multiple
        # resources. This means after apply, each resource can have a different mapped child resources.
        # see the below example
        # resource "aws_lambda_function" "function1" {
        #   count = 2
        #   layers = ${count.index} == 0 ? [aws_lambda_layer_version.layer1.arn]: [aws_lambda_layer_version.layer2.arn]
        # }
        # resource "aws_lambda_layer_version" "layer1" { ... }
        # resource "aws_lambda_layer_version" "layer2" { ... }

        # It also means that it can happen that some of these resources depends on already applied children resources,
        # and other resources can depend on some unknown resource like if the customer update the HCL configuration
        # after applying it, and change one of the source resources to refer to a new child resource.

        # we need to filter out the applied resources and handle them using the actual linking fields mapping approach,
        # and the non-applied resources, we should use the linking algorithm based on the Config definition of the
        # resource

        # Filter out the applied and non-applied resources
        applied_cfn_resources = []
        non_applied_cfn_resources = []
        for cfn_resource in cfn_source_resources:
            linking_field_value = cfn_resource.get("Properties", {}).get(self._resource_pair.cfn_link_field_name)

            # if customer uses any non-applied resources to define the source resource property, Terraform will set
            # the property value to unknown in the Terraform plan.
            if linking_field_value is None:
                non_applied_cfn_resources.append(cfn_resource)
            else:
                applied_cfn_resources.append(cfn_resource)

        LOG.debug(
            "Link resource configuration %s that has these applied instances %s using linking fields approach.",
            source_tf_resource.full_address,
            applied_cfn_resources,
        )
        for applied_cfn_resource in applied_cfn_resources:
            self._link_using_linking_fields(applied_cfn_resource)

        self._link_using_terraform_config(source_tf_resource, non_applied_cfn_resources)

    def _link_using_terraform_config(self, source_tf_resource: TFResource, cfn_resources: List[Dict]):
        """
        Uses the Terraform Configuration to resolve the destination resources linked to the input terraform resource,
        then updates the cnf resources that match the input terraform resource.

        Parameters
        ----------
        source_tf_resource: TFResource
            The source resource Terraform configuration resource

        cfn_source_resources: List[Dict]
            A list of mapped source resources that are equivalent to the input terraform configuration source resource
        """

        if not cfn_resources:
            LOG.debug("No matching CFN resources for configuration %s", source_tf_resource.full_address)
            return

        LOG.debug(
            "Link resource configuration %s that has these applied instances %s using linking fields approach.",
            source_tf_resource.full_address,
            cfn_resources,
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
                "There are no destination resources defined for the source resource %s, skipping linking.",
                source_tf_resource.full_address,
            )

            return

        for cfn_resource in cfn_resources:
            self._resource_pair.cfn_resource_update_call_back_function(cfn_resource, dest_resources)

    def _link_using_linking_fields(self, cfn_resource: Dict) -> None:
        """
        Depends on that all the child resources of the source resource are applied, and so we do not need to traverse
        the terraform configuration to define the destination resource. We will depend on the actual values of the
        linking fields, and find the destination resource that has the same value.

        Parameters
        ----------
        cfn_source_resource: Dict
            A mapped CFN source resource
        """
        # get the constant values of the linking field from the cfn_resource
        values = cfn_resource.get("Properties", {}).get(self._resource_pair.cfn_link_field_name)

        LOG.debug(
            "Link the source resource %s using linking property %s that has the value %s",
            cfn_resource,
            self._resource_pair.cfn_link_field_name,
            values,
        )

        # some resources can be linked to only one child resource like rest apis.
        # make the resource values as a list to make processing easier.
        if not isinstance(values, List):
            values = [values]

        # build map between the destination linking field property values, and resources' logical ids
        child_resources_linking_attributes_logical_id_mapping = {}
        for logical_id, destination_resource in self._resource_pair.destination_resource_tf.items():
            linking_attribute_value = destination_resource.get("values", {}).get(
                self._resource_pair.tf_destination_attribute_name
            )
            if linking_attribute_value:
                child_resources_linking_attributes_logical_id_mapping[linking_attribute_value] = logical_id

        LOG.debug(
            "The map between destination resources linking field %s, and resources logical ids is %s",
            self._resource_pair.tf_destination_attribute_name,
            child_resources_linking_attributes_logical_id_mapping,
        )

        dest_resources = [
            LogicalIdReference(child_resources_linking_attributes_logical_id_mapping[value])
            if value in child_resources_linking_attributes_logical_id_mapping
            else ExistingResourceReference(value)
            for value in values
        ]

        if not dest_resources:
            LOG.debug("Skipping linking call back, no destination resources discovered.")
            return

        LOG.debug("The value of the source resource linking field after mapping %s", dest_resources)
        self._resource_pair.cfn_resource_update_call_back_function(cfn_resource, dest_resources)

    def _process_resolved_resources(
        self,
        source_tf_resource: TFResource,
        resolved_destination_resource: List[Union[ConstantValue, ResolvedReference]],
    ) -> List[ReferenceType]:
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

    def _process_reference_resource_value(
        self, source_tf_resource: TFResource, resolved_destination_resource: ResolvedReference
    ) -> List[ReferenceType]:
        """
        Process the reference destination resource value of type ResolvedReference.

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
            if not resolved_destination_resource.value.endswith(self._resource_pair.tf_destination_attribute_name):
                LOG.debug(
                    "The used property in reference %s is not an ARN property", resolved_destination_resource.value
                )
                raise InvalidResourceLinkingException(
                    f"Could not use the value {resolved_destination_resource.value} as a "
                    f"destination resource for the source resource "
                    f"{source_tf_resource.full_address}. The source resource "
                    f"value should refer to valid destination resource ARN property."
                )

            # we need to the resource name by removing the attribute part from the reference value
            # as an example the reference will be look like aws_layer_version.layer1.arn
            # and the attribute name is `arn`, we need to remove the last 4 characters `.arn`
            # which is the length of the linking attribute `arn` in our example adding one for the `.` character
            tf_dest_res_name = resolved_destination_resource.value[
                len(self._resource_pair.terraform_resource_type_prefix) : -len(
                    self._resource_pair.tf_destination_attribute_name
                )
                - 1
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
            dest_resources: List[ReferenceType] = []
            if cfn_dest_resource_logical_id in self._resource_pair.destination_resource_tf:
                LOG.debug(
                    "The resource referred by %s can be found in the mapped destination resources",
                    resolved_destination_resource.value,
                )
                dest_resources.append(LogicalIdReference(cfn_dest_resource_logical_id))
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

                stripped_reference = get_configuration_address(reference[reference.find(".") + 1 :])
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

                stripped_reference = get_configuration_address(module_name)

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
                config_var_name = get_configuration_address(reference[len("var.") :])
                if module.parent_module:
                    results += _resolve_module_variable(module.parent_module, config_var_name)
            # refer to another module output. This module will be defined in the same level as this module
            elif reference.startswith("module."):
                module_name = reference[reference.find(".") + 1 : reference.rfind(".")]
                config_module_name = get_configuration_address(module_name)
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
            config_var_name = get_configuration_address(reference[len("var.") :])
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
            config_module_name = get_configuration_address(module_name)
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


def _link_lambda_functions_to_layers_call_back(
    function_cfn_resource: Dict, referenced_resource_values: List[ReferenceType]
) -> None:
    """
    Callback function that used by the linking algorith to update a Lambda Function CFN Resource with
    the list of layers ids. Layers ids can be reference to other Layers resources define in the customer project,
    or ARN values to layers exist in customer's account.

    Parameters
    ----------
    function_cfn_resource: Dict
        Lambda Function CFN resource
    referenced_resource_values: List[ReferenceType]
        List of referenced layers either as the logical ids of layers resources defined in the customer project, or
        ARN values for actual layers defined in customer's account.
    """
    ref_list = [
        {"Ref": logical_id.value} if isinstance(logical_id, LogicalIdReference) else logical_id.value
        for logical_id in referenced_resource_values
    ]
    function_cfn_resource["Properties"]["Layers"] = ref_list


def _link_gateway_resources_to_gateway_rest_apis(
    gateway_resources_tf_configs: Dict[str, TFResource],
    gateway_resources_cfn_resources: Dict[str, List],
    rest_apis_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Rest API resource to each Gateway Resource resource.

    Parameters
    ----------
    gateway_resources_tf_configs: Dict[str, TFResource]
        Dictionary of configuration Gateway Resource resources
    gateway_resources_cfn_resources: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Resource
    rest_apis_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """
    resource_linking_pairs = [
        ResourceLinkingPair(
            source_resource_cfn_resource=gateway_resources_cfn_resources,
            source_resource_tf_config=gateway_resources_tf_configs,
            destination_resource_tf=rest_apis_terraform_resources,
            tf_destination_attribute_name="id",
            terraform_link_field_name="rest_api_id",
            cfn_link_field_name="RestApiId",
            terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
            linking_exceptions=ResourcePairExceptions(
                multiple_resource_linking_exception=OneGatewayResourceToRestApiLinkingLimitationException,
                local_variable_linking_exception=GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
            ),
        ),
        ResourceLinkingPair(
            source_resource_cfn_resource=gateway_resources_cfn_resources,
            source_resource_tf_config=gateway_resources_tf_configs,
            destination_resource_tf=rest_apis_terraform_resources,
            tf_destination_attribute_name="root_resource_id",
            terraform_link_field_name="parent_id",
            cfn_link_field_name="ResourceId",
            terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_parent_id_call_back,
            linking_exceptions=ResourcePairExceptions(
                multiple_resource_linking_exception=OneGatewayResourceToRestApiLinkingLimitationException,
                local_variable_linking_exception=GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
            ),
        ),
    ]
    for resource_linking_pair in resource_linking_pairs:
        ResourceLinker(resource_linking_pair).link_resources()


def _link_lambda_functions_to_layers(
    lambda_config_funcs_conf_cfn_resources: Dict[str, TFResource],
    lambda_funcs_conf_cfn_resources: Dict[str, List],
    lambda_layers_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Lambda Layers to each Lambda Function

    Parameters
    ----------
    lambda_config_funcs_conf_cfn_resources: Dict[str, TFResource]
        Dictionary of configuration lambda resources
    lambda_funcs_conf_cfn_resources: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Lambda functions
    lambda_layers_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneLambdaLayerLinkingLimitationException,
        local_variable_linking_exception=FunctionLayerLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=lambda_funcs_conf_cfn_resources,
        source_resource_tf_config=lambda_config_funcs_conf_cfn_resources,
        destination_resource_tf=lambda_layers_terraform_resources,
        tf_destination_attribute_name="arn",
        terraform_link_field_name="layers",
        cfn_link_field_name="Layers",
        terraform_resource_type_prefix=LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_lambda_functions_to_layers_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back(
    gateway_cfn_resource: Dict, referenced_rest_apis_values: List[ReferenceType]
) -> None:
    """
    Callback function that used by the linking algorithm to update an Api Gateway resource
    (Method, Integration, or Integration Response) CFN Resource with a reference to the Rest Api resource.

    Parameters
    ----------
    gateway_cfn_resource: Dict
        API Gateway CFN resource
    referenced_rest_apis_values: List[ReferenceType]
        List of referenced REST API either as the logical id of REST API resource defined in the customer project, or
        ARN values for actual REST API resource defined in customer's account. This list should always contain one
        element only.
    """
    # if the destination rest api list contains more than one element, so we have an issue in our linking logic
    if len(referenced_rest_apis_values) > 1:
        raise InvalidResourceLinkingException("Could not link multiple Rest APIs to one Gateway resource")

    if not referenced_rest_apis_values:
        LOG.info("Unable to find any references to Rest APIs, skip linking Gateway resources")
        return

    logical_id = referenced_rest_apis_values[0]
    gateway_cfn_resource["Properties"]["RestApiId"] = (
        {"Ref": logical_id.value} if isinstance(logical_id, LogicalIdReference) else logical_id.value
    )


def _link_gateway_resource_to_gateway_resource_call_back(
    gateway_resource_cfn_resource: Dict, referenced_gateway_resource_values: List[ReferenceType]
) -> None:
    """
    Callback function that is used by the linking algorithm to update an Api Gateway resource
    (Method, Integration, or Integration Response) CFN with a reference to the Gateway Resource resource.

    Parameters
    ----------
    gateway_resource_cfn_resource: Dict
        API Gateway resource CFN resource
    referenced_gateway_resource_values: List[ReferenceType]
        List of referenced Gateway Resources either as the logical id of Gateway Resource resource
        defined in the customer project, or ARN values for actual Gateway Resources resource defined
        in customer's account. This list should always contain one element only.
    """
    if len(referenced_gateway_resource_values) > 1:
        raise InvalidResourceLinkingException("Could not link multiple Gateway Resources to one Gateway resource")

    if not referenced_gateway_resource_values:
        LOG.info("Unable to find any references to the Gateway Resource, skip linking Gateway resources")
        return

    logical_id = referenced_gateway_resource_values[0]
    gateway_resource_cfn_resource["Properties"]["ResourceId"] = (
        {"Ref": logical_id.value} if isinstance(logical_id, LogicalIdReference) else logical_id.value
    )


def _link_gateway_resource_to_gateway_rest_apis_parent_id_call_back(
    gateway_cfn_resource: Dict, referenced_rest_apis_values: List[ReferenceType]
) -> None:
    """
    Callback function that used by the linking algorithm to update an Api Gateway Resource CFN Resource with
    a reference to the Rest Api resource.

    Parameters
    ----------
    gateway_cfn_resource: Dict
        API Gateway Method CFN resource
    referenced_rest_apis_values: List[ReferenceType]
        List of referenced REST API either as the logical id of REST API resource defined in the customer project, or
        ARN values for actual REST API resource defined in customer's account. This list should always contain one
        element only.
    """
    # if the destination rest api list contains more than one element, so we have an issue in our linking logic
    if len(referenced_rest_apis_values) > 1:
        raise InvalidResourceLinkingException("Could not link multiple Rest APIs to one Gateway resource")

    if not referenced_rest_apis_values:
        LOG.info("Unable to find any references to Rest APIs, skip linking Rest API to Gateway resource")
        return

    logical_id = referenced_rest_apis_values[0]
    gateway_cfn_resource["Properties"]["ParentId"] = (
        {"Fn::GetAtt": [logical_id.value, "RootResourceId"]}
        if isinstance(logical_id, LogicalIdReference)
        else logical_id.value
    )


def _link_gateway_methods_to_gateway_rest_apis(
    gateway_methods_config_resources: Dict[str, TFResource],
    gateway_methods_config_address_cfn_resources_map: Dict[str, List],
    rest_apis_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Rest API resource to each Gateway Method resource.

    Parameters
    ----------
    gateway_methods_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Methods
    gateway_methods_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Method
    rest_apis_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """

    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneRestApiToApiGatewayMethodLinkingLimitationException,
        local_variable_linking_exception=RestApiToApiGatewayMethodLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_methods_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_methods_config_resources,
        destination_resource_tf=rest_apis_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="rest_api_id",
        cfn_link_field_name="RestApiId",
        terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_stage_to_rest_api(
    gateway_stages_config_resources: Dict[str, TFResource],
    gateway_stages_config_address_cfn_resources_map: Dict[str, List],
    rest_apis_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Gateway Stage to each Gateway Rest API resource.

    Parameters
    ----------
    gateway_stages_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Stages
    gateway_stages_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Stage
    rest_apis_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources).
        The dictionary's key is the calculated logical id for each resource.
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneRestApiToApiGatewayStageLinkingLimitationException,
        local_variable_linking_exception=RestApiToApiGatewayStageLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_stages_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_stages_config_resources,
        destination_resource_tf=rest_apis_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="rest_api_id",
        cfn_link_field_name="RestApiId",
        terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_method_to_gateway_resource(
    gateway_method_config_resources: Dict[str, TFResource],
    gateway_method_config_address_cfn_resources_map: Dict[str, List],
    gateway_resources_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding
    Gateway Method resources to each Gateway Resource resources.

    Parameters
    ----------
    gateway_method_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Methods
    gateway_method_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Stage
    gateway_resources_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources).
        The dictionary's key is the calculated logical id for each resource.
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneGatewayResourceToApiGatewayMethodLinkingLimitationException,
        local_variable_linking_exception=GatewayResourceToApiGatewayMethodLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_method_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_method_config_resources,
        destination_resource_tf=gateway_resources_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="resource_id",
        cfn_link_field_name="ResourceId",
        terraform_resource_type_prefix=API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_resource_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_integrations_to_gateway_rest_apis(
    gateway_integrations_config_resources: Dict[str, TFResource],
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List],
    rest_apis_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Rest API resource to each Gateway Integration resource.

    Parameters
    ----------
    gateway_integrations_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Integrations
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Integration
    rest_apis_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """

    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneRestApiToApiGatewayIntegrationLinkingLimitationException,
        local_variable_linking_exception=RestApiToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_integrations_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_integrations_config_resources,
        destination_resource_tf=rest_apis_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="rest_api_id",
        cfn_link_field_name="RestApiId",
        terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_integrations_to_gateway_resource(
    gateway_integrations_config_resources: Dict[str, TFResource],
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List],
    gateway_resources_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding
    Gateway Resource resource to each Gateway Integration resource.

    Parameters
    ----------
    gateway_integrations_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Integrations
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Integration
    gateway_resources_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """

    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneGatewayResourceToApiGatewayIntegrationLinkingLimitationException,
        local_variable_linking_exception=GatewayResourceToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_integrations_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_integrations_config_resources,
        destination_resource_tf=gateway_resources_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="resource_id",
        cfn_link_field_name="ResourceId",
        terraform_resource_type_prefix=API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_resource_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_integration_to_function_call_back(
    gateway_integration_cfn_resource: Dict, referenced_gateway_resource_values: List[ReferenceType]
) -> None:
    """
    Callback function that is used by the linking algorithm to update an Api Gateway integration CFN Resource with
    a reference to the Lambda function resource through the AWS_PROXY integration.

    Parameters
    ----------
    gateway_integration_cfn_resource: Dict
        API Gateway integration CFN resource
    referenced_gateway_resource_values: List[ReferenceType]
        List of referenced Gateway Resources either as the logical id of Gateway Resource resource
        defined in the customer project, or ARN values for actual Gateway Resources resource defined
        in customer's account. This list should always contain one element only.
    """
    if len(referenced_gateway_resource_values) > 1:
        raise InvalidResourceLinkingException(
            "Could not link multiple Lambda functions to one Gateway integration resource"
        )

    if not referenced_gateway_resource_values:
        LOG.info(
            "Unable to find any references to Lambda functions, skip linking Lambda function to Gateway integration"
        )
        return

    logical_id = referenced_gateway_resource_values[0]
    gateway_integration_cfn_resource["Properties"]["Uri"] = (
        {"Fn::Sub": INVOKE_ARN_FORMAT.format(function_logical_id=logical_id.value)}
        if isinstance(logical_id, LogicalIdReference)
        else logical_id.value
    )


def _link_gateway_integrations_to_function_resource(
    gateway_integrations_config_resources: Dict[str, TFResource],
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List],
    lambda_function_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding
    Lambda function resource to each Gateway Integration resource.

    Parameters
    ----------
    gateway_integrations_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Integrations
    gateway_integrations_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Integration
    lambda_function_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Lambda function resources (not configuration resources).
        The dictionary's key is the calculated logical id for each resource.
    """
    # Filter out integrations that are not of type AWS_PROXY since we only care about those currently.
    aws_proxy_integrations_config_resources = {
        config_address: tf_resource
        for config_address, tf_resource in gateway_integrations_config_resources.items()
        if tf_resource.attributes.get("type", ConstantValue("")).value == "AWS_PROXY"
    }
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneLambdaFunctionResourceToApiGatewayIntegrationLinkingLimitationException,
        local_variable_linking_exception=LambdaFunctionToApiGatewayIntegrationLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_integrations_config_address_cfn_resources_map,
        source_resource_tf_config=aws_proxy_integrations_config_resources,
        destination_resource_tf=lambda_function_terraform_resources,
        tf_destination_attribute_name="invoke_arn",
        terraform_link_field_name="uri",
        cfn_link_field_name="Uri",
        terraform_resource_type_prefix=LAMBDA_FUNCTION_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_integration_to_function_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_integration_responses_to_gateway_rest_apis(
    gateway_integration_responses_config_resources: Dict[str, TFResource],
    gateway_integration_responses_config_address_cfn_resources_map: Dict[str, List],
    rest_apis_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Rest API resource to each Gateway Integration Response
    resource.

    Parameters
    ----------
    gateway_integration_responses_config_resources: Dict[str, TFResource]
        Dictionary of Terraform configuration Gateway Integration Response resources.
    gateway_integration_responses_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the internal mapped cfn Gateway
        Integration Response.
    rest_apis_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """

    exceptions = ResourcePairExceptions(
        OneRestApiToApiGatewayIntegrationResponseLinkingLimitationException,
        RestApiToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_integration_responses_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_integration_responses_config_resources,
        destination_resource_tf=rest_apis_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="rest_api_id",
        cfn_link_field_name="RestApiId",
        terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_integration_responses_to_gateway_resource(
    gateway_integration_responses_config_resources: Dict[str, TFResource],
    gateway_integration_responses_config_address_cfn_resources_map: Dict[str, List],
    gateway_resources_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all the resources and link the corresponding Gateway Resource resource to each Gateway Integration
    Response resource.
    Parameters
    ----------
    gateway_integration_responses_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Integration Response resources.
    gateway_integration_responses_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the internal mapped cfn Gateway
        Integration Response.
    gateway_resources_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform Rest API resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource.
    """

    exceptions = ResourcePairExceptions(
        OneGatewayResourceToApiGatewayIntegrationResponseLinkingLimitationException,
        GatewayResourceToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_integration_responses_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_integration_responses_config_resources,
        destination_resource_tf=gateway_resources_terraform_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="resource_id",
        cfn_link_field_name="ResourceId",
        terraform_resource_type_prefix=API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_resource_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_authorizer_to_lambda_function_call_back(
    gateway_authorizer_cfn_resource: Dict, lambda_function_resource_values: List[ReferenceType]
) -> None:
    """
    Callback function that is used by the linking algorithm to update a CFN Authorizer Resource with
    a reference to the Lambda function's invocation URI

    Parameters
    ----------
    gateway_authorizer_cfn_resource: Dict
        API Gateway Authorizer CFN resource
    lambda_function_resource_values: List[ReferenceType]
        List of referenced Lambda Functions either as the logical id of Lambda Function reosurces
        defined in the customer project, or ARN values for actual Lambda Functions defined
        in customer's account. This list should always contain one element only.
    """
    if len(lambda_function_resource_values) > 1:
        raise InvalidResourceLinkingException("Could not link multiple Lambda functions to one Gateway Authorizer")

    if not lambda_function_resource_values:
        LOG.info(
            "Unable to find any references to Lambda functions, skip linking Lambda function to Gateway Authorizer"
        )
        return

    logical_id = lambda_function_resource_values[0]
    gateway_authorizer_cfn_resource["Properties"]["AuthorizerUri"] = (
        {"Fn::Sub": INVOKE_ARN_FORMAT.format(function_logical_id=logical_id.value)}
        if isinstance(logical_id, LogicalIdReference)
        else logical_id.value
    )


def _link_gateway_authorizer_to_lambda_function(
    authorizer_config_resources: Dict[str, TFResource],
    authorizer_cfn_resources: Dict[str, List],
    lamda_function_resources: Dict[str, Dict],
) -> None:
    """
    Iterate through all the resources and link the corresponding Authorizer to each Lambda Function

    Parameters
    ----------
    authorizer_config_resources: Dict[str, TFResource]
        Dictionary of configuration Authorizer resources
    authorizer_cfn_resources: Dict[str, List]
        Dictionary containing resolved configuration address of CFN Authorizer resources
    lamda_function_resources: Dict[str, Dict]
        Dictionary of Terraform Lambda Function resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneGatewayAuthorizerToLambdaFunctionLinkingLimitationException,
        local_variable_linking_exception=GatewayAuthorizerToLambdaFunctionLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=authorizer_cfn_resources,
        source_resource_tf_config=authorizer_config_resources,
        destination_resource_tf=lamda_function_resources,
        tf_destination_attribute_name="invoke_arn",
        terraform_link_field_name="authorizer_uri",
        cfn_link_field_name="AuthorizerUri",
        terraform_resource_type_prefix=LAMBDA_FUNCTION_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_authorizer_to_lambda_function_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_authorizer_to_rest_api(
    authorizer_config_resources: Dict[str, TFResource],
    authorizer_cfn_resources: Dict[str, List],
    rest_api_resource: Dict[str, Dict],
) -> None:
    """
    Iterate through all the resources and link the corresponding Authorizer to each Rest Api

    Parameters
    ----------
    authorizer_config_resources: Dict[str, TFResource]
        Dictionary of configuration Authorizer resources
    authorizer_cfn_resources: Dict[str, List]
        Dictionary containing resolved configuration address of CFN Authorizer resources
    rest_api_resource: Dict[str, Dict]
        Dictionary of Terraform Rest Api resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneGatewayAuthorizerToRestApiLinkingLimitationException,
        local_variable_linking_exception=GatewayAuthorizerToRestApiLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=authorizer_cfn_resources,
        source_resource_tf_config=authorizer_config_resources,
        destination_resource_tf=rest_api_resource,
        tf_destination_attribute_name="id",
        terraform_link_field_name="rest_api_id",
        cfn_link_field_name="RestApiId",
        terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()


def _link_gateway_method_to_gateway_authorizer_call_back(
    gateway_method_cfn_resource: Dict, authorizer_resources: List[ReferenceType]
) -> None:
    """
    Callback function that is used by the linking algorithm to update a CFN Method Resource with
    a reference to the Lambda Authorizers's Id

    Parameters
    ----------
    gateway_method_cfn_resource: Dict
        API Gateway Method CFN resource
    authorizer_resources: List[ReferenceType]
        List of referenced Authorizers either as the logical id of Authorizer resources
        defined in the customer project, or ARN values for actual Authorizers defined
        in customer's account. This list should always contain one element only.
    """
    if len(authorizer_resources) > 1:
        raise InvalidResourceLinkingException("Could not link multiple Lambda Authorizers to one Gateway Method")

    if not authorizer_resources:
        LOG.info("Unable to find any references to Authorizers, skip linking Gateway Method to Lambda Authorizer")
        return

    logical_id = authorizer_resources[0]
    gateway_method_cfn_resource["Properties"]["AuthorizerId"] = (
        {"Ref": logical_id.value} if isinstance(logical_id, LogicalIdReference) else logical_id.value
    )


def _link_gateway_method_to_gateway_authorizer(
    gateway_method_config_resources: Dict[str, TFResource],
    gateway_method_config_address_cfn_resources_map: Dict[str, List],
    authorizer_resources: Dict[str, Dict],
) -> None:
    """
    Iterate through all the resources and link the corresponding
    Gateway Method resources to each Gateway Authorizer

    Parameters
    ----------
    gateway_method_config_resources: Dict[str, TFResource]
        Dictionary of configuration Gateway Methods
    gateway_method_config_address_cfn_resources_map: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Gateway Stage
    authorizer_resources: Dict[str, Dict]
        Dictionary of all Terraform Authorizer resources (not configuration resources).
        The dictionary's key is the calculated logical id for each resource.
    """
    exceptions = ResourcePairExceptions(
        multiple_resource_linking_exception=OneGatewayMethodToGatewayAuthorizerLinkingLimitationException,
        local_variable_linking_exception=GatewayMethodToGatewayAuthorizerLocalVariablesLinkingLimitationException,
    )
    resource_linking_pair = ResourceLinkingPair(
        source_resource_cfn_resource=gateway_method_config_address_cfn_resources_map,
        source_resource_tf_config=gateway_method_config_resources,
        destination_resource_tf=authorizer_resources,
        tf_destination_attribute_name="id",
        terraform_link_field_name="authorizer_id",
        cfn_link_field_name="AuthorizerId",
        terraform_resource_type_prefix=API_GATEWAY_AUTHORIZER_RESOURCE_ADDRESS_PREFIX,
        cfn_resource_update_call_back_function=_link_gateway_method_to_gateway_authorizer_call_back,
        linking_exceptions=exceptions,
    )
    ResourceLinker(resource_linking_pair).link_resources()
