"""
Data classes and enums for CloudFormation Language Extensions processing.

This module provides the core data structures used throughout the template
processing pipeline, including context objects, parsed template representation,
and configuration enums.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    # Avoid circular imports - ParsedTemplate is defined in this module
    pass


class ResolutionMode(Enum):
    """
    Controls how unresolvable references are handled during template processing.

    Attributes:
        FULL: Raise an error when encountering unresolvable references.
              Use this mode when you need complete resolution of all references.
        PARTIAL: Preserve unresolvable references in the output.
                 Use this mode for SAM integration where resource references
                 cannot be resolved locally.
    """

    FULL = "full"
    PARTIAL = "partial"


@dataclass
class PseudoParameterValues:
    """
    AWS pseudo-parameter values for template resolution.

    This class holds values for AWS pseudo-parameters that can be provided
    to simulate different deployment contexts during local template processing.

    Attributes:
        region: The AWS region (e.g., "us-east-1"). Required.
        account_id: The AWS account ID (e.g., "123456789012"). Required.
        stack_id: The CloudFormation stack ID. Optional.
        stack_name: The CloudFormation stack name. Optional.
        notification_arns: List of SNS topic ARNs for stack notifications. Optional.
        partition: AWS partition (e.g., "aws", "aws-cn", "aws-us-gov").
                   Derived from region if not provided.
        url_suffix: AWS URL suffix (e.g., "amazonaws.com", "amazonaws.com.cn").
                    Derived from region if not provided.

    Note:
        The partition and url_suffix can be automatically derived from the region
        during template processing if not explicitly provided.
    """

    region: str
    account_id: str
    stack_id: Optional[str] = None
    stack_name: Optional[str] = None
    notification_arns: Optional[List[str]] = None
    partition: Optional[str] = None
    url_suffix: Optional[str] = None


@dataclass
class ParsedTemplate:
    """
    Structured representation of a CloudFormation template.

    This class provides a typed representation of a CloudFormation template
    with all standard sections. Missing optional sections (Parameters, Mappings,
    Conditions, Outputs) are initialized as empty dictionaries.

    Note: The resources field can be None to allow validation to detect
    when the Resources section is missing or explicitly null in the template.

    Attributes:
        aws_template_format_version: The template format version string.
        description: The template description.
        parameters: Template parameters section.
        mappings: Template mappings section.
        conditions: Template conditions section.
        resources: Template resources section (can be None for validation).
        outputs: Template outputs section.
        transform: Transform declaration (string or list of strings).
    """

    aws_template_format_version: Optional[str] = None
    description: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    mappings: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    resources: Optional[Dict[str, Any]] = None  # Can be None for validation
    outputs: Dict[str, Any] = field(default_factory=dict)
    transform: Optional[Any] = None


@dataclass
class TemplateProcessingContext:
    """
    Mutable context passed through the processing pipeline.

    This class holds all the state needed during template processing,
    including the template fragment being processed, parameter values,
    pseudo-parameter values, and intermediate processing results.

    Attributes:
        fragment: The template content being processed as a dictionary.
        parameter_values: Values for template parameters.
        pseudo_parameters: AWS pseudo-parameter values for resolution.
        resolution_mode: How to handle unresolvable references.
        parsed_template: Structured template representation (set during processing).
        resolved_conditions: Evaluated condition values (set during processing).
        request_id: Unique identifier for the processing request.

    Note:
        The parsed_template and resolved_conditions fields are populated
        during processing by the respective processors in the pipeline.
    """

    fragment: Dict[str, Any]
    parameter_values: Dict[str, Any] = field(default_factory=dict)
    pseudo_parameters: Optional[PseudoParameterValues] = None
    resolution_mode: ResolutionMode = ResolutionMode.PARTIAL

    # Set during processing
    parsed_template: Optional[ParsedTemplate] = None
    resolved_conditions: Dict[str, bool] = field(default_factory=dict)
    request_id: str = ""

    # Track conditions being evaluated for circular reference detection
    _evaluating_conditions: set = field(default_factory=set)


# Packageable resource types and their artifact properties that can be dynamic in Fn::ForEach blocks.
# Derived from samcli.lib.utils.resources to keep one source of truth: any resource type
# whose property the artifact exporter packages MUST be merged back into the original
# (Fn::ForEach-preserving) template. See issue #9005 for the symptom of drift.
#
# Property names follow jmespath syntax (e.g., "Command.ScriptLocation" for nested keys),
# matching the canonical dicts. Consumers must use jmespath-aware get/set when copying.
def _build_packageable_resource_artifact_properties() -> Dict[str, List[str]]:
    from samcli.lib.utils.resources import (
        AWS_ECR_REPOSITORY,
        RESOURCES_WITH_IMAGE_COMPONENT,
        RESOURCES_WITH_LOCAL_PATHS,
    )

    result: Dict[str, List[str]] = {}
    for resource_type, props in RESOURCES_WITH_LOCAL_PATHS.items():
        result[resource_type] = list(props)
    for resource_type, props in RESOURCES_WITH_IMAGE_COMPONENT.items():
        # ECR::Repository.RepositoryName is not a packaged-artifact path.
        if resource_type == AWS_ECR_REPOSITORY:
            continue
        result.setdefault(resource_type, [])
        for prop in props:
            if prop not in result[resource_type]:
                result[resource_type].append(prop)
    return result


PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES: Dict[str, List[str]] = _build_packageable_resource_artifact_properties()


@dataclass(frozen=True)
class DynamicArtifactProperty:
    """
    Represents a dynamic artifact property found in a Fn::ForEach block.

    Attributes
    ----------
    foreach_key : str
        The Fn::ForEach key (e.g., "Fn::ForEach::Services")
    loop_name : str
        The loop name extracted from the foreach_key (e.g., "Services")
    loop_variable : str
        The loop variable name (e.g., "Name")
    collection : List[str]
        The collection values to iterate over (e.g., ["Users", "Orders", "Products"])
    resource_key : str
        The resource template key (e.g., "${Name}Service")
    resource_type : str
        The CloudFormation resource type (e.g., "AWS::Serverless::Function")
    property_name : str
        The artifact property name (e.g., "CodeUri")
    property_value : Any
        The original property value with loop variable (e.g., "./services/${Name}")
    collection_is_parameter_ref : bool
        True if the collection came from a parameter reference (!Ref ParamName),
        False if it's a static list. Used to emit warnings about package-time
        collection values being fixed.
    collection_parameter_name : Optional[str]
        The parameter name if collection_is_parameter_ref is True, None otherwise.
    outer_loops : List[Tuple[str, str, List[str]]]
        List of enclosing Fn::ForEach loops for nested ForEach scenarios.
        Each tuple is (foreach_key, loop_variable, collection) for an outer loop.
        Empty for top-level (non-nested) ForEach blocks.
        Used to determine if compound Mapping keys are needed when the dynamic
        artifact property references outer loop variables.
    """

    foreach_key: str
    loop_name: str
    loop_variable: str
    collection: List[str]
    resource_key: str
    resource_type: str
    property_name: str
    property_value: Any
    collection_is_parameter_ref: bool = False
    collection_parameter_name: Optional[str] = None
    outer_loops: List[Tuple[str, str, List[str]]] = field(default_factory=list)
