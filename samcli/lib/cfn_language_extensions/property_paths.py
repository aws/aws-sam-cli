"""
Helpers for addressing CloudFormation resource artifact properties by jmespath.

CloudFormation resource artifact properties are most-naturally addressed as
jmespath paths because some live at flat keys (``CodeUri``) and others at
nested locations (``Command.ScriptLocation`` on ``AWS::Glue::Job``,
``Code.ImageUri`` on a Lambda image function). The canonical packageable-
property registry (`PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES`) records each
in its addressing form, so consumers across SAM CLI must use jmespath get/set
to read and write them without clobbering siblings.

This module provides those small, jmespath-aware helpers plus
``copy_artifact_properties``, the single helper that copies packaged
artifact values from an exported resource onto the corresponding original
resource for a given resource type. It is shared by the build-time and
package-time pipelines so the two cannot drift in their treatment of
property addressing.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import jmespath
from botocore.utils import set_value_from_jmespath


def get_prop_value(props: Dict[str, Any], path: str) -> Optional[Any]:
    """Read a property by jmespath path. Supports flat keys ("CodeUri") and
    dotted paths ("Command.ScriptLocation"). Returns None if missing.
    """
    return jmespath.search(path, props)


def set_prop_value(props: Dict[str, Any], path: str, value: Any) -> None:
    """Write a property by jmespath path. Creates intermediate dicts as
    needed. Supports flat keys and dotted paths.
    """
    set_value_from_jmespath(props, path, value)


def leaf_prop_name(path: str) -> str:
    """Return the last segment of a jmespath property path.

    CloudFormation Mapping names must be alphanumeric, and the third argument
    of ``Fn::FindInMap`` and the keys of Mapping value-dicts must match each
    other as plain strings. Dotted property paths (e.g. ``Command.ScriptLocation``)
    address the property *on* a resource; the *identifier* used in Mapping
    names and FindInMap lookups must use only the leaf segment so the
    generated CloudFormation is well-formed.
    """
    return path.rsplit(".", 1)[-1]


def resolve_property_paths(paths: List[str], properties: Dict[str, Any]) -> List[str]:
    """Filter ``paths`` so a parent path is dropped when a more specific
    child path is present in ``properties``.

    Some resource types declare multiple alternative artifact paths in
    ``PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES``. For example,
    ``AWS::Lambda::Function`` lists ``Code`` (used for ZIP packages) and
    ``Code.ImageUri`` (used for image packages). A given user template uses
    only one of these shapes, but ``Code`` is a prefix of ``Code.ImageUri``,
    so a naive iteration would address both paths and treat the same nested
    value twice. Returning only the most specific resolved path picks the
    correct interpretation for the user's actual property shape.
    """
    # Sort longest-first so child paths win over their parents.
    sorted_paths = sorted(paths, key=lambda p: -p.count("."))
    consumed_prefixes: Set[str] = set()
    selected: List[str] = []
    for path in sorted_paths:
        if get_prop_value(properties, path) is None:
            continue
        # If a more specific path under this prefix has already been selected, skip.
        if any(other.startswith(path + ".") for other in consumed_prefixes):
            continue
        selected.append(path)
        consumed_prefixes.add(path)
    # Preserve original ordering for callers that care.
    order = {p: i for i, p in enumerate(paths)}
    selected.sort(key=lambda p: order.get(p, 0))
    return selected


def copy_artifact_properties(
    original_props: Dict[str, Any],
    exported_props: Dict[str, Any],
    resource_type: str,
    *,
    foreach_key: Optional[str] = None,
    dynamic_prop_keys: Optional[Set[Tuple[str, str]]] = None,
) -> bool:
    """Copy packaged artifact property values from ``exported_props`` onto
    ``original_props`` for the given resource type.

    Returns True if any property was copied. When called from the
    language-extensions merge path, pass ``foreach_key`` and
    ``dynamic_prop_keys`` so dynamic-loop properties (handled separately by
    Mapping/FindInMap rewrites) are skipped. Build-time and non-ForEach
    callers omit both kwargs.

    Both input dicts are addressed with jmespath, so dotted property paths
    like ``Command.ScriptLocation`` or ``Code.ImageUri`` round-trip correctly
    without creating literal flat keys.
    """
    # Lazy import to avoid forcing the canonical-list module on every consumer
    # of this small helper module at import time.
    from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES

    paths = PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(resource_type)
    if not paths:
        return False

    copied = False
    for path in paths:
        exported_value = get_prop_value(exported_props, path)
        if exported_value is None:
            continue
        if dynamic_prop_keys and foreach_key and (foreach_key, path) in dynamic_prop_keys:
            continue
        set_prop_value(original_props, path, exported_value)
        copied = True

    return copied


__all__ = [
    "copy_artifact_properties",
    "get_prop_value",
    "leaf_prop_name",
    "resolve_property_paths",
    "set_prop_value",
]
