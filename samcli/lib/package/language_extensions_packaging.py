"""
Standalone functions for handling CloudFormation Language Extensions during packaging.

These functions were extracted from PackageContext to enable reuse in
CloudFormationStackResource.do_export() for nested stack packaging.
None of the functions use instance state — they are pure functions.
"""

import copy
import itertools
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import click

from samcli.lib.cfn_language_extensions.models import (
    PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES,
    DynamicArtifactProperty,
)
from samcli.lib.cfn_language_extensions.sam_integration import (
    contains_loop_variable,
    sanitize_resource_key_for_mapping,
    substitute_loop_variable,
)
from samcli.lib.cfn_language_extensions.utils import FOREACH_REQUIRED_ELEMENTS, is_foreach_key

LOG = logging.getLogger(__name__)

# Pre-compiled pattern for validating CloudFormation Mapping keys
_VALID_MAPPING_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def merge_language_extensions_s3_uris(
    original_template: Dict[str, Any],
    exported_template: Dict[str, Any],
    dynamic_properties: Optional[List[DynamicArtifactProperty]] = None,
) -> Dict[str, Any]:
    """
    Update the original template (with Fn::ForEach intact) with S3 URIs from the exported template.

    For templates with language extensions, we preserve the original Fn::ForEach structure
    but update artifact properties (CodeUri, ContentUri, etc.) with the S3 locations
    from the exported (expanded) template.

    For dynamic artifact properties (those using loop variables), we skip updating them
    here since they will be handled by the Mappings transformation.

    Parameters
    ----------
    original_template : dict
        The original template with Fn::ForEach constructs
    exported_template : dict
        The exported template with expanded resources and S3 URIs
    dynamic_properties : Optional[List[DynamicArtifactProperty]]
        List of dynamic artifact properties to skip (will be handled by Mappings)

    Returns
    -------
    dict
        The original template with updated S3 URIs
    """
    result = copy.deepcopy(original_template)

    # Build a set of (foreach_key, property_name) tuples for dynamic properties
    dynamic_prop_keys: set = set()
    if dynamic_properties:
        for prop in dynamic_properties:
            dynamic_prop_keys.add((prop.foreach_key, prop.property_name))

    # Only the Resources section needs S3 URI updates from the exported template.
    original_resources = result.get("Resources", {})
    exported_resources = exported_template.get("Resources", {})

    _update_resources_with_s3_uris(original_resources, exported_resources, dynamic_prop_keys)

    return result


def generate_and_apply_artifact_mappings(
    template: Dict[str, Any],
    dynamic_properties: List[DynamicArtifactProperty],
    exported_resources: Dict[str, Any],
    template_dir: str,
) -> Dict[str, Any]:
    """
    Generate Mappings for dynamic artifact properties and apply them to the template.

    This wraps ``_generate_artifact_mappings`` and ``_apply_artifact_mappings_to_template``
    into a single call for convenience.

    Parameters
    ----------
    template : dict
        The template to modify (will be modified in place)
    dynamic_properties : List[DynamicArtifactProperty]
        List of dynamic artifact properties detected in Fn::ForEach blocks
    exported_resources : dict
        The exported resources with S3 URIs from the expanded template
    template_dir : str
        The directory containing the template (for resolving relative paths)

    Returns
    -------
    dict
        The modified template with Mappings and Fn::FindInMap references
    """
    warn_parameter_based_collections(dynamic_properties)

    mappings, property_to_mapping = _generate_artifact_mappings(dynamic_properties, template_dir, exported_resources)

    return _apply_artifact_mappings_to_template(template, mappings, dynamic_properties, property_to_mapping)


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _update_resources_with_s3_uris(
    original_resources: Dict[str, Any],
    exported_resources: Dict[str, Any],
    dynamic_prop_keys: Optional[set] = None,
) -> None:
    """
    Update resources in the original template with S3 URIs from the exported template.

    Handles both regular resources and Fn::ForEach constructs.
    """
    for resource_key, resource_value in original_resources.items():
        if is_foreach_key(resource_key):
            _update_foreach_with_s3_uris(resource_key, resource_value, exported_resources, dynamic_prop_keys)
        elif isinstance(resource_value, dict) and resource_key in exported_resources:
            exported_resource = exported_resources.get(resource_key, {})
            _copy_artifact_uris(resource_value, exported_resource)


