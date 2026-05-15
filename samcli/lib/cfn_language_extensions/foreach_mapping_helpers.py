"""
Pure helpers that compute the three identifiers SAM CLI emits when rewriting
dynamic ``Fn::ForEach`` artifact properties: the ``Mappings`` table name, the
second argument of ``Fn::FindInMap`` (the lookup key), and the inner-Mapping
table key for nested ``Fn::ForEach`` value combinations.

These were previously inline in two near-duplicate places —
``samcli/commands/build/build_context.py::_update_foreach_artifact_paths`` /
``_collect_nested_mapping_entry`` (build-time) and
``samcli/lib/package/language_extensions_packaging.py::_compute_mapping_name`` /
``_replace_dynamic_artifact_with_findmap`` /
``_generate_artifact_mappings`` (package-time). Each round of bot review on
PR #9009 caught a divergence between those copies (collision keying on the
dotted path vs. the leaf, missing prefixes, FindInMap third-arg spelling).

Co-locating the three computations in one module makes drift between the two
pipelines structurally impossible: there is one source of truth for what
SAM-emitted Mapping identifiers look like.
"""

from typing import Any, List

from samcli.lib.cfn_language_extensions.sam_integration import sanitize_resource_key_for_mapping


def compute_mapping_name(
    leaf: str,
    nesting_path: str,
    *,
    has_collision: bool,
    resource_template_key: str,
) -> str:
    """Build the ``SAM<leaf><nesting_path>[<resource-suffix>]`` Mapping name.

    The base name is ``SAM<leaf><nesting_path>``. When ``has_collision`` is
    True (multiple resources in the same ``Fn::ForEach`` body share the same
    ``(nesting_path, leaf)`` pair), a sanitized suffix derived from the
    resource logical-ID template is appended to keep Mapping names unique.

    ``leaf`` must be the leaf segment of the property path
    (e.g. ``"ScriptLocation"``, not ``"Command.ScriptLocation"``) — Mapping
    names must be alphanumeric.
    """
    base = f"SAM{leaf}{nesting_path}"
    if not has_collision:
        return base
    return f"{base}{sanitize_resource_key_for_mapping(resource_template_key)}"


def compute_lookup_key(loop_variable: str, referenced_outer_vars: List[str]) -> Any:
    """Build the second argument of ``Fn::FindInMap``.

    Returns ``{"Ref": loop_variable}`` when no outer ``Fn::ForEach`` loops are
    referenced, or ``{"Fn::Join": ["-", [{"Ref": ovar}, ..., {"Ref": loop_variable}]]}``
    otherwise. Order matches the order of ``referenced_outer_vars`` in the
    list, with the inner ``loop_variable`` appended at the end. This mirrors
    the order used to build the corresponding compound Mapping key in
    :func:`compute_compound_mapping_key`.
    """
    if not referenced_outer_vars:
        return {"Ref": loop_variable}

    ref_parts: List[Any] = [{"Ref": ovar} for ovar in referenced_outer_vars]
    ref_parts.append({"Ref": loop_variable})
    return {"Fn::Join": ["-", ref_parts]}


def compute_compound_mapping_key(outer_values: List[str], inner_value: str) -> str:
    """Build the dash-joined Mapping table key for a nested-``Fn::ForEach``
    value combination.

    Example: ``compute_compound_mapping_key(["Dev", "Api"], "Users")`` →
    ``"Dev-Api-Users"``. Outer values come first, in the same order as the
    ``referenced_outer_vars`` passed to :func:`compute_lookup_key`, with the
    inner-loop value appended at the end.
    """
    return "-".join(list(outer_values) + [inner_value])


__all__ = [
    "compute_compound_mapping_key",
    "compute_lookup_key",
    "compute_mapping_name",
]
