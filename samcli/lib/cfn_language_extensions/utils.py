"""
Utility functions for CloudFormation Language Extensions.

This module provides shared helpers used across the SAM CLI codebase
for working with templates that may contain Fn::ForEach blocks.
"""

from typing import TYPE_CHECKING, Any, Dict, Iterator, Tuple

if TYPE_CHECKING:
    from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext

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
    elif region.startswith("eusc-"):
        return "aws-eusc"
    else:
        return "aws"


def derive_url_suffix(region: str) -> str:
    """Derive the AWS URL suffix from the region."""
    if region.startswith("cn-"):
        return "amazonaws.com.cn"
    elif region.startswith("eusc-"):
        return "amazonaws.eu"
    else:
        return "amazonaws.com"


def is_foreach_key(key: str) -> bool:
    """Check if a resource key is a Fn::ForEach block."""
    return isinstance(key, str) and key.startswith(FOREACH_PREFIX)


# Keys that identify CloudFormation intrinsic functions (besides the Fn:: prefix).
_INTRINSIC_SINGLE_KEYS = {"Ref", "Condition"}


def is_intrinsic_key(key: str) -> bool:
    """Return True if *key* is a CloudFormation intrinsic function name.

    Intrinsic function keys either start with ``Fn::`` or are one of the
    special single-word keys (``Ref``, ``Condition``).
    """
    return key.startswith("Fn::") or key in _INTRINSIC_SINGLE_KEYS


def is_unresolved_param_or_pseudo_ref(value: Any, context: "TemplateProcessingContext") -> bool:
    """Return True if *value* is ``{"Ref": <name>}`` where ``<name>`` is a declared
    template parameter or a pseudo-parameter — i.e. an unresolved reference that
    CloudFormation will resolve at deploy time.

    Used by template-time intrinsic resolvers (Fn::FindInMap, Fn::Join, Fn::Select,
    Fn::Base64) to decide, in PARTIAL resolution mode, whether to preserve the
    enclosing call instead of raising. Resource refs and other intrinsics return
    False so they continue to raise — matching Kotlin compatibility for
    template-time intrinsics that genuinely cannot accept deploy-time inputs.
    """
    if not isinstance(value, dict) or len(value) != 1:
        return False
    if "Ref" not in value:
        return False
    ref_target = value["Ref"]
    if not isinstance(ref_target, str):
        return False
    if ref_target in PSEUDO_PARAMETERS:
        return True
    if context.parsed_template is not None and ref_target in context.parsed_template.parameters:
        return True
    return False


# Mapping-name prefixes that SAM CLI emits for dynamic Fn::ForEach handling:
#   - SAM + <leaf of packageable artifact property> + <nesting path> + [resource suffix]
#     (see language_extensions_packaging._compute_mapping_name)
#   - SAMLayers + <nesting path>  (see build_context — auto dependency layer refs)
# Derived from PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES so the set automatically
# tracks the canonical packageable-resource list. Customer-authored mappings
# should never start with one of these exact PascalCase prefixes; exact-prefix
# matching avoids the false positives a regex like r"^SAM[A-Z]..." would hit on
# names like SAMPLE / SAMSUNG.
def _build_sam_generated_mapping_prefixes() -> Tuple[str, ...]:
    from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES

    seen: set = set()
    prefixes: list = []
    for props in PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.values():
        for prop in props:
            leaf = prop.rsplit(".", 1)[-1]
            prefix = f"SAM{leaf}"
            if prefix not in seen:
                seen.add(prefix)
                prefixes.append(prefix)
    # SAMLayers is emitted by sam build for auto dependency layer references and
    # has no corresponding artifact property; add it explicitly.
    if "SAMLayers" not in seen:
        prefixes.append("SAMLayers")
    return tuple(prefixes)


_SAM_GENERATED_MAPPING_PREFIXES: Tuple[str, ...] = _build_sam_generated_mapping_prefixes()


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
            # Accept any alphanumeric character after the prefix.
            # Loop names can be PascalCase, lowercase, or start with digits.
            if nxt.isalnum():
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