def _update_foreach_with_s3_uris(
    foreach_key: str,
    foreach_value: list,
    exported_resources: Dict[str, Any],
    dynamic_prop_keys: Optional[set] = None,
    outer_context: Optional[List[Tuple[str, List[str]]]] = None,
) -> None:
    """
    Update artifact URIs in a Fn::ForEach construct.

    For static artifact properties all expanded functions share the same S3 URI.
    Dynamic properties are skipped (handled by Mappings).
    """
    if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
        return

    loop_variable = foreach_value[0]
    collection = foreach_value[1]
    body = foreach_value[2]

    if not isinstance(loop_variable, str) or not isinstance(body, dict):
        return

    collection_values: List[str] = []
    if isinstance(collection, list):
        collection_values = [str(item) for item in collection if item is not None]

    if outer_context is None:
        outer_context = []
    current_outer_context = outer_context + [(loop_variable, collection_values)]

    for resource_template_key, resource_template in body.items():
        if isinstance(resource_template_key, str) and is_foreach_key(resource_template_key):
            _update_foreach_with_s3_uris(
                resource_template_key,
                resource_template,
                exported_resources,
                dynamic_prop_keys,
                outer_context=current_outer_context,
            )
            continue

        if not isinstance(resource_template, dict):
            continue

        properties = resource_template.get("Properties", {})

        expanded_key = _build_expanded_key(
            resource_template_key,
            loop_variable,
            collection_values,
            outer_context,
        )
        if not expanded_key or expanded_key not in exported_resources:
            continue

        exported_resource = exported_resources[expanded_key]
        if not isinstance(exported_resource, dict):
            continue
        exported_props = exported_resource.get("Properties", {})

        _copy_artifact_uris_for_type(
            properties, exported_props, resource_template.get("Type", ""), foreach_key, dynamic_prop_keys
        )


def _build_expanded_key(
    resource_template_key: str,
    loop_variable: str,
    collection_values: List[str],
    outer_context: Optional[List[Tuple[str, List[str]]]],
) -> Optional[str]:
    """Build an expanded resource key by substituting the first value from each loop."""
    if not collection_values:
        return None
    expanded_key = resource_template_key
    if outer_context:
        for ovar, ocoll in outer_context:
            if not ocoll:
                return None
            expanded_key = substitute_loop_variable(expanded_key, ovar, ocoll[0])
    expanded_key = substitute_loop_variable(expanded_key, loop_variable, collection_values[0])
    return expanded_key


def _copy_artifact_uris(original_resource: Dict, exported_resource: Dict) -> None:
    """Copy artifact URIs from exported resource to original resource."""
    original_props = original_resource.get("Properties", {})
    exported_props = exported_resource.get("Properties", {})
    resource_type = original_resource.get("Type", "")
    _copy_artifact_uris_for_type(original_props, exported_props, resource_type)


def _copy_artifact_uris_for_type(
    original_props: Dict,
    exported_props: Dict,
    resource_type: str,
    foreach_key: Optional[str] = None,
    dynamic_prop_keys: Optional[set] = None,
) -> bool:
    """
    Copy artifact URIs based on resource type.

    Uses PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES to determine which
    properties to copy, avoiding a long elif chain.
    """
    prop_names = PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(resource_type)
    if not prop_names:
        return False

    copied = False
    for prop_name in prop_names:
        if prop_name not in exported_props:
            continue
        if dynamic_prop_keys and foreach_key and (foreach_key, prop_name) in dynamic_prop_keys:
            continue
        original_props[prop_name] = exported_props[prop_name]
        copied = True

    return copied


