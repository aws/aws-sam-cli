"""
Utility functions for CloudFormation Language Extensions.

This module provides shared helpers used across the SAM CLI codebase
for working with templates that may contain Fn::ForEach blocks.
"""

from typing import Dict, Iterator, Tuple

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
