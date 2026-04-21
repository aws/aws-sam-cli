"""
Utility functions for CloudFormation Language Extensions.

This module provides shared helpers used across the SAM CLI codebase
for working with templates that may contain Fn::ForEach blocks.
"""

from types import MappingProxyType
from typing import Any, Dict, Iterator, Tuple

FOREACH_PREFIX = "Fn::ForEach::"

# Fn::ForEach structure requires exactly 3 elements: [loop_variable, collection, output_template]
FOREACH_REQUIRED_ELEMENTS = 3

# Set of AWS pseudo-parameter names
PSEUDO_PARAMETERS = {
    "AWS::AccountId",
    "AWS::NotificationARNs",
    "AWS::NoValue",
    "AWS::Partition",
    "AWS::Region",
    "AWS::StackId",
    "AWS::StackName",
    "AWS::URLSuffix",
}


def derive_partition(region: str) -> str:
    """Derive the AWS partition from the region."""
    if region.startswith("cn-"):
        return "aws-cn"
    elif region.startswith("us-gov-"):
        return "aws-us-gov"
    else:
        return "aws"


def derive_url_suffix(region: str) -> str:
    """Derive the AWS URL suffix from the region."""
    if region.startswith("cn-"):
        return "amazonaws.com.cn"
    else:
        return "amazonaws.com"


def is_foreach_key(key: str) -> bool:
    """Check if a resource key is a Fn::ForEach block."""
    return isinstance(key, str) and key.startswith(FOREACH_PREFIX)


# Mapping-name prefixes that SAM CLI emits for dynamic Fn::ForEach handling:
#   - SAM + <packageable artifact property> + <nesting path> + [resource suffix]
#     (see language_extensions_packaging._compute_mapping_name)
#   - SAMLayers + <nesting path>  (see build_context — auto dependency layer refs)
# Customer-authored mappings should never start with one of these exact
# PascalCase prefixes, so exact-prefix matching avoids the false positives
# a regex like r"^SAM[A-Z]..." would hit on names like SAMPLE / SAMSUNG.
_SAM_GENERATED_MAPPING_PREFIXES: Tuple[str, ...] = (
    "SAMCodeUri",
    "SAMImageUri",
    "SAMContentUri",
    "SAMDefinitionUri",
    "SAMSchemaUri",
    "SAMBodyS3Location",
    "SAMDefinitionS3Location",
    "SAMTemplateURL",
    "SAMCode",
    "SAMContent",
    "SAMLayers",
)


def is_sam_generated_mapping(mapping_name: str) -> bool:
    """Return True if *mapping_name* matches the naming scheme SAM CLI uses
    for Mappings emitted during sam build / sam package for dynamic
    Fn::ForEach artifact properties.

    Customer-authored mappings that happen to start with "SAM" as a substring
    (e.g. SAMPLE, SAMSUNG) will NOT match because the next character after the
    prefix must begin a new PascalCase segment (upper-case letter).
    """
    if not mapping_name:
        return False
    for prefix in _SAM_GENERATED_MAPPING_PREFIXES:
        if mapping_name == prefix:
            # Bare prefix with no nesting path isn't a real SAM-generated name.
            return False
        if mapping_name.startswith(prefix):
            nxt = mapping_name[len(prefix)]
            if "A" <= nxt <= "Z":
                return True
    return False


def iter_regular_resources(template_dict: Dict) -> Iterator[Tuple[str, Dict]]:
    """
    Yield (logical_id, resource_dict) pairs from a template's Resources section,
    skipping Fn::ForEach blocks and non-dict entries.

    Parameters
    ----------
    template_dict : dict
        A CloudFormation template dictionary (must have a "Resources" key).

    Yields
    ------
    Tuple[str, dict]
        (logical_id, resource_dict) for each regular (non-ForEach) resource.
    """
    for key, value in template_dict.get("Resources", {}).items():
        if not is_foreach_key(key) and isinstance(value, dict):
            yield key, value


def deep_freeze(obj: Any) -> Any:
    """Recursively make a template structure immutable.

    - dicts become ``MappingProxyType`` (read-only view)
    - lists become ``tuple`` (immutable sequence)
    - primitives (str, int, float, bool, None) pass through unchanged

    Any caller that tries to mutate a frozen template gets an immediate
    ``TypeError`` instead of silently corrupting shared state.  Callers
    that need a mutable copy should use ``deep_thaw()`` (not
    ``copy.deepcopy`` which cannot pickle ``MappingProxyType``).

    Cost is O(n) — same as one ``copy.deepcopy`` — but you pay it once
    at creation time and then never need defensive copies again.
    """
    if isinstance(obj, MappingProxyType):
        return obj  # already frozen
    if isinstance(obj, dict):
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(deep_freeze(item) for item in obj)
    return obj


def deep_thaw(obj: Any) -> Any:
    """Recursively convert a frozen template back to mutable dicts and lists.

    Inverse of ``deep_freeze``.  Use this instead of ``copy.deepcopy``
    on frozen templates (``MappingProxyType`` is not picklable).
    """
    if isinstance(obj, MappingProxyType):
        return {k: deep_thaw(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: deep_thaw(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_thaw(item) for item in obj]
    return obj