# ---------------------------------------------------------------------------
# Mappings generation
# ---------------------------------------------------------------------------


def _sanitize_resource_key_for_mapping(resource_key: str) -> str:
    """Delegate to the shared helper in sam_integration."""
    return sanitize_resource_key_for_mapping(resource_key)


def _nesting_path(prop: DynamicArtifactProperty) -> str:
    """Chain of ancestor loop names + current loop name.

    Non-nested: ``"Services"``.  Nested under Envs: ``"EnvsServices"``.
    """
    parts = [ok.replace("Fn::ForEach::", "") for ok, _, _ in prop.outer_loops]
    parts.append(prop.loop_name)
    return "".join(parts)


def _prop_identity(prop: DynamicArtifactProperty) -> Tuple:
    """Hashable key that uniquely identifies a DynamicArtifactProperty.

    Uses outer loop keys to distinguish same-named inner loops nested under
    different parents.
    """
    outer_keys = tuple(ok for ok, _, _ in prop.outer_loops)
    return (outer_keys, prop.foreach_key, prop.property_name, prop.resource_key)


def _compute_mapping_name(
    prop: DynamicArtifactProperty,
    collision_groups: Dict[Tuple[str, str], int],
) -> str:
    """
    Compute a unique Mapping name, adding a resource-key suffix when multiple
    resources share the same (loop_name, property_name).

    The suffix is derived from the resource logical ID template (resource_key)
    with loop variable placeholders stripped.  This is guaranteed unique because
    resource keys are unique within a ForEach body.

    Examples (collision on DefinitionUri in Fn::ForEach::Services):
      - resource_key="${Svc}Api"          -> SAMDefinitionUriServicesApi
      - resource_key="${Svc}StateMachine"  -> SAMDefinitionUriServicesStateMachine

    When there is no collision the base name is returned unchanged for backward
    compatibility.
    """
    npath = _nesting_path(prop)
    base_name = f"SAM{prop.property_name}{npath}"
    key = (npath, prop.property_name)
    if collision_groups.get(key, 0) <= 1:
        return base_name
    suffix = _sanitize_resource_key_for_mapping(prop.resource_key)
    return f"{base_name}{suffix}"


def _generate_artifact_mappings(
    dynamic_properties: List[DynamicArtifactProperty],
    template_dir: str,
    exported_resources: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Dict[str, str]]], Dict[Tuple, str]]:
    """
    Generate Mappings section for dynamic artifact properties in Fn::ForEach blocks.

    Returns
    -------
    Tuple
        (mappings dict, property_to_mapping dict keyed by _prop_identity())
    """
    mappings: Dict[str, Dict[str, Dict[str, str]]] = {}
    property_to_mapping: Dict[Tuple, str] = {}

    # Pre-pass: detect collisions where multiple resources share (nesting_path, property_name)
    collision_groups: Dict[Tuple[str, str], int] = Counter(
        (_nesting_path(p), p.property_name) for p in dynamic_properties
    )

    for prop in dynamic_properties:
        _validate_mapping_key_compatibility(prop)

        mapping_name = _compute_mapping_name(prop, collision_groups)

        if mapping_name not in mappings:
            mappings[mapping_name] = {}

        uses_outer_vars = False
        referenced_outer_loops: List[Tuple[str, str, List[str]]] = []
        if prop.outer_loops:
            for outer_key, outer_var, outer_coll in prop.outer_loops:
                if contains_loop_variable(prop.property_value, outer_var):
                    uses_outer_vars = True
                    referenced_outer_loops.append((outer_key, outer_var, outer_coll))

        if uses_outer_vars and referenced_outer_loops:
            outer_collections = [ol[2] for ol in referenced_outer_loops]
            outer_vars = [ol[1] for ol in referenced_outer_loops]

            for combo in itertools.product(*outer_collections, prop.collection):
                outer_values = list(combo[:-1])
                inner_value = combo[-1]
                compound_key = "-".join(list(outer_values) + [inner_value])

                expanded_resource_key = prop.resource_key
                for outer_var, outer_val in zip(outer_vars, outer_values):
                    expanded_resource_key = substitute_loop_variable(expanded_resource_key, outer_var, outer_val)
                expanded_resource_key = substitute_loop_variable(expanded_resource_key, prop.loop_variable, inner_value)

                s3_uri = _find_artifact_uri_for_resource(
                    exported_resources, expanded_resource_key, prop.resource_type, prop.property_name
                )

                if s3_uri:
                    mappings[mapping_name][compound_key] = {prop.property_name: s3_uri}
                else:
                    LOG.warning(
                        "Could not find S3 URI for %s in expanded resource %s",
                        prop.property_name,
                        expanded_resource_key,
                    )
        else:
            for collection_value in prop.collection:
                expanded_resource_key = prop.resource_key

                if prop.outer_loops:
                    for _, outer_var, outer_coll in prop.outer_loops:
                        if outer_coll:
                            expanded_resource_key = substitute_loop_variable(
                                expanded_resource_key, outer_var, outer_coll[0]
                            )

                expanded_resource_key = substitute_loop_variable(
                    expanded_resource_key, prop.loop_variable, collection_value
                )

                s3_uri = _find_artifact_uri_for_resource(
                    exported_resources, expanded_resource_key, prop.resource_type, prop.property_name
                )

                if s3_uri:
                    mappings[mapping_name][collection_value] = {prop.property_name: s3_uri}
                else:
                    LOG.warning(
                        "Could not find S3 URI for %s in expanded resource %s",
                        prop.property_name,
                        expanded_resource_key,
                    )

        property_to_mapping[_prop_identity(prop)] = mapping_name

    return mappings, property_to_mapping


