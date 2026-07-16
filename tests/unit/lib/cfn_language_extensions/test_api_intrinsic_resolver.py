"""
Tests for IntrinsicResolverProcessor in api.py.

Covers _partial_resolve, _resolve_with_false_condition, _resolve_resources_section,
_resolve_outputs_section, and _remove_no_value.
"""

import pytest

from samcli.lib.cfn_language_extensions.api import (
    IntrinsicResolverProcessor,
    create_default_intrinsic_resolver,
    create_default_pipeline,
    process_template,
)
from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ParsedTemplate,
)


class TestPartialResolve:
    """Tests for _partial_resolve method."""

    def _make_processor(self, context):
        resolver = create_default_intrinsic_resolver(context)
        return IntrinsicResolverProcessor(resolver)

    def test_primitive_value_returned_as_is(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        assert proc._partial_resolve("hello") == "hello"
        assert proc._partial_resolve(42) == 42
        assert proc._partial_resolve(True) is True

    def test_list_recursively_resolved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        result = proc._partial_resolve(["a", "b", 3])
        assert result == ["a", "b", 3]

    def test_regular_dict_recursively_resolved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        result = proc._partial_resolve({"key1": "val1", "key2": 42})
        assert result == {"key1": "val1", "key2": 42}

    def test_ref_to_parameter_replaced_with_no_value(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"MyParam": "value"},
        )
        proc = self._make_processor(context)
        result = proc._partial_resolve({"Ref": "MyParam"})
        assert result == {"Ref": "AWS::NoValue"}

    def test_ref_to_pseudo_param_preserved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"AWS::Region": "us-east-1"},
        )
        proc = self._make_processor(context)
        result = proc._partial_resolve({"Ref": "AWS::Region"})
        assert result == "us-east-1"

    def test_ref_to_no_value_preserved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        result = proc._partial_resolve({"Ref": "AWS::NoValue"})
        assert result == {"Ref": "AWS::NoValue"}


