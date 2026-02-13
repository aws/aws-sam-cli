"""
Unit tests and property-based tests for the FnToJsonStringResolver class.

Tests cover:
- Basic Fn::ToJsonString functionality with literal dicts and lists
- Nested intrinsic function resolution
- Error handling for invalid inputs
- Integration with IntrinsicResolver orchestrator
- Property-based tests for universal correctness properties

Requirements:
    - 4.1: WHEN Fn::ToJsonString is applied to a dictionary, THEN THE Resolver SHALL
           return a JSON string representation of that dictionary
    - 4.2: WHEN Fn::ToJsonString is applied to a list, THEN THE Resolver SHALL
           return a JSON string representation of that list
    - 4.3: WHEN Fn::ToJsonString contains nested intrinsic functions that can be
           resolved, THEN THE Resolver SHALL resolve those intrinsics before
           converting to JSON
    - 4.4: WHEN Fn::ToJsonString contains intrinsic functions that cannot be resolved
           (e.g., Fn::GetAtt), THEN THE Resolver SHALL preserve those intrinsics
           in the JSON output
    - 4.5: WHEN Fn::ToJsonString is applied to an invalid layout, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
"""

import json
import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicFunctionResolver,
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.fn_to_json_string import FnToJsonStringResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


# =============================================================================
# Unit Tests for FnToJsonStringResolver
# =============================================================================


class TestFnToJsonStringResolverCanResolve:
    """Tests for FnToJsonStringResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnToJsonStringResolver:
        """Create a FnToJsonStringResolver for testing."""
        return FnToJsonStringResolver(context, None)

    def test_can_resolve_fn_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test that can_resolve returns True for Fn::ToJsonString."""
        value = {"Fn::ToJsonString": {"key": "value"}}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnToJsonStringResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnToJsonStringResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnToJsonStringResolver):
        """Test that FUNCTION_NAMES contains Fn::ToJsonString."""
        assert FnToJsonStringResolver.FUNCTION_NAMES == ["Fn::ToJsonString"]


class TestFnToJsonStringResolverBasicFunctionality:
    """Tests for basic Fn::ToJsonString functionality.

    Requirement 4.1: WHEN Fn::ToJsonString is applied to a dictionary, THEN THE
    Resolver SHALL return a JSON string representation of that dictionary

    Requirement 4.2: WHEN Fn::ToJsonString is applied to a list, THEN THE
    Resolver SHALL return a JSON string representation of that list
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnToJsonStringResolver:
        """Create a FnToJsonStringResolver for testing."""
        return FnToJsonStringResolver(context, None)

    def test_empty_dict_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with empty dict returns '{}'.

        Requirement 4.1: Return JSON string representation of dictionary
        """
        value: Dict[str, Any] = {"Fn::ToJsonString": {}}
        result = resolver.resolve(value)
        assert result == "{}"
        assert json.loads(result) == {}

    def test_simple_dict_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with simple dict.

        Requirement 4.1: Return JSON string representation of dictionary
        """
        value = {"Fn::ToJsonString": {"key": "value"}}
        result = resolver.resolve(value)
        assert json.loads(result) == {"key": "value"}

    def test_nested_dict_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with nested dict.

        Requirement 4.1: Return JSON string representation of dictionary
        """
        value = {"Fn::ToJsonString": {"outer": {"inner": "value"}}}
        result = resolver.resolve(value)
        assert json.loads(result) == {"outer": {"inner": "value"}}

    def test_empty_list_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with empty list returns '[]'.

        Requirement 4.2: Return JSON string representation of list
        """
        value: Dict[str, Any] = {"Fn::ToJsonString": []}
        result = resolver.resolve(value)
        assert result == "[]"
        assert json.loads(result) == []

    def test_simple_list_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with simple list.

        Requirement 4.2: Return JSON string representation of list
        """
        value = {"Fn::ToJsonString": [1, 2, 3]}
        result = resolver.resolve(value)
        assert json.loads(result) == [1, 2, 3]

    def test_mixed_type_list_to_json_string(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with mixed type list.

        Requirement 4.2: Return JSON string representation of list
        """
        value = {"Fn::ToJsonString": [1, "two", {"three": 3}, [4], None, True]}
        result = resolver.resolve(value)
        assert json.loads(result) == [1, "two", {"three": 3}, [4], None, True]

    def test_compact_json_output(self, resolver: FnToJsonStringResolver):
        """Test that Fn::ToJsonString produces compact JSON (no extra whitespace).

        Requirement 4.1, 4.2: Return JSON string representation
        """
        value = {"Fn::ToJsonString": {"key": "value"}}
        result = resolver.resolve(value)
        # Should use compact separators (no spaces after : or ,)
        assert result == '{"key":"value"}'


class TestFnToJsonStringResolverErrorHandling:
    """Tests for Fn::ToJsonString error handling.

    Requirement 4.5: WHEN Fn::ToJsonString is applied to an invalid layout, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnToJsonStringResolver:
        """Create a FnToJsonStringResolver for testing."""
        return FnToJsonStringResolver(context, None)

    def test_non_dict_or_list_string_raises_exception(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with string raises InvalidTemplateException.

        Requirement 4.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::ToJsonString": "not-a-dict-or-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::ToJsonString layout is incorrect" in str(exc_info.value)

    def test_non_dict_or_list_integer_raises_exception(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with integer raises InvalidTemplateException.

        Requirement 4.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::ToJsonString": 42}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::ToJsonString layout is incorrect" in str(exc_info.value)

    def test_non_dict_or_list_none_raises_exception(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with None raises InvalidTemplateException.

        Requirement 4.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::ToJsonString": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::ToJsonString layout is incorrect" in str(exc_info.value)

    def test_non_dict_or_list_boolean_raises_exception(self, resolver: FnToJsonStringResolver):
        """Test Fn::ToJsonString with boolean raises InvalidTemplateException.

        Requirement 4.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::ToJsonString": True}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::ToJsonString layout is incorrect" in str(exc_info.value)

    def test_error_message_exact_format(self, resolver: FnToJsonStringResolver):
        """Test that error message matches exact expected format.

        Requirement 4.5: Raise Invalid_Template_Exception indicating incorrect layout
        """
        value = {"Fn::ToJsonString": "not-valid"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        # Verify exact error message format
        assert str(exc_info.value) == "Fn::ToJsonString layout is incorrect"


class MockDictResolver(IntrinsicFunctionResolver):
    """A mock resolver that returns a dict for testing nested resolution."""

    FUNCTION_NAMES = ["Fn::MockDict"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return a dict based on the argument."""
        args = self.get_function_args(value)
        if isinstance(args, str):
            return {"resolved": args}
        return args


class MockListResolver(IntrinsicFunctionResolver):
    """A mock resolver that returns a list for testing nested resolution."""

    FUNCTION_NAMES = ["Fn::MockList"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return a list based on the argument."""
        args = self.get_function_args(value)
        if isinstance(args, int):
            return list(range(args))
        return args


class TestFnToJsonStringResolverNestedIntrinsics:
    """Tests for Fn::ToJsonString with nested intrinsic functions.

    Requirement 4.3: WHEN Fn::ToJsonString contains nested intrinsic functions
    that can be resolved, THEN THE Resolver SHALL resolve those intrinsics before
    converting to JSON
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnToJsonStringResolver and mock resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        orchestrator.register_resolver(MockDictResolver)
        orchestrator.register_resolver(MockListResolver)
        return orchestrator

    def test_nested_intrinsic_resolved_first(self, orchestrator: IntrinsicResolver):
        """Test that nested intrinsic is resolved before JSON conversion.

        Requirement 4.3: Resolve nested intrinsics before converting to JSON
        """
        # Fn::MockDict with arg "test" returns {"resolved": "test"}
        value = {"Fn::ToJsonString": {"Fn::MockDict": "test"}}
        result = orchestrator.resolve_value(value)

        assert json.loads(result) == {"resolved": "test"}

    def test_nested_list_intrinsic_resolved(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to list.

        Requirement 4.3: Resolve nested intrinsics before converting to JSON
        """
        # Fn::MockList with arg 3 returns [0, 1, 2]
        value = {"Fn::ToJsonString": {"Fn::MockList": 3}}
        result = orchestrator.resolve_value(value)

        assert json.loads(result) == [0, 1, 2]

    def test_nested_intrinsic_in_dict_value(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic inside a dict value.

        Requirement 4.3: Resolve nested intrinsics before converting to JSON
        """
        value = {"Fn::ToJsonString": {"static": "value", "dynamic": {"Fn::MockDict": "nested"}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"static": "value", "dynamic": {"resolved": "nested"}}

    def test_nested_intrinsic_in_list_element(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic inside a list element.

        Requirement 4.3: Resolve nested intrinsics before converting to JSON
        """
        value = {"Fn::ToJsonString": ["static", {"Fn::MockDict": "nested"}, {"Fn::MockList": 2}]}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == ["static", {"resolved": "nested"}, [0, 1]]


class TestFnToJsonStringResolverWithOrchestrator:
    """Tests for FnToJsonStringResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnToJsonStringResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::ToJsonString through the orchestrator."""
        value = {"Fn::ToJsonString": {"key": "value"}}
        result = orchestrator.resolve_value(value)

        assert json.loads(result) == {"key": "value"}

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::ToJsonString in a nested template structure."""
        value = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Environment": {"Variables": {"CONFIG": {"Fn::ToJsonString": {"setting": "value"}}}}
                    },
                }
            }
        }
        result = orchestrator.resolve_value(value)

        config = result["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]["CONFIG"]
        assert json.loads(config) == {"setting": "value"}

    def test_resolve_multiple_fn_to_json_string(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::ToJsonString in same structure."""
        value = {
            "first": {"Fn::ToJsonString": {"a": 1}},
            "second": {"Fn::ToJsonString": [1, 2, 3]},
            "third": {"Fn::ToJsonString": {}},
        }
        result = orchestrator.resolve_value(value)

        assert json.loads(result["first"]) == {"a": 1}
        assert json.loads(result["second"]) == [1, 2, 3]
        assert json.loads(result["third"]) == {}


class TestFnToJsonStringResolverPartialMode:
    """Tests for FnToJsonStringResolver in partial resolution mode.

    Fn::ToJsonString should always be resolved, even in partial mode.
    Unresolvable intrinsics (like Fn::GetAtt) should be preserved in the JSON output.

    Requirement 4.4: WHEN Fn::ToJsonString contains intrinsic functions that cannot
    be resolved (e.g., Fn::GetAtt), THEN THE Resolver SHALL preserve those intrinsics
    in the JSON output
    """

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnToJsonStringResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        return orchestrator

    def test_fn_to_json_string_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::ToJsonString is resolved even in partial mode.

        Requirement 16.4: In partial mode, still resolve Fn::ToJsonString
        """
        value = {"Fn::ToJsonString": {"key": "value"}}
        result = orchestrator.resolve_value(value)

        assert json.loads(result) == {"key": "value"}

    def test_fn_get_att_preserved_in_json_output(self, orchestrator: IntrinsicResolver):
        """Test that Fn::GetAtt is preserved in JSON output in partial mode.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output
        """
        value = {"Fn::ToJsonString": {"arn": {"Fn::GetAtt": ["MyBucket", "Arn"]}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"arn": {"Fn::GetAtt": ["MyBucket", "Arn"]}}

    def test_mixed_resolvable_and_unresolvable(self, orchestrator: IntrinsicResolver):
        """Test mix of resolvable and unresolvable intrinsics in partial mode."""
        value = {
            "Fn::ToJsonString": {
                "static": "value",
                "preserved": {"Fn::GetAtt": ["Resource", "Attr"]},
                "also_preserved": {"Fn::ImportValue": "ExportName"},
            }
        }
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {
            "static": "value",
            "preserved": {"Fn::GetAtt": ["Resource", "Attr"]},
            "also_preserved": {"Fn::ImportValue": "ExportName"},
        }

    def test_fn_import_value_preserved_in_json_output(self, orchestrator: IntrinsicResolver):
        """Test that Fn::ImportValue is preserved in JSON output in partial mode.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output
        """
        value = {"Fn::ToJsonString": {"imported": {"Fn::ImportValue": "SharedVpcId"}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"imported": {"Fn::ImportValue": "SharedVpcId"}}

    def test_fn_get_azs_preserved_in_json_output(self, orchestrator: IntrinsicResolver):
        """Test that Fn::GetAZs is preserved in JSON output in partial mode.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        Fn::GetAZs returns availability zones for a region and requires
        runtime AWS information, so it must be preserved.
        """
        value = {"Fn::ToJsonString": {"availabilityZones": {"Fn::GetAZs": "us-east-1"}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"availabilityZones": {"Fn::GetAZs": "us-east-1"}}

    def test_fn_get_azs_empty_region_preserved(self, orchestrator: IntrinsicResolver):
        """Test that Fn::GetAZs with empty string (current region) is preserved.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        Fn::GetAZs with empty string returns AZs for the current region.
        """
        value = {"Fn::ToJsonString": {"currentRegionAZs": {"Fn::GetAZs": ""}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"currentRegionAZs": {"Fn::GetAZs": ""}}

    def test_fn_cidr_preserved_in_json_output(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Cidr is preserved in JSON output in partial mode.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        Fn::Cidr generates CIDR address blocks and is typically preserved
        for CloudFormation to resolve.
        """
        value = {"Fn::ToJsonString": {"subnets": {"Fn::Cidr": ["10.0.0.0/16", 6, 8]}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"subnets": {"Fn::Cidr": ["10.0.0.0/16", 6, 8]}}

    def test_ref_to_resource_preserved_in_json_output(self, orchestrator: IntrinsicResolver):
        """Test that Ref to a resource is preserved in JSON output in partial mode.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        Ref to a resource (not a parameter or pseudo-parameter) requires
        the deployed resource's physical ID, so it must be preserved.
        """
        value = {"Fn::ToJsonString": {"bucketName": {"Ref": "MyS3Bucket"}}}
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"bucketName": {"Ref": "MyS3Bucket"}}

    def test_all_unresolvable_intrinsics_preserved_in_list(self, orchestrator: IntrinsicResolver):
        """Test that all unresolvable intrinsics are preserved in a list context.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        This test verifies that unresolvable intrinsics work correctly
        when they appear as list elements rather than dict values.
        """
        value = {
            "Fn::ToJsonString": [
                {"Fn::GetAtt": ["MyBucket", "Arn"]},
                {"Fn::ImportValue": "SharedValue"},
                {"Fn::GetAZs": "us-west-2"},
                {"Fn::Cidr": ["10.0.0.0/8", 3, 5]},
                {"Ref": "MyResource"},
            ]
        }
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == [
            {"Fn::GetAtt": ["MyBucket", "Arn"]},
            {"Fn::ImportValue": "SharedValue"},
            {"Fn::GetAZs": "us-west-2"},
            {"Fn::Cidr": ["10.0.0.0/8", 3, 5]},
            {"Ref": "MyResource"},
        ]

    def test_nested_unresolvable_intrinsics_preserved(self, orchestrator: IntrinsicResolver):
        """Test that deeply nested unresolvable intrinsics are preserved.

        Requirement 4.4: Preserve unresolvable intrinsics in JSON output

        This test verifies that unresolvable intrinsics are preserved
        even when they appear in deeply nested structures.
        """
        value = {
            "Fn::ToJsonString": {"level1": {"level2": {"level3": {"arn": {"Fn::GetAtt": ["DeepResource", "Arn"]}}}}}
        }
        result = orchestrator.resolve_value(value)

        parsed = json.loads(result)
        assert parsed == {"level1": {"level2": {"level3": {"arn": {"Fn::GetAtt": ["DeepResource", "Arn"]}}}}}


# =============================================================================
# Parametrized Tests for Fn::ToJsonString
# =============================================================================


class TestFnToJsonStringParametrizedTests:
    """
    Parametrized tests for Fn::ToJsonString intrinsic function.

    These tests validate that for any dictionary or list value, applying
    Fn::ToJsonString and then json.loads SHALL produce a value equivalent
    to the original (after resolving any nested resolvable intrinsics).

    **Validates: Requirements 4.1, 4.2, 4.3**
    """

    @staticmethod
    def _create_context() -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @staticmethod
    def _create_orchestrator(context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnToJsonStringResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        return orchestrator

    @pytest.mark.parametrize(
        "data",
        [
            {"key": "value", "number": 42},
            {"empty": None, "flag": True, "count": 0},
            {"nested_key": "hello world", "pi": 3.14},
        ],
    )
    def test_fn_to_json_string_round_trip_simple_dict(self, data: Dict[str, Any]):
        """
        For any simple dictionary, applying Fn::ToJsonString and then json.loads
        SHALL produce a value equivalent to the original.

        **Validates: Requirements 4.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    @pytest.mark.parametrize(
        "data",
        [
            [1, "two", 3.0, None, True],
            [],
            [42, -100, 0],
        ],
    )
    def test_fn_to_json_string_round_trip_simple_list(self, data: List[Any]):
        """
        For any simple list, applying Fn::ToJsonString and then json.loads
        SHALL produce a value equivalent to the original.

        **Validates: Requirements 4.2**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    @pytest.mark.parametrize(
        "data",
        [
            {"outer": {"inner": "value", "list": [1, 2]}},
            {"a": {"b": {"c": "deep"}}},
            {"mixed": [{"key": "val"}, [1, 2], "text"]},
        ],
    )
    def test_fn_to_json_string_round_trip_nested_dict(self, data: Dict[str, Any]):
        """
        For any nested dictionary, applying Fn::ToJsonString and then json.loads
        SHALL produce a value equivalent to the original.

        **Validates: Requirements 4.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    @pytest.mark.parametrize(
        "data",
        [
            [[1, 2], [3, 4], [5]],
            [{"a": 1}, {"b": 2}],
            [None, [True, False], {"key": "val"}],
        ],
    )
    def test_fn_to_json_string_round_trip_nested_list(self, data: List[Any]):
        """
        For any nested list, applying Fn::ToJsonString and then json.loads
        SHALL produce a value equivalent to the original.

        **Validates: Requirements 4.2**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    @pytest.mark.parametrize(
        "static_data, mock_value",
        [
            ({"key": "value"}, "test"),
            ({"count": 42, "flag": True}, "hello"),
            ({"name": "resource"}, "world"),
        ],
    )
    def test_fn_to_json_string_round_trip_with_nested_intrinsic(self, static_data: Dict[str, Any], mock_value: str):
        """
        For any dictionary containing nested intrinsic functions that can be resolved,
        applying Fn::ToJsonString and then json.loads SHALL produce a value equivalent
        to the original after resolving the nested intrinsics.

        **Validates: Requirements 4.3**
        """
        context = self._create_context()
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        orchestrator.register_resolver(MockDictResolver)

        input_data = dict(static_data)
        input_data["dynamic"] = {"Fn::MockDict": mock_value}

        value = {"Fn::ToJsonString": input_data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)

        expected = dict(static_data)
        expected["dynamic"] = {"resolved": mock_value}

        parsed = json.loads(result)
        assert parsed == expected

    @pytest.mark.parametrize(
        "items, mock_count",
        [
            ([1, "two"], 3),
            ([], 0),
            ([None, True, 42], 5),
        ],
    )
    def test_fn_to_json_string_round_trip_list_with_nested_intrinsic(self, items: List[Any], mock_count: int):
        """
        For any list containing nested intrinsic functions that can be resolved,
        applying Fn::ToJsonString and then json.loads SHALL produce a value equivalent
        to the original after resolving the nested intrinsics.

        **Validates: Requirements 4.2, 4.3**
        """
        context = self._create_context()
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnToJsonStringResolver)
        orchestrator.register_resolver(MockListResolver)

        input_data = list(items)
        input_data.append({"Fn::MockList": mock_count})

        value = {"Fn::ToJsonString": input_data}
        result = orchestrator.resolve_value(value)

        assert isinstance(result, str)

        expected = list(items)
        expected.append(list(range(mock_count)))

        parsed = json.loads(result)
        assert parsed == expected

    @pytest.mark.parametrize(
        "data",
        [
            {"setting": "value"},
            {"a": 1, "b": [2, 3]},
            {"nested": {"deep": True}},
        ],
    )
    def test_fn_to_json_string_produces_valid_json(self, data: Dict[str, Any]):
        """
        For any dictionary, Fn::ToJsonString SHALL produce a valid JSON string
        that can be parsed without errors.

        **Validates: Requirements 4.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        try:
            parsed = json.loads(result)
        except json.JSONDecodeError as e:
            pytest.fail(f"Fn::ToJsonString produced invalid JSON: {e}")

        assert isinstance(parsed, dict)

    @pytest.mark.parametrize(
        "data",
        [
            [1, 2, 3],
            ["a", None, True],
            [{"key": "val"}, [1, 2]],
        ],
    )
    def test_fn_to_json_string_list_produces_valid_json(self, data: List[Any]):
        """
        For any list, Fn::ToJsonString SHALL produce a valid JSON string
        that can be parsed without errors.

        **Validates: Requirements 4.2**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        try:
            parsed = json.loads(result)
        except json.JSONDecodeError as e:
            pytest.fail(f"Fn::ToJsonString produced invalid JSON: {e}")

        assert isinstance(parsed, list)

    @pytest.mark.parametrize(
        "data",
        [
            {"setting": "value"},
            {"count": 42, "enabled": True},
            {"tags": [{"Key": "env", "Value": "prod"}]},
        ],
    )
    def test_fn_to_json_string_in_template_structure(self, data: Dict[str, Any]):
        """
        For any dictionary embedded in a CloudFormation template structure,
        Fn::ToJsonString SHALL produce a valid JSON string that round-trips correctly.

        **Validates: Requirements 4.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        template_value = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Environment": {"Variables": {"CONFIG": {"Fn::ToJsonString": data}}}},
                }
            }
        }

        result = orchestrator.resolve_value(template_value)

        config_json = result["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]["CONFIG"]
        parsed = json.loads(config_json)
        assert parsed == data

    @pytest.mark.parametrize(
        "data",
        [
            {"key": "value"},
            {"a": 1, "b": "two"},
            {"flag": True, "count": 0},
        ],
    )
    def test_fn_to_json_string_compact_output(self, data: Dict[str, Any]):
        """
        For any dictionary, Fn::ToJsonString SHALL produce compact JSON output
        (no unnecessary whitespace) while still being valid JSON.

        **Validates: Requirements 4.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::ToJsonString": data}
        result = orchestrator.resolve_value(value)

        expected_compact = json.dumps(data, separators=(",", ":"))
        assert result == expected_compact

    @pytest.mark.parametrize(
        "data",
        [
            {"key": "value", "num": 42},
            [1, "two", None],
            {"nested": {"a": [1, 2]}},
        ],
    )
    def test_fn_to_json_string_idempotent_round_trip(self, data: Any):
        """
        For any dictionary or list, the round-trip (Fn::ToJsonString -> json.loads)
        SHALL be idempotent: applying it multiple times produces the same result.

        **Validates: Requirements 4.1, 4.2**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        # First round-trip
        value1 = {"Fn::ToJsonString": data}
        result1 = orchestrator.resolve_value(value1)
        parsed1 = json.loads(result1)

        # Second round-trip (using the parsed result)
        value2 = {"Fn::ToJsonString": parsed1}
        result2 = orchestrator.resolve_value(value2)
        parsed2 = json.loads(result2)

        assert parsed1 == parsed2
        assert result1 == result2