def _validate_mapping_key_compatibility(prop: DynamicArtifactProperty) -> None:
    """
    Validate that collection values are valid CloudFormation Mapping keys.

    Raises InvalidMappingKeyError if any collection value contains invalid characters.
    """
    from samcli.commands.package.exceptions import InvalidMappingKeyError

    invalid_values = []
    for value in prop.collection:
        if not _VALID_MAPPING_KEY_PATTERN.match(value):
            invalid_values.append(value)

    if invalid_values:
        raise InvalidMappingKeyError(
            foreach_key=prop.foreach_key,
            loop_name=prop.loop_name,
            invalid_values=invalid_values,
        )


def _find_artifact_uri_for_resource(
    exported_resources: Dict[str, Any],
    resource_key: str,
    resource_type: str,
    property_name: str,
) -> Optional[str]:
    """
    Find the artifact URI for a specific resource and property from the exported resources.

    Handles all artifact property export formats (string URIs, {S3Bucket, S3Key},
    {Bucket, Key}, {ImageUri}).
    """
    resource = exported_resources.get(resource_key)
    if not isinstance(resource, dict):
        return None

    if resource.get("Type") != resource_type:
        return None

    properties = resource.get("Properties", {})
    if not isinstance(properties, dict):
        return None

    artifact_uri = properties.get(property_name)

    if isinstance(artifact_uri, str):
        return artifact_uri

    if isinstance(artifact_uri, dict):
        if "S3Bucket" in artifact_uri and "S3Key" in artifact_uri:
            return f"s3://{artifact_uri['S3Bucket']}/{artifact_uri['S3Key']}"

        if "Bucket" in artifact_uri and "Key" in artifact_uri:
            return f"s3://{artifact_uri['Bucket']}/{artifact_uri['Key']}"

        if "ImageUri" in artifact_uri:
            image_uri = artifact_uri["ImageUri"]
            return str(image_uri) if image_uri is not None else None

    return None