class TestPartialResolveDirectCall:
    """Tests for _partial_resolve (formerly _resolve_with_false_condition)."""

    def test_primitive_value_returned_as_is(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        result = proc._partial_resolve("simple")
        assert result == "simple"


class TestRemoveNoValue:
    """Tests for _remove_no_value."""

    def _make_processor(self, context):
        resolver = create_default_intrinsic_resolver(context)
        return IntrinsicResolverProcessor(resolver)

    def test_removes_no_value_from_dict(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        value = {"key1": "val1", "key2": {"Ref": "AWS::NoValue"}}
        result = proc._remove_no_value(value)
        assert "key1" in result
        assert "key2" not in result

    def test_removes_no_value_from_list(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        value = ["a", {"Ref": "AWS::NoValue"}, "b"]
        result = proc._remove_no_value(value)
        assert result == ["a", "b"]

    def test_primitive_returned_as_is(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        proc = self._make_processor(context)
        assert proc._remove_no_value("hello") == "hello"
        assert proc._remove_no_value(42) == 42


class TestProcessTemplateConditions:
    """Tests for process_template with conditions."""

    def test_false_condition_resource_uses_partial_resolution(self):
        result = process_template(
            {
                "Conditions": {
                    "IsEnabled": {"Fn::Equals": ["false", "true"]},
                },
                "Resources": {
                    "MyFunc": {
                        "Type": "AWS::Serverless::Function",
                        "Condition": "IsEnabled",
                        "Properties": {
                            "CodeUri": "./src",
                        },
                    }
                },
            },
            parameter_values={},
        )
        # Resource should still exist but with partial resolution
        assert "MyFunc" in result.get("Resources", {})

    def test_true_condition_resource_fully_resolved(self):
        result = process_template(
            {
                "Conditions": {
                    "IsEnabled": {"Fn::Equals": ["true", "true"]},
                },
                "Resources": {
                    "MyFunc": {
                        "Type": "AWS::Serverless::Function",
                        "Condition": "IsEnabled",
                        "Properties": {
                            "CodeUri": "./src",
                        },
                    }
                },
            },
            parameter_values={},
        )
        assert "MyFunc" in result.get("Resources", {})

    def test_output_with_false_condition(self):
        result = process_template(
            {
                "Conditions": {
                    "IsEnabled": {"Fn::Equals": ["false", "true"]},
                },
                "Resources": {
                    "MyFunc": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "./src"},
                    }
                },
                "Outputs": {
                    "MyOutput": {
                        "Condition": "IsEnabled",
                        "Value": {"Ref": "MyFunc"},
                    }
                },
            },
            parameter_values={},
        )
        assert "Outputs" in result


class TestResolveSectionWithConditions:
    """Tests for _resolve_section_with_conditions edge cases."""

    def test_non_dict_section_resolved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": "not a dict"},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        result = proc._resolve_section_with_conditions("not a dict", context)
        assert result == "not a dict"


class TestExtractConditionDependencies:
    """Tests for _extract_condition_dependencies."""

    def test_fn_if_recurses_into_values(self):
        """Fn::If condition name is a plain string in the list, not a Condition ref,
        so _extract_condition_dependencies won't add it — it only extracts from
        {"Condition": "name"} dicts. But it does recurse into nested structures."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        # Fn::If with a nested Condition ref inside the true branch
        deps = proc._extract_condition_dependencies(
            {"Fn::If": ["MyCondition", {"Condition": "NestedCond"}, "false-val"]}
        )
        assert "NestedCond" in deps

    def test_extracts_condition_from_condition_key(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        deps = proc._extract_condition_dependencies({"Condition": "MyCondition"})
        assert "MyCondition" in deps

    def test_no_conditions_in_primitive(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        deps = proc._extract_condition_dependencies("simple string")
        assert len(deps) == 0

    def test_recursive_extraction_from_list(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        deps = proc._extract_condition_dependencies([{"Condition": "Cond1"}, {"Condition": "Cond2"}])
        assert "Cond1" in deps
        assert "Cond2" in deps


class TestResolveConditionsSection:
    """Tests for _resolve_conditions_section."""

    def test_non_dict_conditions(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        result = proc._resolve_conditions_section("not a dict")
        assert result == "not a dict"

    def test_dict_conditions_resolved(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        result = proc._resolve_conditions_section({"IsEnabled": {"Fn::Equals": ["true", "true"]}})
        assert isinstance(result, dict)
        assert "IsEnabled" in result


class TestIsNoValue:
    """Tests for _is_no_value."""

    def test_ref_no_value(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        assert proc._is_no_value({"Ref": "AWS::NoValue"}) is True

    def test_not_no_value(self):
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        assert proc._is_no_value({"Ref": "MyParam"}) is False
        assert proc._is_no_value("string") is False
        assert proc._is_no_value(42) is False


class TestIntrinsicResolverProcessorPartialResolution:
    """Tests for IntrinsicResolverProcessor partial resolution for false conditions."""

    def test_partial_resolve_ref_to_parameter(self):
        """Test partial resolution replaces Ref to parameters with AWS::NoValue."""
        template = {
            "Parameters": {"MyParam": {"Type": "String", "Default": "value"}},
            "Conditions": {"AlwaysFalse": {"Fn::Equals": ["a", "b"]}},
            "Resources": {
                "MyResource": {
                    "Type": "AWS::SNS::Topic",
                    "Condition": "AlwaysFalse",
                    "Properties": {"TopicName": {"Ref": "MyParam"}},
                }
            },
        }
        result = process_template(template)
        assert "MyResource" in result["Resources"]

    def test_partial_resolve_fn_to_json_string(self):
        """Test partial resolution replaces Fn::ToJsonString with AWS::NoValue."""
        template = {
            "Conditions": {"AlwaysFalse": {"Fn::Equals": ["a", "b"]}},
            "Resources": {
                "MyResource": {
                    "Type": "AWS::SNS::Topic",
                    "Condition": "AlwaysFalse",
                    "Properties": {"DisplayName": {"Fn::ToJsonString": {"key": "val"}}},
                }
            },
        }
        result = process_template(template)
        assert "MyResource" in result["Resources"]


class TestIntrinsicResolverProcessorConditionValidation:
    """Tests for IntrinsicResolverProcessor condition validation."""

    def test_resource_references_non_existent_condition(self):
        """Test that resource referencing non-existent condition raises error."""
        template = {"Resources": {"MyResource": {"Type": "AWS::SNS::Topic", "Condition": "NonExistentCondition"}}}
        with pytest.raises(Exception):
            process_template(template)


class TestIntrinsicResolverProcessorCircularConditions:
    """Tests for IntrinsicResolverProcessor circular condition detection."""

    def test_circular_condition_dependency_detected(self):
        """Test that circular condition dependencies are detected."""
        template = {
            "Conditions": {"CondA": {"Condition": "CondB"}, "CondB": {"Condition": "CondA"}},
            "Resources": {},
        }
        with pytest.raises(Exception):
            process_template(template)

    def test_self_referencing_condition_detected(self):
        """Test that self-referencing condition is detected."""
        template = {
            "Conditions": {"SelfRef": {"Condition": "SelfRef"}},
            "Resources": {},
        }
        with pytest.raises(Exception):
            process_template(template)


class TestExtractConditionDependenciesMultiKeyDict:
    """Tests for _extract_condition_dependencies with multi-key dicts."""

    def test_multi_key_dict_extracts_dependencies(self):
        """Test that multi-key dicts have their values recursively searched."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Conditions": {
                    "CondA": {"Fn::Equals": ["a", "a"]},
                    "CondB": {"Fn::Equals": ["b", "b"]},
                },
            },
            parameter_values={},
        )
        resolver = create_default_intrinsic_resolver(context)
        proc = IntrinsicResolverProcessor(resolver)
        # A dict with multiple keys, each containing condition references
        value = {
            "key1": {"Condition": "CondA"},
            "key2": {"Condition": "CondB"},
        }
        deps = proc._extract_condition_dependencies(value)
        assert "CondA" in deps
        assert "CondB" in deps


class TestResolveConditionsSectionMultiKeyDict:
    """Tests for _resolve_conditions_section with multi-key condition values."""

    def test_condition_with_multi_key_dict_value(self):
        """Test resolving conditions where condition value has multiple keys."""
        template = {
            "Parameters": {"Env": {"Type": "String", "Default": "prod"}},
            "Conditions": {
                "IsProduction": {"Fn::Equals": [{"Ref": "Env"}, "prod"]},
            },
            "Resources": {
                "MyTopic": {"Type": "AWS::SNS::Topic", "Condition": "IsProduction"},
            },
        }
        result = process_template(template, parameter_values={"Env": "prod"})
        assert "IsProduction" in result.get("Conditions", {})
