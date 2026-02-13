"""
Tests for ForEachProcessor fallback resolution paths.

Covers _resolve_intrinsic, _resolve_collection_item, and _resolve_collection
when _intrinsic_resolver is None (fallback manual resolution).
"""

import pytest

from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor
from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext, ParsedTemplate


@pytest.fixture
def processor() -> ForEachProcessor:
    return ForEachProcessor(intrinsic_resolver=None)


class TestResolveIntrinsicFallback:
    """Tests for _resolve_intrinsic fallback paths (no intrinsic_resolver)."""

    def test_ref_resolved_from_parameter_values(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"MyParam": "resolved-value"},
        )
        result = processor._resolve_intrinsic({"Ref": "MyParam"}, context)
        assert result == "resolved-value"

    def test_ref_resolved_from_parsed_template_parameters(self, processor):

        parsed = ParsedTemplate(parameters={"MyParam": {"Default": "default-val"}})
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=parsed,
        )
        result = processor._resolve_intrinsic({"Ref": "MyParam"}, context)
        assert result == "default-val"

    def test_ref_unresolvable_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Ref": "Unknown"}
        result = processor._resolve_intrinsic(value, context)
        assert result == value

    def test_non_ref_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Fn::Sub": "something"}
        result = processor._resolve_intrinsic(value, context)
        assert result == value

    def test_non_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        assert processor._resolve_intrinsic("plain string", context) == "plain string"
        assert processor._resolve_intrinsic(42, context) == 42

    def test_multi_key_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Ref": "X", "Extra": "Y"}
        result = processor._resolve_intrinsic(value, context)
        assert result == value

    def test_non_string_ref_target_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Ref": 123}
        result = processor._resolve_intrinsic(value, context)
        assert result == value


class TestResolveCollectionItemFallback:
    """Tests for _resolve_collection_item fallback paths."""

    def test_list_item_returned_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        result = processor._resolve_collection_item([1, "a"], context)
        assert result == [1, "a"]

    def test_ref_resolved_from_parameter_values_string(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Names": "Alpha,Beta,Gamma"},
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["Alpha", "Beta", "Gamma"]

    def test_ref_resolved_from_parameter_values_list(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Names": ["A", "B"]},
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["A", "B"]

    def test_ref_resolved_from_parsed_template_comma_delimited(self, processor):

        parsed = ParsedTemplate(parameters={"Names": {"Type": "CommaDelimitedList", "Default": "X,Y,Z"}})
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=parsed,
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["X", "Y", "Z"]

    def test_ref_resolved_from_parsed_template_non_comma_delimited(self, processor):

        parsed = ParsedTemplate(parameters={"Names": {"Type": "String", "Default": ["A", "B"]}})
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=parsed,
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["A", "B"]

    def test_ref_resolved_from_fragment_parameters(self, processor):
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "P,Q"}},
                "Resources": {},
            },
            parameter_values={},
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["P", "Q"]

    def test_ref_resolved_from_fragment_parameters_non_comma(self, processor):
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Names": {"Type": "String", "Default": ["M", "N"]}},
                "Resources": {},
            },
            parameter_values={},
        )
        result = processor._resolve_collection_item({"Ref": "Names"}, context)
        assert result == ["M", "N"]

    def test_unresolvable_ref_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Ref": "Unknown"}
        result = processor._resolve_collection_item(value, context)
        assert result == value

    def test_non_ref_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Fn::Split": [",", "a,b"]}
        result = processor._resolve_collection_item(value, context)
        assert result == value


class TestResolveCollectionFallback:
    """Tests for _resolve_collection fallback paths."""

    def test_ref_resolved_from_parameter_values_string(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Names": "A,B,C"},
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["A", "B", "C"]

    def test_ref_resolved_from_parameter_values_list(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Names": ["X", "Y"]},
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["X", "Y"]

    def test_ref_resolved_from_parsed_template_comma_delimited(self, processor):

        parsed = ParsedTemplate(parameters={"Names": {"Type": "CommaDelimitedList", "Default": "D,E,F"}})
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=parsed,
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["D", "E", "F"]

    def test_ref_resolved_from_parsed_template_non_comma(self, processor):

        parsed = ParsedTemplate(parameters={"Names": {"Type": "String", "Default": ["G", "H"]}})
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=parsed,
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["G", "H"]

    def test_ref_resolved_from_fragment_parameters(self, processor):
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "R,S"}},
                "Resources": {},
            },
            parameter_values={},
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["R", "S"]

    def test_ref_resolved_from_fragment_parameters_non_comma(self, processor):
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Names": {"Type": "String", "Default": ["T", "U"]}},
                "Resources": {},
            },
            parameter_values={},
        )
        result = processor._resolve_collection({"Ref": "Names"}, context)
        assert result == ["T", "U"]

    def test_unresolvable_ref_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Ref": "Unknown"}
        result = processor._resolve_collection(value, context)
        assert result == value

    def test_static_list_returned_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        result = processor._resolve_collection(["A", "B"], context)
        assert result == ["A", "B"]

    def test_non_ref_dict_returns_as_is(self, processor):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        value = {"Fn::Split": [",", "a,b"]}
        result = processor._resolve_collection(value, context)
        assert result == value