def _apply_artifact_mappings_to_template(
    template: Dict[str, Any],
    mappings: Dict[str, Dict[str, Dict[str, str]]],
    dynamic_properties: List[DynamicArtifactProperty],
    property_to_mapping: Optional[Dict[Tuple, str]] = None,
) -> Dict[str, Any]:
    """
    Apply generated Mappings to the template and replace dynamic artifact properties
    with Fn::FindInMap references.
    """
    if mappings:
        if "Mappings" not in template:
            template["Mappings"] = {}
        template["Mappings"].update(mappings)

    resources = template.get("Resources", {})
    for prop in dynamic_properties:
        mapping_name = None
        if property_to_mapping:
            mapping_name = property_to_mapping.get(_prop_identity(prop))
        _replace_dynamic_artifact_with_findmap(resources, prop, mapping_name=mapping_name)

    return template


def _replace_dynamic_artifact_with_findmap(
    resources: Dict[str, Any],
    prop: DynamicArtifactProperty,
    mapping_name: Optional[str] = None,
) -> bool:
    """
    Replace a dynamic artifact property value with Fn::FindInMap reference.
    """
    if mapping_name is None:
        mapping_name = f"SAM{prop.property_name}{_nesting_path(prop)}"

    current_scope = resources
    if prop.outer_loops:
        for outer_key, _, _ in prop.outer_loops:
            foreach_value = current_scope.get(outer_key)
            if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
                LOG.warning("Could not traverse outer Fn::ForEach block %s", outer_key)
                return False
            body = foreach_value[2]
            if not isinstance(body, dict):
                LOG.warning("Outer Fn::ForEach body is not a dict for %s", outer_key)
                return False
            current_scope = body

    foreach_value = current_scope.get(prop.foreach_key)
    if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
        LOG.warning("Could not find valid Fn::ForEach block for %s", prop.foreach_key)
        return False

    body = foreach_value[2]
    if not isinstance(body, dict):
        LOG.warning("Fn::ForEach body is not a dict for %s", prop.foreach_key)
        return False

    resource_def = body.get(prop.resource_key)
    if not isinstance(resource_def, dict):
        LOG.warning("Could not find resource definition for %s in %s", prop.resource_key, prop.foreach_key)
        return False

    properties = resource_def.get("Properties", {})
    if not isinstance(properties, dict):
        LOG.warning("Properties is not a dict for resource %s in %s", prop.resource_key, prop.foreach_key)
        return False

    uses_compound_keys = False
    referenced_outer_vars: List[str] = []
    if prop.outer_loops:
        for _, outer_var, _ in prop.outer_loops:
            if contains_loop_variable(prop.property_value, outer_var):
                uses_compound_keys = True
                referenced_outer_vars.append(outer_var)

    if uses_compound_keys and referenced_outer_vars:
        ref_parts = [{"Ref": ovar} for ovar in referenced_outer_vars]
        ref_parts.append({"Ref": prop.loop_variable})
        lookup_key: Any = {"Fn::Join": ["-", ref_parts]}
    else:
        lookup_key = {"Ref": prop.loop_variable}

    properties[prop.property_name] = {
        "Fn::FindInMap": [
            mapping_name,
            lookup_key,
            prop.property_name,
        ]
    }

    LOG.debug(
        "Replaced %s in %s/%s with Fn::FindInMap reference to %s",
        prop.property_name,
        prop.foreach_key,
        prop.resource_key,
        mapping_name,
    )

    return True


def warn_parameter_based_collections(dynamic_properties: List[DynamicArtifactProperty]) -> None:
    """
    Emit warnings for dynamic artifact properties that use parameter-based collections.
    """
    warned_loops: set = set()

    for prop in dynamic_properties:
        if prop.collection_is_parameter_ref and prop.foreach_key not in warned_loops:
            warned_loops.add(prop.foreach_key)

            loop_name = prop.loop_name
            param_name = prop.collection_parameter_name or "parameter"

            warning_msg = (
                f"Warning: Fn::ForEach '{loop_name}' uses dynamic {prop.property_name} "
                f"with a parameter-based collection (!Ref {param_name}). "
                f"Collection values are fixed at package time. "
                f"If you change the parameter value at deploy time, you must re-package first."
            )

            LOG.debug(warning_msg)
            click.secho(warning_msg, fg="yellow")
