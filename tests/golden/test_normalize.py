"""Unit tests for normalize() — deterministic YAML serialization."""

import pytest

from tests.golden.normalize import normalize


def test_normalize_produces_trailing_newline():
    out = normalize({"Resources": {}})
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_normalize_sorts_resources_keys():
    template = {
        "Resources": {
            "Zeta": {"Type": "AWS::Lambda::Function"},
            "Alpha": {"Type": "AWS::Lambda::Function"},
        },
    }
    out = normalize(template)
    assert out.index("Alpha") < out.index("Zeta")


def test_normalize_sorts_mappings_keys():
    template = {
        "Mappings": {
            "Z": {"k": {"v": "1"}},
            "A": {"k": {"v": "1"}},
        },
    }
    out = normalize(template)
    assert out.index("A:") < out.index("Z:")


def test_normalize_drops_sam_transform_metrics():
    template = {
        "Metadata": {
            "SamTransformMetrics": {"foo": "bar"},
            "Other": "keep",
        },
        "Resources": {},
    }
    out = normalize(template)
    assert "SamTransformMetrics" not in out
    assert "Other" in out


def test_normalize_drops_metadata_block_if_empty_after_filter():
    template = {
        "Metadata": {"SamTransformMetrics": {"foo": "bar"}},
        "Resources": {},
    }
    out = normalize(template)
    assert "Metadata" not in out


def test_normalize_is_idempotent():
    template = {"Resources": {"A": {"Type": "T"}}}
    once = normalize(template)
    import yaml
    twice = normalize(yaml.safe_load(once))
    assert once == twice


def test_normalize_preserves_intrinsic_function_dicts():
    template = {
        "Resources": {
            "F": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ZipFile": {"Fn::Sub": "x-${AWS::Region}"}},
                },
            }
        }
    }
    out = normalize(template)
    assert "Fn::Sub" in out
    assert "x-${AWS::Region}" in out


def test_normalize_uses_block_style_not_flow_style():
    template = {"Resources": {"A": {"Type": "T", "Properties": {"k": "v"}}}}
    out = normalize(template)
    # block style uses indentation, not braces
    assert "{" not in out
    assert "}" not in out
