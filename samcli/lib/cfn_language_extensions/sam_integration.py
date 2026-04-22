"""
SAM CLI integration for CloudFormation Language Extensions.

This module provides integration points for the AWS SAM ecosystem:
1. expand_language_extensions - Canonical Phase 1 entry point with template-level caching
2. process_template_for_sam_cli - Function for SAM CLI commands

The integration enables processing of language extensions (Fn::ForEach,
Fn::Length, Fn::ToJsonString, Fn::FindInMap with DefaultValue) before
SAM transforms are applied.
"""

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.cfn_language_extensions.api import create_default_pipeline
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException as LangExtInvalidTemplateException
from samcli.lib.cfn_language_extensions.models import (
    PseudoParameterValues,
    ResolutionMode,
    TemplateProcessingContext,
)
from samcli.lib.cfn_language_extensions.utils import (
    FOREACH_PREFIX,
    FOREACH_REQUIRED_ELEMENTS,
    is_foreach_key,
)

LOG = logging.getLogger(__name__)

# Transform name for AWS Language Extensions
AWS_LANGUAGE_EXTENSIONS_TRANSFORM = "AWS::LanguageExtensions"


@dataclass(frozen=True)
class LanguageExtensionResult:
    """
    Result of expanding CloudFormation Language Extensions in a template.

    This dataclass carries all Phase 1 outputs so that callers don't need
    to re-derive them.

    All template fields are independent deep copies.  Callers may mutate
    them freely without affecting the original input or other callers.

    Attributes
    ----------
    expanded_template : Dict[str, Any]
        The template with language extensions resolved (Fn::ForEach expanded, etc.)
    original_template : Dict[str, Any]
        Deep copy of the original template before expansion, preserving Fn::ForEach structure
    dynamic_artifact_properties : List
        List of DynamicArtifactProperty instances detected in Fn::ForEach blocks
    had_language_extensions : bool
        True if the template contained the AWS::LanguageExtensions transform
    """

    expanded_template: Dict[str, Any]
    original_template: Dict[str, Any]
    dynamic_artifact_properties: List = field(default_factory=list)
    had_language_extensions: bool = False


def check_using_language_extension(template: Optional[Dict]) -> bool:
    """
    Check if language extensions are set in the template's Transform.

    This is the canonical location for this check. SamTranslatorWrapper and
    PackageContext maintain backward-compatible aliases that delegate here.

    Parameters
    ----------
    template : dict or None
        The template to check

    Returns
    -------
    bool
        True if language extensions are set in the template, False otherwise
    """
    if template is None:
        return False
    transform = template.get("Transform")
    if transform:
        if isinstance(transform, str) and transform == AWS_LANGUAGE_EXTENSIONS_TRANSFORM:
            return True
        if isinstance(transform, list):
            for transform_instance in transform:
                if not isinstance(transform_instance, str):
                    continue
                if transform_instance == AWS_LANGUAGE_EXTENSIONS_TRANSFORM:
                    return True
    return False


def _build_pseudo_parameters(
    parameter_values: Optional[Dict[str, Any]],
) -> Optional[PseudoParameterValues]:
    """
    Build PseudoParameterValues from a parameter_values dictionary.

    Extracts AWS pseudo-parameters (AWS::Region, AWS::AccountId, etc.) from
    the parameter_values dict and returns a PseudoParameterValues instance.

    Parameters
    ----------
    parameter_values : dict or None
        Dictionary that may contain pseudo-parameter keys

    Returns
    -------
    PseudoParameterValues or None
        The pseudo parameters if any are present, None otherwise
    """
    if not parameter_values:
        return None

    region = parameter_values.get("AWS::Region")
    account_id = parameter_values.get("AWS::AccountId")
    stack_name = parameter_values.get("AWS::StackName")
    stack_id = parameter_values.get("AWS::StackId")
    partition = parameter_values.get("AWS::Partition")
    url_suffix = parameter_values.get("AWS::URLSuffix")

    if any([region, account_id, stack_name, stack_id, partition, url_suffix]):
        return PseudoParameterValues(
            region=str(region) if region else "",
            account_id=str(account_id) if account_id else "",
            stack_name=str(stack_name) if stack_name else None,
            stack_id=str(stack_id) if stack_id else None,
            partition=str(partition) if partition else None,
            url_suffix=str(url_suffix) if url_suffix else None,
        )

    return None


