"""Deterministic YAML rendering for golden-template comparison.

The harness and update_goldens.py both call normalize() so the bytes
written to disk match the bytes the test compares. Determinism rules:

- Resources / Mappings keys sorted alphabetically.
- Metadata.SamTransformMetrics dropped (varies by run).
- Empty Metadata block dropped.
- yaml.safe_dump with sort_keys=True, default_flow_style=False.
- Single trailing newline.

OrderedDict handling: ``samcli.yamlhelper.yaml_parse`` registers a
``DEFAULT_MAPPING_TAG`` constructor that emits ``OrderedDict`` instead of
``dict`` on the global ``yaml.SafeLoader``. Once any caller has imported
yamlhelper, every subsequent ``yaml.safe_load`` returns OrderedDict. The
default ``yaml.safe_dump`` representer rejects OrderedDict, so we
recursively coerce the input to plain ``dict`` before serializing.
"""

from __future__ import annotations

from typing import Any, Dict

import yaml

_VOLATILE_METADATA_KEYS = frozenset({"SamTransformMetrics"})


def _to_plain(value: Any) -> Any:
    """Recursively coerce OrderedDict (and anything dict-like) to plain dict.

    Necessary because ``samcli.yamlhelper.yaml_parse`` mutates the global
    ``yaml.SafeLoader`` to emit OrderedDict, and ``yaml.safe_dump`` does
    not know how to represent OrderedDict.
    """
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


def _filter_metadata(template: Dict[str, Any]) -> None:
    metadata = template.get("Metadata")
    if not isinstance(metadata, dict):
        return
    for key in _VOLATILE_METADATA_KEYS:
        metadata.pop(key, None)
    if not metadata:
        template.pop("Metadata", None)


def normalize(template: Dict[str, Any]) -> str:
    """Render template to deterministic YAML string."""
    # Coerce to plain dict so yaml.safe_dump can represent it; also gives
    # us a deep copy so we don't surprise the caller.
    template = _to_plain(template)
    _filter_metadata(template)

    rendered = yaml.safe_dump(
        template,
        sort_keys=True,
        default_flow_style=False,
        width=10**9,  # don't wrap long strings
        allow_unicode=True,
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered
