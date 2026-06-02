"""Deterministic YAML rendering for golden-template comparison.

The harness and update_goldens.py both call normalize() so the bytes
written to disk match the bytes the test compares. Determinism rules:

- Resources / Mappings keys sorted alphabetically.
- Metadata.SamTransformMetrics dropped (varies by run).
- Empty Metadata block dropped.
- yaml.safe_dump with sort_keys=True, default_flow_style=False.
- Single trailing newline.
"""

from __future__ import annotations

from typing import Any, Dict

import yaml

_VOLATILE_METADATA_KEYS = frozenset({"SamTransformMetrics"})


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
    # Mutate a copy so we don't surprise the caller.
    template = {k: v for k, v in template.items()}
    if isinstance(template.get("Metadata"), dict):
        template["Metadata"] = dict(template["Metadata"])
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