def contains_loop_variable(value: Any, loop_variable: str) -> bool:
    """
    Check if a value contains a reference to the loop variable.

    This checks for ${LoopVariable} patterns in strings, {"Ref": LoopVariable}
    dicts, and recursively checks nested structures.

    Parameters
    ----------
    value : Any
        The value to check
    loop_variable : str
        The loop variable name to look for

    Returns
    -------
    bool
        True if the value contains the loop variable, False otherwise
    """
    if isinstance(value, str):
        pattern = r"\$\{" + re.escape(loop_variable) + r"\}"
        return bool(re.search(pattern, value))
    elif isinstance(value, dict):
        # Check for {"Ref": loop_variable} — used in Fn::FindInMap after build
        if "Ref" in value and value["Ref"] == loop_variable:
            return True
        if "Fn::Sub" in value:
            sub_value = value["Fn::Sub"]
            if isinstance(sub_value, str):
                return contains_loop_variable(sub_value, loop_variable)
            elif isinstance(sub_value, list) and len(sub_value) >= 1:
                return contains_loop_variable(sub_value[0], loop_variable)
        return any(contains_loop_variable(v, loop_variable) for v in value.values())
    elif isinstance(value, list):
        return any(contains_loop_variable(item, loop_variable) for item in value)
    return False


def substitute_loop_variable(template_str: str, loop_variable: str, value: str) -> str:
    """
    Substitute the loop variable in a template string with a value.

    Parameters
    ----------
    template_str : str
        The template string containing ${LoopVariable} patterns
    loop_variable : str
        The loop variable name to substitute
    value : str
        The value to substitute

    Returns
    -------
    str
        The string with the loop variable substituted
    """
    pattern = r"\$\{" + re.escape(loop_variable) + r"\}"
    return re.sub(pattern, value, template_str)


def sanitize_resource_key_for_mapping(resource_key: str) -> str:
    """
    Sanitize a resource key for use as part of a CloudFormation Mapping name.

    Strips loop variable placeholders (e.g., ``${Svc}``) and removes any
    characters that are not alphanumeric, leaving a clean suffix.
    For example ``${Svc}Api`` becomes ``Api``, ``${Env}${Svc}Function`` becomes ``Function``.

    Raises
    ------
    ValueError
        If the sanitized result is empty (resource key has no static alphanumeric
        component), since this would fail to disambiguate mapping names.
    """
    # Remove ${...} placeholders
    cleaned = re.sub(r"\$\{[^}]*\}", "", resource_key)
    # Keep only alphanumeric characters
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", cleaned)
    if not cleaned:
        raise ValueError(
            f"Resource key '{resource_key}' produces an empty suffix after sanitization. "
            "Multiple resources in the same Fn::ForEach body share the same packageable "
            "property name, and each resource logical ID template must contain a static "
            "alphanumeric component (beyond loop variable placeholders) to generate unique "
            "mapping names."
        )
    return cleaned


def resolve_collection(
    collection_value: Any,
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Resolve a Fn::ForEach collection to a list of string values.

    Handles static lists and parameter references.

    Parameters
    ----------
    collection_value : Any
        The collection value from the Fn::ForEach block
    template : dict
        The full template dictionary (for resolving parameter references)
    parameter_values : dict, optional
        Parameter values for resolving !Ref to parameters

    Returns
    -------
    List[str]
        The resolved collection values, or empty list if cannot be resolved
    """
    if isinstance(collection_value, list):
        return [str(item) for item in collection_value if item is not None]

    if isinstance(collection_value, dict):
        if "Ref" in collection_value:
            param_name = collection_value["Ref"]
            return resolve_parameter_collection(param_name, template, parameter_values)

    return []


def resolve_parameter_collection(
    param_name: str,
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Resolve a parameter reference to a list of string values.

    Parameters
    ----------
    param_name : str
        The parameter name
    template : dict
        The full template dictionary
    parameter_values : dict, optional
        Parameter values (from --parameter-overrides)

    Returns
    -------
    List[str]
        The resolved collection values, or empty list if cannot be resolved
    """
    if parameter_values and param_name in parameter_values:
        value = parameter_values[param_name]
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",")]

    parameters = template.get("Parameters", {})
    if param_name in parameters:
        param_def = parameters[param_name]
        if isinstance(param_def, dict):
            default_value = param_def.get("Default")
            if isinstance(default_value, list):
                return [str(item) for item in default_value]
            if isinstance(default_value, str):
                return [item.strip() for item in default_value.split(",")]

    return []


def detect_foreach_dynamic_properties(
    foreach_key: str,
    foreach_value: Any,
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
    outer_loops: Optional[List[Tuple[str, str, List[str]]]] = None,
) -> List:
    """
    Detect dynamic artifact properties in a single Fn::ForEach block.

    Recursively descends into nested Fn::ForEach blocks within the body,
    tracking enclosing loops in ``outer_loops`` so that compound Mapping
    keys can be generated when the artifact property references multiple
    loop variables.

    Parameters
    ----------
    foreach_key : str
        The Fn::ForEach key (e.g., "Fn::ForEach::Services")
    foreach_value : Any
        The Fn::ForEach value (should be a list with 3 elements)
    template : dict
        The full template dictionary (for resolving parameter references)
    parameter_values : dict, optional
        Parameter values for resolving collections
    outer_loops : list of tuples, optional
        Enclosing loop info accumulated during recursion.
        Each tuple is ``(foreach_key, loop_variable, collection)``.

    Returns
    -------
    List[DynamicArtifactProperty]
        List of dynamic artifact property locations found in this ForEach block
        (including any nested blocks)
    """
    from samcli.lib.cfn_language_extensions.models import (
        PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES,
        DynamicArtifactProperty,
    )

    dynamic_properties: List = []

    if outer_loops is None:
        outer_loops = []

    if not isinstance(foreach_value, list) or len(foreach_value) != FOREACH_REQUIRED_ELEMENTS:
        return dynamic_properties

    loop_variable = foreach_value[0]
    collection_value = foreach_value[1]
    output_template = foreach_value[2]

    if not isinstance(loop_variable, str):
        return dynamic_properties

    if not isinstance(output_template, dict):
        return dynamic_properties

    loop_name = foreach_key.replace(FOREACH_PREFIX, "")

    # Check if collection is a parameter reference
    collection_is_parameter_ref = False
    collection_parameter_name: Optional[str] = None
    if isinstance(collection_value, dict) and "Ref" in collection_value:
        param_name = collection_value["Ref"]
        parameters = template.get("Parameters", {})
        if param_name in parameters:
            collection_is_parameter_ref = True
            collection_parameter_name = param_name

    collection = resolve_collection(collection_value, template, parameter_values)
    if not collection:
        return dynamic_properties

    # Build the outer_loops list for any nested calls
    current_outer_loops = outer_loops + [(foreach_key, loop_variable, collection)]

    for resource_key, resource_def in output_template.items():
        # Recurse into nested Fn::ForEach blocks
        if is_foreach_key(resource_key):
            nested_props = detect_foreach_dynamic_properties(
                resource_key, resource_def, template, parameter_values, outer_loops=current_outer_loops
            )
            dynamic_properties.extend(nested_props)
            continue

        if not isinstance(resource_def, dict):
            continue

        resource_type = resource_def.get("Type")
        if not isinstance(resource_type, str):
            continue

        artifact_properties = PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(resource_type)
        if not artifact_properties:
            continue

        properties = resource_def.get("Properties", {})
        if not isinstance(properties, dict):
            continue

        for prop_name in artifact_properties:
            prop_value = properties.get(prop_name)
            if prop_value is not None:
                if contains_loop_variable(prop_value, loop_variable):
                    dynamic_properties.append(
                        DynamicArtifactProperty(
                            foreach_key=foreach_key,
                            loop_name=loop_name,
                            loop_variable=loop_variable,
                            collection=collection,
                            resource_key=resource_key,
                            resource_type=resource_type,
                            property_name=prop_name,
                            property_value=prop_value,
                            collection_is_parameter_ref=collection_is_parameter_ref,
                            collection_parameter_name=collection_parameter_name,
                            outer_loops=list(outer_loops),
                        )
                    )

    return dynamic_properties


def detect_dynamic_artifact_properties(
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
) -> List:
    """
    Detect dynamic artifact properties in Fn::ForEach blocks.

    Scans all Fn::ForEach blocks in the Resources section and identifies
    any generated resources with packageable artifact properties that use
    the loop variable.

    Parameters
    ----------
    template : dict
        The template dictionary to scan
    parameter_values : dict, optional
        Parameter values for resolving collections

    Returns
    -------
    List[DynamicArtifactProperty]
        List of dynamic artifact property locations found in the template
    """
    dynamic_properties: List = []
    resources = template.get("Resources", {})
    if not isinstance(resources, dict):
        return dynamic_properties

    for key, value in resources.items():
        if is_foreach_key(key):
            props = detect_foreach_dynamic_properties(key, value, template, parameter_values)
            dynamic_properties.extend(props)

    return dynamic_properties


