"""
Unit tests for the FnIfResolver class.

Tests cover:
- Basic Fn::If functionality with true/false conditions
- Condition evaluation from resolved_conditions cache
- Condition evaluation from template Conditions section
- AWS::NoValue handling
- Nested intrinsic function resolution
- Error handling for invalid inputs
- Integration with IntrinsicResolver orchestrator
- Property-based tests for universal correctness properties

Requirements:
    - 8.2: WHEN Fn::If references a condition, THEN THE Resolver SHALL evaluate
           the condition and return the appropriate branch
    - 8.3: WHEN Fn::If references a non-existent condition, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
    - 8.5: WHEN a resource has a Condition attribute, THEN THE Resolver SHALL
           only process the resource if the condition evaluates to true
"""

import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_if import FnIfResolver, AWS_NO_VALUE
from samcli.lib.cfn_language_extensions.resolvers.condition_resolver import ConditionResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnIfResolverCanResolve:
    """Tests for FnIfResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnIfResolver:
        """Create a FnIfResolver for testing."""
        return FnIfResolver(context, None)

    def test_can_resolve_fn_if(self, resolver: FnIfResolver):
        """Test that can_resolve returns True for Fn::If."""
        value = {"Fn::If": ["Condition", "true-value", "false-value"]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnIfResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Equals": ["a", "b"]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnIfResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnIfResolver):
        """Test that FUNCTION_NAMES contains Fn::If."""
        assert FnIfResolver.FUNCTION_NAMES == ["Fn::If"]


class TestFnIfResolverBasicFunctionality:
    """Tests for basic Fn::If functionality.

    Requirement 8.2: WHEN Fn::If references a condition, THEN THE Resolver
    SHALL evaluate the condition and return the appropriate branch
    """

    @pytest.fixture
    def context_with_resolved_conditions(self) -> TemplateProcessingContext:
        """Create a context with pre-resolved conditions."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.resolved_conditions = {
            "IsProduction": True,
            "IsDevelopment": False,
            "AlwaysTrue": True,
            "AlwaysFalse": False,
        }
        return context

    @pytest.fixture
    def resolver(self, context_with_resolved_conditions: TemplateProcessingContext) -> FnIfResolver:
        """Create a FnIfResolver for testing."""
        return FnIfResolver(context_with_resolved_conditions, None)

    def test_fn_if_returns_true_branch_when_condition_true(self, resolver: FnIfResolver):
        """Test Fn::If returns value_if_true when condition is true."""
        value = {"Fn::If": ["IsProduction", "prod-value", "dev-value"]}
        result = resolver.resolve(value)
        assert result == "prod-value"

    def test_fn_if_returns_false_branch_when_condition_false(self, resolver: FnIfResolver):
        """Test Fn::If returns value_if_false when condition is false."""
        value = {"Fn::If": ["IsDevelopment", "dev-value", "other-value"]}
        result = resolver.resolve(value)
        assert result == "other-value"

    def test_fn_if_with_always_true_condition(self, resolver: FnIfResolver):
        """Test Fn::If with a condition that is always true."""
        value = {"Fn::If": ["AlwaysTrue", "yes", "no"]}
        result = resolver.resolve(value)
        assert result == "yes"

    def test_fn_if_with_always_false_condition(self, resolver: FnIfResolver):
        """Test Fn::If with a condition that is always false."""
        value = {"Fn::If": ["AlwaysFalse", "yes", "no"]}
        result = resolver.resolve(value)
        assert result == "no"

    def test_fn_if_with_dict_values(self, resolver: FnIfResolver):
        """Test Fn::If with dictionary values in branches."""
        value = {"Fn::If": ["IsProduction", {"key": "prod"}, {"key": "dev"}]}
        result = resolver.resolve(value)
        assert result == {"key": "prod"}

    def test_fn_if_with_list_values(self, resolver: FnIfResolver):
        """Test Fn::If with list values in branches."""
        value = {"Fn::If": ["IsProduction", ["a", "b"], ["c", "d"]]}
        result = resolver.resolve(value)
        assert result == ["a", "b"]

    def test_fn_if_with_integer_values(self, resolver: FnIfResolver):
        """Test Fn::If with integer values in branches."""
        value = {"Fn::If": ["IsProduction", 100, 50]}
        result = resolver.resolve(value)
        assert result == 100

    def test_fn_if_with_boolean_values(self, resolver: FnIfResolver):
        """Test Fn::If with boolean values in branches."""
        value = {"Fn::If": ["IsProduction", True, False]}
        result = resolver.resolve(value)
        assert result is True


class TestFnIfResolverConditionEvaluation:
    """Tests for condition evaluation from template Conditions section."""

    @pytest.fixture
    def context_with_conditions(self) -> TemplateProcessingContext:
        """Create a context with conditions defined in parsed template."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "IsProduction": {"Fn::Equals": ["prod", "prod"]},
                "IsDevelopment": {"Fn::Equals": ["dev", "prod"]},
                "BooleanTrue": True,
                "BooleanFalse": False,
                "StringTrue": "true",
                "StringFalse": "false",
            },
        )
        return context

    @pytest.fixture
    def orchestrator(self, context_with_conditions: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnIfResolver and ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)
        return orchestrator

    def test_fn_if_evaluates_condition_from_template(self, orchestrator: IntrinsicResolver):
        """Test Fn::If evaluates condition from template Conditions section."""
        value = {"Fn::If": ["IsProduction", "prod", "dev"]}
        result = orchestrator.resolve_value(value)
        assert result == "prod"

    def test_fn_if_evaluates_false_condition_from_template(self, orchestrator: IntrinsicResolver):
        """Test Fn::If evaluates false condition from template."""
        value = {"Fn::If": ["IsDevelopment", "dev", "other"]}
        result = orchestrator.resolve_value(value)
        assert result == "other"

    def test_fn_if_with_boolean_true_condition(self, orchestrator: IntrinsicResolver):
        """Test Fn::If with boolean true condition."""
        value = {"Fn::If": ["BooleanTrue", "yes", "no"]}
        result = orchestrator.resolve_value(value)
        assert result == "yes"

    def test_fn_if_with_boolean_false_condition(self, orchestrator: IntrinsicResolver):
        """Test Fn::If with boolean false condition."""
        value = {"Fn::If": ["BooleanFalse", "yes", "no"]}
        result = orchestrator.resolve_value(value)
        assert result == "no"

    def test_fn_if_with_string_true_condition(self, orchestrator: IntrinsicResolver):
        """Test Fn::If with string 'true' condition."""
        value = {"Fn::If": ["StringTrue", "yes", "no"]}
        result = orchestrator.resolve_value(value)
        assert result == "yes"

    def test_fn_if_with_string_false_condition(self, orchestrator: IntrinsicResolver):
        """Test Fn::If with string 'false' condition."""
        value = {"Fn::If": ["StringFalse", "yes", "no"]}
        result = orchestrator.resolve_value(value)
        assert result == "no"

    def test_fn_if_caches_condition_result(self, context_with_conditions: TemplateProcessingContext):
        """Test that condition results are cached after evaluation."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)

        # First resolution
        value = {"Fn::If": ["IsProduction", "prod", "dev"]}
        orchestrator.resolve_value(value)

        # Check that result is cached
        assert "IsProduction" in context_with_conditions.resolved_conditions
        assert context_with_conditions.resolved_conditions["IsProduction"] is True


class TestFnIfResolverNonExistentCondition:
    """Tests for non-existent condition handling.

    Requirement 8.3: WHEN Fn::If references a non-existent condition, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def context_with_conditions(self) -> TemplateProcessingContext:
        """Create a context with conditions defined."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "ExistingCondition": True,
            },
        )
        return context

    @pytest.fixture
    def orchestrator(self, context_with_conditions: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnIfResolver registered."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)
        return orchestrator

    def test_fn_if_raises_for_non_existent_condition(self, orchestrator: IntrinsicResolver):
        """Test Fn::If raises InvalidTemplateException for non-existent condition."""
        value = {"Fn::If": ["NonExistentCondition", "yes", "no"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Condition 'NonExistentCondition' not found" in str(exc_info.value)

    def test_fn_if_raises_when_no_parsed_template(self):
        """Test Fn::If raises when parsed_template is None."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        # parsed_template is None by default

        resolver = FnIfResolver(context, None)
        value = {"Fn::If": ["SomeCondition", "yes", "no"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Condition 'SomeCondition' not found" in str(exc_info.value)


class TestFnIfResolverAwsNoValue:
    """Tests for AWS::NoValue handling.

    When Fn::If returns {"Ref": "AWS::NoValue"}, the property should be removed.
    """

    @pytest.fixture
    def context_with_conditions(self) -> TemplateProcessingContext:
        """Create a context with conditions defined."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.resolved_conditions = {
            "IsProduction": True,
            "IsDevelopment": False,
        }
        return context

    @pytest.fixture
    def resolver(self, context_with_conditions: TemplateProcessingContext) -> FnIfResolver:
        """Create a FnIfResolver for testing."""
        return FnIfResolver(context_with_conditions, None)

    def test_fn_if_returns_none_for_no_value_true_branch(self, resolver: FnIfResolver):
        """Test Fn::If returns None when true branch is AWS::NoValue."""
        value = {"Fn::If": ["IsProduction", {"Ref": "AWS::NoValue"}, "dev-value"]}
        result = resolver.resolve(value)
        assert result is None

    def test_fn_if_returns_none_for_no_value_false_branch(self, resolver: FnIfResolver):
        """Test Fn::If returns None when false branch is AWS::NoValue."""
        value = {"Fn::If": ["IsDevelopment", "dev-value", {"Ref": "AWS::NoValue"}]}
        result = resolver.resolve(value)
        assert result is None

    def test_fn_if_returns_value_when_no_value_not_selected(self, resolver: FnIfResolver):
        """Test Fn::If returns value when AWS::NoValue is not selected."""
        value = {"Fn::If": ["IsProduction", "prod-value", {"Ref": "AWS::NoValue"}]}
        result = resolver.resolve(value)
        assert result == "prod-value"

    def test_is_no_value_ref_with_valid_no_value(self, resolver: FnIfResolver):
        """Test _is_no_value_ref returns True for valid AWS::NoValue ref."""
        assert resolver._is_no_value_ref({"Ref": "AWS::NoValue"}) is True

    def test_is_no_value_ref_with_other_ref(self, resolver: FnIfResolver):
        """Test _is_no_value_ref returns False for other Ref values."""
        assert resolver._is_no_value_ref({"Ref": "SomeParameter"}) is False

    def test_is_no_value_ref_with_non_dict(self, resolver: FnIfResolver):
        """Test _is_no_value_ref returns False for non-dict values."""
        assert resolver._is_no_value_ref("string") is False
        assert resolver._is_no_value_ref(123) is False
        assert resolver._is_no_value_ref(None) is False

    def test_is_no_value_ref_with_multi_key_dict(self, resolver: FnIfResolver):
        """Test _is_no_value_ref returns False for dict with multiple keys."""
        assert resolver._is_no_value_ref({"Ref": "AWS::NoValue", "extra": "key"}) is False


class TestFnIfResolverInvalidLayout:
    """Tests for invalid layout handling."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.resolved_conditions = {"SomeCondition": True}
        return context

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnIfResolver:
        """Create a FnIfResolver for testing."""
        return FnIfResolver(context, None)

    def test_fn_if_invalid_layout_not_list(self, resolver: FnIfResolver):
        """Test Fn::If with non-list raises InvalidTemplateException."""
        value = {"Fn::If": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_empty_list(self, resolver: FnIfResolver):
        """Test Fn::If with empty list raises InvalidTemplateException."""
        value: Dict[str, Any] = {"Fn::If": []}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_one_element(self, resolver: FnIfResolver):
        """Test Fn::If with one element raises InvalidTemplateException."""
        value = {"Fn::If": ["Condition"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_two_elements(self, resolver: FnIfResolver):
        """Test Fn::If with two elements raises InvalidTemplateException."""
        value = {"Fn::If": ["Condition", "value"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_four_elements(self, resolver: FnIfResolver):
        """Test Fn::If with four elements raises InvalidTemplateException."""
        value = {"Fn::If": ["Condition", "true", "false", "extra"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_non_string_condition(self, resolver: FnIfResolver):
        """Test Fn::If with non-string condition name raises InvalidTemplateException."""
        value = {"Fn::If": [123, "true", "false"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_list_condition(self, resolver: FnIfResolver):
        """Test Fn::If with list as condition name raises InvalidTemplateException."""
        value = {"Fn::If": [["Condition"], "true", "false"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)

    def test_fn_if_invalid_layout_dict_condition(self, resolver: FnIfResolver):
        """Test Fn::If with dict as condition name raises InvalidTemplateException."""
        value = {"Fn::If": [{"key": "value"}, "true", "false"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::If layout is incorrect" in str(exc_info.value)


class TestFnIfResolverNestedIntrinsics:
    """Tests for nested intrinsic function resolution."""

    @pytest.fixture
    def context_with_conditions(self) -> TemplateProcessingContext:
        """Create a context with conditions defined."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Environment": "prod"},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            parameters={"Environment": {"Type": "String"}},
            conditions={
                "IsProduction": True,
                "IsDevelopment": False,
            },
        )
        context.resolved_conditions = {
            "IsProduction": True,
            "IsDevelopment": False,
        }
        return context

    @pytest.fixture
    def orchestrator(self, context_with_conditions: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with multiple resolvers registered."""
        from samcli.lib.cfn_language_extensions.resolvers.fn_join import FnJoinResolver
        from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver

        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)
        orchestrator.register_resolver(FnJoinResolver)
        orchestrator.register_resolver(FnRefResolver)
        return orchestrator

    def test_fn_if_resolves_nested_fn_join_in_true_branch(self, orchestrator: IntrinsicResolver):
        """Test Fn::If resolves nested Fn::Join in true branch."""
        value = {"Fn::If": ["IsProduction", {"Fn::Join": ["-", ["prod", "value"]]}, "dev-value"]}
        result = orchestrator.resolve_value(value)
        assert result == "prod-value"

    def test_fn_if_resolves_nested_fn_join_in_false_branch(self, orchestrator: IntrinsicResolver):
        """Test Fn::If resolves nested Fn::Join in false branch."""
        value = {"Fn::If": ["IsDevelopment", "dev-value", {"Fn::Join": ["-", ["other", "value"]]}]}
        result = orchestrator.resolve_value(value)
        assert result == "other-value"

    def test_fn_if_resolves_nested_ref_in_true_branch(self, orchestrator: IntrinsicResolver):
        """Test Fn::If resolves nested Ref in true branch."""
        value = {"Fn::If": ["IsProduction", {"Ref": "Environment"}, "dev"]}
        result = orchestrator.resolve_value(value)
        assert result == "prod"

    def test_fn_if_with_nested_dict_containing_intrinsics(self, orchestrator: IntrinsicResolver):
        """Test Fn::If resolves intrinsics in nested dict values."""
        value = {
            "Fn::If": [
                "IsProduction",
                {"Name": {"Fn::Join": ["-", ["app", "prod"]]}, "Env": {"Ref": "Environment"}},
                {"Name": "app-dev", "Env": "dev"},
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result == {"Name": "app-prod", "Env": "prod"}


class TestFnIfResolverWithOrchestrator:
    """Tests for FnIfResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a template processing context."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "IsProduction": {"Fn::Equals": ["prod", "prod"]},
                "IsDevelopment": {"Fn::Equals": ["dev", "prod"]},
            },
        )
        return context

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnIfResolver and ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::If through the orchestrator."""
        value = {"Fn::If": ["IsProduction", "prod", "dev"]}
        result = orchestrator.resolve_value(value)
        assert result == "prod"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::If in a nested structure."""
        value = {"Properties": {"Environment": {"Fn::If": ["IsProduction", "production", "development"]}}}
        result = orchestrator.resolve_value(value)
        assert result == {"Properties": {"Environment": "production"}}

    def test_resolve_multiple_fn_if_in_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::If in a structure."""
        value = {
            "Env": {"Fn::If": ["IsProduction", "prod", "dev"]},
            "Debug": {"Fn::If": ["IsDevelopment", True, False]},
        }
        result = orchestrator.resolve_value(value)
        assert result == {"Env": "prod", "Debug": False}

    def test_nested_fn_if(self, orchestrator: IntrinsicResolver):
        """Test nested Fn::If expressions."""
        value = {"Fn::If": ["IsProduction", {"Fn::If": ["IsDevelopment", "nested-dev", "nested-prod"]}, "outer-dev"]}
        result = orchestrator.resolve_value(value)
        # IsProduction is True, so we evaluate the inner Fn::If
        # IsDevelopment is False, so we get "nested-prod"
        assert result == "nested-prod"


class TestFnIfResolverToBooleanConversion:
    """Tests for _to_boolean conversion method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnIfResolver:
        """Create a FnIfResolver for testing."""
        return FnIfResolver(context, None)

    def test_to_boolean_with_true(self, resolver: FnIfResolver):
        """Test _to_boolean with boolean True."""
        assert resolver._to_boolean(True) is True

    def test_to_boolean_with_false(self, resolver: FnIfResolver):
        """Test _to_boolean with boolean False."""
        assert resolver._to_boolean(False) is False

    def test_to_boolean_with_string_true(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'true'."""
        assert resolver._to_boolean("true") is True

    def test_to_boolean_with_string_false(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'false'."""
        assert resolver._to_boolean("false") is False

    def test_to_boolean_with_string_true_uppercase(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'TRUE'."""
        assert resolver._to_boolean("TRUE") is True

    def test_to_boolean_with_string_false_uppercase(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'FALSE'."""
        assert resolver._to_boolean("FALSE") is False

    def test_to_boolean_with_string_true_mixed_case(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'True'."""
        assert resolver._to_boolean("True") is True

    def test_to_boolean_with_string_false_mixed_case(self, resolver: FnIfResolver):
        """Test _to_boolean with string 'False'."""
        assert resolver._to_boolean("False") is False

    def test_to_boolean_with_non_empty_string(self, resolver: FnIfResolver):
        """Test _to_boolean with non-empty string (truthy)."""
        assert resolver._to_boolean("some-string") is True

    def test_to_boolean_with_empty_string(self, resolver: FnIfResolver):
        """Test _to_boolean with empty string (falsy)."""
        assert resolver._to_boolean("") is False

    def test_to_boolean_with_non_zero_integer(self, resolver: FnIfResolver):
        """Test _to_boolean with non-zero integer (truthy)."""
        assert resolver._to_boolean(1) is True
        assert resolver._to_boolean(42) is True

    def test_to_boolean_with_zero(self, resolver: FnIfResolver):
        """Test _to_boolean with zero (falsy)."""
        assert resolver._to_boolean(0) is False

    def test_to_boolean_with_non_empty_list(self, resolver: FnIfResolver):
        """Test _to_boolean with non-empty list (truthy)."""
        assert resolver._to_boolean([1, 2, 3]) is True

    def test_to_boolean_with_empty_list(self, resolver: FnIfResolver):
        """Test _to_boolean with empty list (falsy)."""
        assert resolver._to_boolean([]) is False


class TestFnIfResolverAwsNoValueConstant:
    """Tests for AWS_NO_VALUE constant."""

    def test_aws_no_value_constant(self):
        """Test AWS_NO_VALUE constant value."""
        assert AWS_NO_VALUE == "AWS::NoValue"


# =============================================================================
# Parametrized Tests for Fn::If Condition Evaluation
# =============================================================================


class TestFnIfParametrizedTests:
    """
    Parametrized tests for Fn::If condition evaluation.

    These tests validate that for any Fn::If referencing a condition that evaluates
    to true, the resolver SHALL return the second argument (value_if_true); for false,
    it SHALL return the third argument (value_if_false).

    **Validates: Requirements 8.2, 8.5**
    """

    @staticmethod
    def _create_context_with_condition(condition_name: str, condition_value: bool) -> TemplateProcessingContext:
        """Create a template processing context with a pre-resolved condition."""
        context = TemplateProcessingContext(fragment={"Resources": {}})
        context.resolved_conditions = {condition_name: condition_value}
        context.parsed_template = ParsedTemplate(resources={}, conditions={condition_name: condition_value})
        return context

    @staticmethod
    def _create_orchestrator(context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnIfResolver and ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)
        orchestrator.register_resolver(FnIfResolver)
        return orchestrator

    @pytest.mark.parametrize(
        "condition_name, value_if_true, value_if_false",
        [
            ("IsProduction", "prod-value", "dev-value"),
            ("EnableFeature", {"key": "enabled"}, {"key": "disabled"}),
            ("UseHighCapacity", [1, 2, 3], []),
        ],
    )
    def test_fn_if_returns_true_branch_when_condition_is_true(
        self,
        condition_name: str,
        value_if_true: Any,
        value_if_false: Any,
    ):
        """
        For any Fn::If referencing a condition that evaluates to true, the resolver
        SHALL return the second argument (value_if_true).

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, True)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::If": [condition_name, value_if_true, value_if_false]}
        result = orchestrator.resolve_value(value)

        assert result == value_if_true

    @pytest.mark.parametrize(
        "condition_name, value_if_true, value_if_false",
        [
            ("IsProduction", "prod-value", "dev-value"),
            ("EnableFeature", {"key": "enabled"}, {"key": "disabled"}),
            ("UseHighCapacity", [1, 2, 3], []),
        ],
    )
    def test_fn_if_returns_false_branch_when_condition_is_false(
        self,
        condition_name: str,
        value_if_true: Any,
        value_if_false: Any,
    ):
        """
        For any Fn::If referencing a condition that evaluates to false, the resolver
        SHALL return the third argument (value_if_false).

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, False)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::If": [condition_name, value_if_true, value_if_false]}
        result = orchestrator.resolve_value(value)

        assert result == value_if_false

    @pytest.mark.parametrize(
        "condition_name, condition_value, value_if_true, value_if_false",
        [
            ("IsProduction", True, "prod", "dev"),
            ("IsProduction", False, "prod", "dev"),
            ("EnableDebug", True, 100, 0),
        ],
    )
    def test_fn_if_returns_correct_branch_for_any_condition_value(
        self,
        condition_name: str,
        condition_value: bool,
        value_if_true: Any,
        value_if_false: Any,
    ):
        """
        For any condition value (true or false), Fn::If SHALL return the correct branch.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::If": [condition_name, value_if_true, value_if_false]}
        result = orchestrator.resolve_value(value)

        expected = value_if_true if condition_value else value_if_false
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value, string_value",
        [
            ("IsProduction", True, "hello"),
            ("IsProduction", False, "world"),
            ("EnableFeature", True, ""),
        ],
    )
    def test_fn_if_with_string_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
        string_value: str,
    ):
        """
        For any Fn::If with string branch values, the resolver SHALL return the
        correct string based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = f"true-{string_value}"
        false_value = f"false-{string_value}"

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value, int_value",
        [
            ("IsProduction", True, 42),
            ("IsProduction", False, -100),
            ("EnableFeature", True, 0),
        ],
    )
    def test_fn_if_with_integer_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
        int_value: int,
    ):
        """
        For any Fn::If with integer branch values, the resolver SHALL return the
        correct integer based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = int_value
        false_value = int_value * 2

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value, list_items",
        [
            ("IsProduction", True, ["a", "b", "c"]),
            ("IsProduction", False, ["x"]),
            ("EnableFeature", True, []),
        ],
    )
    def test_fn_if_with_list_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
        list_items: List[str],
    ):
        """
        For any Fn::If with list branch values, the resolver SHALL return the
        correct list based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = list_items
        false_value = list_items[::-1]

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value, dict_value",
        [
            ("IsProduction", True, {"region": "us-east-1"}),
            ("IsProduction", False, {"tier": "standard", "count": "5"}),
            ("EnableFeature", True, {}),
        ],
    )
    def test_fn_if_with_dict_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
        dict_value: Dict[str, str],
    ):
        """
        For any Fn::If with dictionary branch values, the resolver SHALL return the
        correct dictionary based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = {"env": "prod", **dict_value}
        false_value = {"env": "dev", **dict_value}

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value",
        [
            ("IsProduction", True),
            ("IsProduction", False),
            ("EnableFeature", True),
        ],
    )
    def test_fn_if_with_boolean_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
    ):
        """
        For any Fn::If with boolean branch values, the resolver SHALL return the
        correct boolean based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = True
        false_value = False

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected

    @pytest.mark.parametrize(
        "condition_name, condition_value",
        [
            ("IsProduction", True),
            ("IsProduction", False),
            ("EnableFeature", False),
        ],
    )
    def test_fn_if_with_none_branch_values(
        self,
        condition_name: str,
        condition_value: bool,
    ):
        """
        For any Fn::If with None branch values, the resolver SHALL return the
        correct None or non-None value based on the condition value.

        **Validates: Requirements 8.2, 8.5**
        """
        context = self._create_context_with_condition(condition_name, condition_value)
        orchestrator = self._create_orchestrator(context)

        true_value = "has-value"
        false_value = None

        value = {"Fn::If": [condition_name, true_value, false_value]}
        result = orchestrator.resolve_value(value)

        expected = true_value if condition_value else false_value
        assert result == expected
