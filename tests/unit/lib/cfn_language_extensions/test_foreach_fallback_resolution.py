"""
Tests for ForEachProcessor resolution paths when _intrinsic_resolver is None.

When no intrinsic resolver is provided, values are returned as-is
without any fallback resolution.
"""

import pytest

from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor
from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext, ParsedTemplate


@pytest.fixture
def processor() -> ForEachProcessor:
    return ForEachProcessor(intrinsic_resolver=None)


class TestResolveIntrinsicNoResolver:
    """Tests for _resolve_intrinsic when no intrinsic_resolver is set."""

    def test_ref_returned_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"MyParam": "resolved-value"},
        )
        result = processor._resolve_intrinsic({"Ref": "MyParam"}, context)
        assert result == {"Ref": "MyParam"}

    def test_non_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        assert processor._resolve_intrinsic("plain string", context) == "plain string"
        assert processor._resolve_intrinsic(42, context) == 42


class TestResolveCollectionNoResolver:
    """Tests for _resolve_collection when no intrinsic_resolver is set."""

    def test_ref_returned_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Names": "A,B,C"},
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == {"Ref": "Names"}

    def test_static_list_returned_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        result = processor._resolve_collection(["A", "B"], context)
        assert result == ["A", "B"]