def expand_language_extensions(
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
) -> LanguageExtensionResult:
    """
    Canonical Phase 1 entry point for expanding CloudFormation Language Extensions.

    This function performs all Phase 1 work:
    1. Checks for AWS::LanguageExtensions transform
    2. Deep copies the original template before expansion
    3. Detects dynamic artifact properties in Fn::ForEach blocks
    4. Extracts pseudo-parameters from parameter_values
    5. Calls process_template_for_sam_cli() for expansion
    6. Returns a LanguageExtensionResult with all outputs

    Results are cached per ``(template_path, file_mtime, parameter_values_hash)``
    when *template_path* points to an existing file.  Cache hits return deep
    copies of the mutable fields so callers can freely mutate the result.

    If the template does not contain the AWS::LanguageExtensions transform,
    returns early with had_language_extensions=False and the original template
    unchanged.

    Parameters
    ----------
    template : dict
        The raw template dictionary
    parameter_values : dict, optional
        Template parameter values (may include pseudo-parameters like AWS::Region)

    Returns
    -------
    LanguageExtensionResult
        Result containing expanded_template, original_template,
        dynamic_artifact_properties, and had_language_extensions flag

    Raises
    ------
    InvalidSamDocumentException
        If the template contains invalid language extension syntax
    """
    if not check_using_language_extension(template):
        return LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )

    LOG.debug("Expanding CloudFormation Language Extensions (Phase 1)")

    # Detect dynamic artifact properties before expansion
    dynamic_properties = detect_dynamic_artifact_properties(template, parameter_values)

    # Extract pseudo-parameters from parameter_values
    pseudo_params = _build_pseudo_parameters(parameter_values)

    try:
        # process_template_for_sam_cli deep-copies internally,
        # so template is not mutated and can serve as the original.
        expanded_template = process_template_for_sam_cli(
            template,
            parameter_values=parameter_values,
            pseudo_parameters=pseudo_params,
        )

        LOG.debug("Successfully expanded CloudFormation Language Extensions")

        result = LanguageExtensionResult(
            expanded_template=copy.deepcopy(expanded_template),
            original_template=copy.deepcopy(template),
            dynamic_artifact_properties=dynamic_properties,
            had_language_extensions=True,
        )

        # Track language extensions usage for telemetry
        from samcli.lib.telemetry.event import EventName, EventTracker, UsedFeature

        EventTracker.track_event(EventName.USED_FEATURE.value, UsedFeature.CFN_LANGUAGE_EXTENSIONS.value)

        return result

    except Exception as e:
        if isinstance(e, LangExtInvalidTemplateException):
            LOG.error("Failed to expand CloudFormation Language Extensions: %s", str(e))
            raise InvalidSamDocumentException(str(e)) from e
        raise


def process_template_for_sam_cli(
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
    pseudo_parameters: Optional[PseudoParameterValues] = None,
) -> Dict[str, Any]:
    """
    Process a template for SAM CLI commands.

    This function is designed to be called from SAM CLI's template
    processing pipeline (e.g., in SamLocalStackProvider). It processes
    language extensions in partial resolution mode, preserving references
    that cannot be resolved locally.

    The function:
    1. Creates a processing context with partial resolution mode
    2. Runs the template through the default processing pipeline
    3. Returns the processed template with language extensions resolved

    Unlike the SAMLanguageExtensionsPlugin, this function does NOT remove
    the AWS::LanguageExtensions transform from the template. This is because
    SAM CLI may need to preserve the transform for deployment.

    Args:
        template: The raw template dictionary.
        parameter_values: Template parameter values.
        pseudo_parameters: AWS pseudo-parameter values.

    Returns:
        Processed template with language extensions resolved.

    """
    context = TemplateProcessingContext(
        fragment=copy.deepcopy(template),
        parameter_values=parameter_values or {},
        pseudo_parameters=pseudo_parameters,
        resolution_mode=ResolutionMode.PARTIAL,
    )

    pipeline = create_default_pipeline(context)
    return pipeline.process_template(context)
