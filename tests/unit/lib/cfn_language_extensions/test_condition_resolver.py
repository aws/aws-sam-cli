"""
Unit tests for the ConditionResolver class.

Tests cover:
- Fn::Equals functionality
- Fn::And functionality
- Fn::Or functionality
- Fn::Not functionality
- Condition reference functionality
- Circular condition reference detection
- Error handling for invalid inputs
- Integration with IntrinsicResolver orchestrator

Requirements:
    - 8.1: WHEN a Condition section contains language extension functions, THEN THE
           Resolver SHALL resolve them before evaluating conditions
    - 8.4: WHEN conditions contain circular references, THEN THE Resolver SHALL
           raise an Invalid_Template_Exception
"""

import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicFunctionResolver,
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.condition_resolver import ConditionResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestConditionResolverCanResolve:
    """Tests for ConditionResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        """Create a ConditionResolver for testing."""
        return ConditionResolver(context, None)

    def test_can_resolve_fn_equals(self, resolver: ConditionResolver):
        """Test that can_resolve returns True for Fn::Equals."""
        value = {"Fn::Equals": ["a", "b"]}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_fn_and(self, resolver: ConditionResolver):
        """Test that can_resolve returns True for Fn::And."""
        value = {"Fn::And": [True, True]}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_fn_or(self, resolver: ConditionResolver):
        """Test that can_resolve returns True for Fn::Or."""
        value = {"Fn::Or": [True, False]}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_fn_not(self, resolver: ConditionResolver):
        """Test that can_resolve returns True for Fn::Not."""
        value = {"Fn::Not": [True]}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_condition(self, resolver: ConditionResolver):
        """Test that can_resolve returns True for Condition."""
        value = {"Condition": "MyCondition"}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: ConditionResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False

    def test_cannot_resolve_non_dict(self, resolver: ConditionResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: ConditionResolver):
        """Test that FUNCTION_NAMES contains all condition functions."""
        expected = ["Fn::Equals", "Fn::And", "Fn::Or", "Fn::Not", "Condition"]
        assert ConditionResolver.FUNCTION_NAMES == expected


class TestFnEqualsResolver:
    """Tests for Fn::Equals functionality.

    Fn::Equals compares two values and returns true if they are equal.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        """Create a ConditionResolver for testing."""
        return ConditionResolver(context, None)

    def test_equals_same_strings(self, resolver: ConditionResolver):
        """Test Fn::Equals with identical strings returns True."""
        value = {"Fn::Equals": ["value", "value"]}
        assert resolver.resolve(value) is True

    def test_equals_different_strings(self, resolver: ConditionResolver):
        """Test Fn::Equals with different strings returns False."""
        value = {"Fn::Equals": ["value1", "value2"]}
        assert resolver.resolve(value) is False

    def test_equals_same_integers(self, resolver: ConditionResolver):
        """Test Fn::Equals with identical integers returns True."""
        value = {"Fn::Equals": [42, 42]}
        assert resolver.resolve(value) is True

    def test_equals_different_integers(self, resolver: ConditionResolver):
        """Test Fn::Equals with different integers returns False."""
        value = {"Fn::Equals": [42, 43]}
        assert resolver.resolve(value) is False

    def test_equals_same_booleans(self, resolver: ConditionResolver):
        """Test Fn::Equals with identical booleans returns True."""
        value = {"Fn::Equals": [True, True]}
        assert resolver.resolve(value) is True

    def test_equals_different_booleans(self, resolver: ConditionResolver):
        """Test Fn::Equals with different booleans returns False."""
        value = {"Fn::Equals": [True, False]}
        assert resolver.resolve(value) is False

    def test_equals_empty_strings(self, resolver: ConditionResolver):
        """Test Fn::Equals with empty strings returns True."""
        value = {"Fn::Equals": ["", ""]}
        assert resolver.resolve(value) is True

    def test_equals_case_sensitive(self, resolver: ConditionResolver):
        """Test Fn::Equals is case-sensitive for strings."""
        value = {"Fn::Equals": ["Value", "value"]}
        assert resolver.resolve(value) is False

    def test_equals_type_mismatch(self, resolver: ConditionResolver):
        """Test Fn::Equals with different types returns False."""
        value = {"Fn::Equals": ["42", 42]}
        assert resolver.resolve(value) is False

    def test_equals_invalid_layout_not_list(self, resolver: ConditionResolver):
        """Test Fn::Equals with non-list raises InvalidTemplateException."""
        value = {"Fn::Equals": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Equals layout is incorrect" in str(exc_info.value)

    def test_equals_invalid_layout_one_element(self, resolver: ConditionResolver):
        """Test Fn::Equals with one element raises InvalidTemplateException."""
        value = {"Fn::Equals": ["only-one"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Equals layout is incorrect" in str(exc_info.value)

    def test_equals_invalid_layout_three_elements(self, resolver: ConditionResolver):
        """Test Fn::Equals with three elements raises InvalidTemplateException."""
        value = {"Fn::Equals": ["one", "two", "three"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Equals layout is incorrect" in str(exc_info.value)


class TestFnAndResolver:
    """Tests for Fn::And functionality.

    Fn::And returns true if all conditions are true. It accepts 2-10 conditions.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        """Create a ConditionResolver for testing."""
        return ConditionResolver(context, None)

    def test_and_all_true(self, resolver: ConditionResolver):
        """Test Fn::And with all true conditions returns True."""
        value = {"Fn::And": [True, True]}
        assert resolver.resolve(value) is True

    def test_and_one_false(self, resolver: ConditionResolver):
        """Test Fn::And with one false condition returns False."""
        value = {"Fn::And": [True, False]}
        assert resolver.resolve(value) is False

    def test_and_all_false(self, resolver: ConditionResolver):
        """Test Fn::And with all false conditions returns False."""
        value = {"Fn::And": [False, False]}
        assert resolver.resolve(value) is False

    def test_and_multiple_conditions_all_true(self, resolver: ConditionResolver):
        """Test Fn::And with multiple true conditions returns True."""
        value = {"Fn::And": [True, True, True, True, True]}
        assert resolver.resolve(value) is True

    def test_and_multiple_conditions_one_false(self, resolver: ConditionResolver):
        """Test Fn::And with multiple conditions, one false returns False."""
        value = {"Fn::And": [True, True, False, True, True]}
        assert resolver.resolve(value) is False

    def test_and_ten_conditions(self, resolver: ConditionResolver):
        """Test Fn::And with maximum 10 conditions."""
        value = {"Fn::And": [True] * 10}
        assert resolver.resolve(value) is True

    def test_and_string_true(self, resolver: ConditionResolver):
        """Test Fn::And with string 'true' values."""
        value = {"Fn::And": ["true", "true"]}
        assert resolver.resolve(value) is True

    def test_and_string_false(self, resolver: ConditionResolver):
        """Test Fn::And with string 'false' values."""
        value = {"Fn::And": ["true", "false"]}
        assert resolver.resolve(value) is False

    def test_and_invalid_layout_not_list(self, resolver: ConditionResolver):
        """Test Fn::And with non-list raises InvalidTemplateException."""
        value = {"Fn::And": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::And layout is incorrect" in str(exc_info.value)

    def test_and_invalid_layout_one_element(self, resolver: ConditionResolver):
        """Test Fn::And with one element raises InvalidTemplateException."""
        value = {"Fn::And": [True]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::And layout is incorrect" in str(exc_info.value)

    def test_and_invalid_layout_eleven_elements(self, resolver: ConditionResolver):
        """Test Fn::And with more than 10 elements raises InvalidTemplateException."""
        value = {"Fn::And": [True] * 11}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::And layout is incorrect" in str(exc_info.value)


class TestFnOrResolver:
    """Tests for Fn::Or functionality.

    Fn::Or returns true if any condition is true. It accepts 2-10 conditions.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        """Create a ConditionResolver for testing."""
        return ConditionResolver(context, None)

    def test_or_all_true(self, resolver: ConditionResolver):
        """Test Fn::Or with all true conditions returns True."""
        value = {"Fn::Or": [True, True]}
        assert resolver.resolve(value) is True

    def test_or_one_true(self, resolver: ConditionResolver):
        """Test Fn::Or with one true condition returns True."""
        value = {"Fn::Or": [False, True]}
        assert resolver.resolve(value) is True

    def test_or_all_false(self, resolver: ConditionResolver):
        """Test Fn::Or with all false conditions returns False."""
        value = {"Fn::Or": [False, False]}
        assert resolver.resolve(value) is False

    def test_or_multiple_conditions_one_true(self, resolver: ConditionResolver):
        """Test Fn::Or with multiple conditions, one true returns True."""
        value = {"Fn::Or": [False, False, True, False, False]}
        assert resolver.resolve(value) is True

    def test_or_multiple_conditions_all_false(self, resolver: ConditionResolver):
        """Test Fn::Or with multiple false conditions returns False."""
        value = {"Fn::Or": [False, False, False, False, False]}
        assert resolver.resolve(value) is False

    def test_or_ten_conditions(self, resolver: ConditionResolver):
        """Test Fn::Or with maximum 10 conditions."""
        conditions = [False] * 9 + [True]
        value = {"Fn::Or": conditions}
        assert resolver.resolve(value) is True

    def test_or_string_true(self, resolver: ConditionResolver):
        """Test Fn::Or with string 'true' values."""
        value = {"Fn::Or": ["false", "true"]}
        assert resolver.resolve(value) is True

    def test_or_string_false(self, resolver: ConditionResolver):
        """Test Fn::Or with string 'false' values."""
        value = {"Fn::Or": ["false", "false"]}
        assert resolver.resolve(value) is False

    def test_or_invalid_layout_not_list(self, resolver: ConditionResolver):
        """Test Fn::Or with non-list raises InvalidTemplateException."""
        value = {"Fn::Or": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Or layout is incorrect" in str(exc_info.value)

    def test_or_invalid_layout_one_element(self, resolver: ConditionResolver):
        """Test Fn::Or with one element raises InvalidTemplateException."""
        value = {"Fn::Or": [True]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Or layout is incorrect" in str(exc_info.value)

    def test_or_invalid_layout_eleven_elements(self, resolver: ConditionResolver):
        """Test Fn::Or with more than 10 elements raises InvalidTemplateException."""
        value = {"Fn::Or": [False] * 11}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Or layout is incorrect" in str(exc_info.value)


class TestFnNotResolver:
    """Tests for Fn::Not functionality.

    Fn::Not returns the inverse of a condition.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        """Create a ConditionResolver for testing."""
        return ConditionResolver(context, None)

    def test_not_true(self, resolver: ConditionResolver):
        """Test Fn::Not with true returns False."""
        value = {"Fn::Not": [True]}
        assert resolver.resolve(value) is False

    def test_not_false(self, resolver: ConditionResolver):
        """Test Fn::Not with false returns True."""
        value = {"Fn::Not": [False]}
        assert resolver.resolve(value) is True

    def test_not_string_true(self, resolver: ConditionResolver):
        """Test Fn::Not with string 'true' returns False."""
        value = {"Fn::Not": ["true"]}
        assert resolver.resolve(value) is False

    def test_not_string_false(self, resolver: ConditionResolver):
        """Test Fn::Not with string 'false' returns True."""
        value = {"Fn::Not": ["false"]}
        assert resolver.resolve(value) is True

    def test_not_invalid_layout_not_list(self, resolver: ConditionResolver):
        """Test Fn::Not with non-list raises InvalidTemplateException."""
        value = {"Fn::Not": True}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Not layout is incorrect" in str(exc_info.value)

    def test_not_invalid_layout_empty_list(self, resolver: ConditionResolver):
        """Test Fn::Not with empty list raises InvalidTemplateException."""
        value: Dict[str, Any] = {"Fn::Not": []}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Not layout is incorrect" in str(exc_info.value)

    def test_not_invalid_layout_two_elements(self, resolver: ConditionResolver):
        """Test Fn::Not with two elements raises InvalidTemplateException."""
        value = {"Fn::Not": [True, False]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Not layout is incorrect" in str(exc_info.value)


class TestConditionReference:
    """Tests for Condition reference functionality.

    The Condition intrinsic function references a named condition from
    the Conditions section of the template.
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
                "IsProduction": {"Fn::Equals": ["prod", "prod"]},
                "IsDevelopment": {"Fn::Equals": ["dev", "prod"]},
                "AlwaysTrue": True,
                "AlwaysFalse": False,
            },
        )
        return context

    @pytest.fixture
    def orchestrator(self, context_with_conditions: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        return orchestrator

    def test_condition_reference_true(self, orchestrator: IntrinsicResolver):
        """Test Condition reference to a true condition."""
        value = {"Condition": "AlwaysTrue"}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_condition_reference_false(self, orchestrator: IntrinsicResolver):
        """Test Condition reference to a false condition."""
        value = {"Condition": "AlwaysFalse"}
        result = orchestrator.resolve_value(value)
        assert result is False

    def test_condition_reference_with_fn_equals(self, orchestrator: IntrinsicResolver):
        """Test Condition reference to a condition with Fn::Equals."""
        value = {"Condition": "IsProduction"}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_condition_reference_with_fn_equals_false(self, orchestrator: IntrinsicResolver):
        """Test Condition reference to a condition with Fn::Equals that is false."""
        value = {"Condition": "IsDevelopment"}
        result = orchestrator.resolve_value(value)
        assert result is False

    def test_condition_reference_caches_result(self, context_with_conditions: TemplateProcessingContext):
        """Test that condition results are cached."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)

        # First resolution
        value = {"Condition": "IsProduction"}
        orchestrator.resolve_value(value)

        # Check that result is cached
        assert "IsProduction" in context_with_conditions.resolved_conditions
        assert context_with_conditions.resolved_conditions["IsProduction"] is True

    def test_condition_reference_not_found(self, orchestrator: IntrinsicResolver):
        """Test Condition reference to non-existent condition raises exception."""
        value = {"Condition": "NonExistentCondition"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Condition 'NonExistentCondition' not found" in str(exc_info.value)

    def test_condition_reference_invalid_layout(self, orchestrator: IntrinsicResolver):
        """Test Condition with non-string raises InvalidTemplateException."""
        value = {"Condition": 123}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Condition layout is incorrect" in str(exc_info.value)


class TestCircularConditionDetection:
    """Tests for circular condition reference detection.

    Requirement 8.4: WHEN conditions contain circular references, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception
    """

    def test_direct_circular_reference(self):
        """Test detection of direct circular reference (A -> A)."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "CircularCondition": {"Condition": "CircularCondition"},
            },
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)

        value = {"Condition": "CircularCondition"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Circular condition reference detected" in str(exc_info.value)

    def test_indirect_circular_reference(self):
        """Test detection of indirect circular reference (A -> B -> A)."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "ConditionA": {"Condition": "ConditionB"},
                "ConditionB": {"Condition": "ConditionA"},
            },
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)

        value = {"Condition": "ConditionA"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Circular condition reference detected" in str(exc_info.value)

    def test_longer_circular_chain(self):
        """Test detection of longer circular chain (A -> B -> C -> A)."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "ConditionA": {"Condition": "ConditionB"},
                "ConditionB": {"Condition": "ConditionC"},
                "ConditionC": {"Condition": "ConditionA"},
            },
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)

        value = {"Condition": "ConditionA"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Circular condition reference detected" in str(exc_info.value)

    def test_circular_reference_in_fn_and(self):
        """Test detection of circular reference within Fn::And."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "ConditionA": {"Fn::And": [True, {"Condition": "ConditionB"}]},
                "ConditionB": {"Condition": "ConditionA"},
            },
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)

        value = {"Condition": "ConditionA"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Circular condition reference detected" in str(exc_info.value)

    def test_non_circular_chain(self):
        """Test that non-circular chains work correctly."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
        )
        context.parsed_template = ParsedTemplate(
            resources={},
            conditions={
                "ConditionA": {"Condition": "ConditionB"},
                "ConditionB": {"Condition": "ConditionC"},
                "ConditionC": True,
            },
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)

        value = {"Condition": "ConditionA"}
        result = orchestrator.resolve_value(value)

        assert result is True


class TestNestedConditionFunctions:
    """Tests for nested condition functions.

    Requirement 8.1: WHEN a Condition section contains language extension functions,
    THEN THE Resolver SHALL resolve them before evaluating conditions
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)
        return orchestrator

    def test_nested_fn_equals_in_fn_and(self, orchestrator: IntrinsicResolver):
        """Test Fn::And with nested Fn::Equals."""
        value = {"Fn::And": [{"Fn::Equals": ["a", "a"]}, {"Fn::Equals": ["b", "b"]}]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_nested_fn_equals_in_fn_or(self, orchestrator: IntrinsicResolver):
        """Test Fn::Or with nested Fn::Equals."""
        value = {"Fn::Or": [{"Fn::Equals": ["a", "b"]}, {"Fn::Equals": ["c", "c"]}]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_nested_fn_not_in_fn_and(self, orchestrator: IntrinsicResolver):
        """Test Fn::And with nested Fn::Not."""
        value = {"Fn::And": [{"Fn::Not": [False]}, {"Fn::Not": [False]}]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_deeply_nested_conditions(self, orchestrator: IntrinsicResolver):
        """Test deeply nested condition functions."""
        value = {
            "Fn::And": [
                {"Fn::Or": [{"Fn::Equals": ["a", "b"]}, {"Fn::Not": [False]}]},
                {"Fn::Not": [{"Fn::Equals": ["x", "y"]}]},
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_not_with_nested_fn_equals(self, orchestrator: IntrinsicResolver):
        """Test Fn::Not with nested Fn::Equals."""
        value = {"Fn::Not": [{"Fn::Equals": ["a", "b"]}]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_not_with_nested_fn_and(self, orchestrator: IntrinsicResolver):
        """Test Fn::Not with nested Fn::And."""
        value = {"Fn::Not": [{"Fn::And": [True, False]}]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_not_with_nested_fn_or(self, orchestrator: IntrinsicResolver):
        """Test Fn::Not with nested Fn::Or."""
        value = {"Fn::Not": [{"Fn::Or": [False, False]}]}
        result = orchestrator.resolve_value(value)
        assert result is True


class TestConditionResolverWithOrchestrator:
    """Tests for ConditionResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with ConditionResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(ConditionResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving condition functions through the orchestrator."""
        value = {"Fn::Equals": ["a", "a"]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving condition functions in a nested template structure."""
        value = {
            "Conditions": {
                "IsProduction": {"Fn::Equals": ["prod", "prod"]},
                "IsDevelopment": {"Fn::Equals": ["dev", "prod"]},
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Conditions"]["IsProduction"] is True
        assert result["Conditions"]["IsDevelopment"] is False

    def test_resolve_multiple_conditions(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple condition functions in same structure."""
        value = {
            "cond1": {"Fn::Equals": ["a", "a"]},
            "cond2": {"Fn::And": [True, True]},
            "cond3": {"Fn::Or": [False, True]},
            "cond4": {"Fn::Not": [False]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "cond1": True,
            "cond2": True,
            "cond3": True,
            "cond4": True,
        }

    def test_condition_in_list(self, orchestrator: IntrinsicResolver):
        """Test condition functions inside a list."""
        value = [
            {"Fn::Equals": ["a", "a"]},
            {"Fn::Equals": ["a", "b"]},
            {"Fn::Not": [True]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == [True, False, False]


class TestConditionResolverPartialMode:
    """Tests for ConditionResolver in partial resolution mode.

    Condition functions should always be resolved, even in partial mode.
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
        """Create an orchestrator in partial mode with ConditionResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(ConditionResolver)
        return orchestrator

    def test_fn_equals_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Equals is resolved even in partial mode."""
        value = {"Fn::Equals": ["a", "a"]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_and_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::And is resolved even in partial mode."""
        value = {"Fn::And": [True, True]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_or_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Or is resolved even in partial mode."""
        value = {"Fn::Or": [False, True]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_fn_not_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Not is resolved even in partial mode."""
        value = {"Fn::Not": [False]}
        result = orchestrator.resolve_value(value)
        assert result is True

    def test_condition_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test condition functions alongside preserved intrinsics in partial mode."""
        value = {
            "condition": {"Fn::Equals": ["a", "a"]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "condition": True,
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


class TestConditionResolverAdditionalEdgeCases:
    """Tests for ConditionResolver additional edge cases."""

    @pytest.fixture
    def context_with_conditions(self) -> TemplateProcessingContext:
        conditions = {
            "IsProduction": {"Fn::Equals": ["prod", "prod"]},
            "IsDevelopment": {"Fn::Equals": ["dev", "prod"]},
        }
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Conditions": conditions})
        ctx.parsed_template = ParsedTemplate(resources={}, conditions=conditions)
        return ctx

    def test_unknown_function_not_resolvable(self, context_with_conditions: TemplateProcessingContext):
        """Test that unknown function name is not resolvable by ConditionResolver."""
        resolver = ConditionResolver(context_with_conditions, None)
        value = {"Fn::Unknown": ["a", "b"]}
        assert not resolver.can_resolve(value)

    def test_ref_in_condition_function_raises_exception(self, context_with_conditions: TemplateProcessingContext):
        """Test that Ref inside Fn::And raises exception."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        value = {"Fn::And": [{"Ref": "SomeParam"}, True]}
        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)
        assert "boolean operations" in str(exc_info.value).lower()

    def test_condition_not_found_raises_exception(self, context_with_conditions: TemplateProcessingContext):
        """Test that referencing non-existent condition raises exception."""
        orchestrator = IntrinsicResolver(context_with_conditions)
        orchestrator.register_resolver(ConditionResolver)
        value = {"Condition": "NonExistentCondition"}
        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)
        assert "not found" in str(exc_info.value).lower()

    def test_to_boolean_with_non_boolean_value(self, context_with_conditions: TemplateProcessingContext):
        """Test _to_boolean with non-boolean, non-string values."""
        resolver = ConditionResolver(context_with_conditions, None)
        assert resolver._to_boolean(1) is True
        assert resolver._to_boolean(0) is False
        assert resolver._to_boolean([1, 2, 3]) is True
        assert resolver._to_boolean([]) is False


class TestConditionResolverStringBooleans:
    """Tests for ConditionResolver handling of string booleans."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        ctx = TemplateProcessingContext(fragment={"Resources": {}})
        ctx.parsed_template = ParsedTemplate(resources={}, conditions={})
        return ctx

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> ConditionResolver:
        return ConditionResolver(context, None)

    def test_string_true_in_fn_not(self, resolver: ConditionResolver):
        result = resolver._resolve_not(["true"])
        assert result is False

    def test_string_false_in_fn_not(self, resolver: ConditionResolver):
        result = resolver._resolve_not(["false"])
        assert result is True

    def test_string_TRUE_uppercase_in_fn_not(self, resolver: ConditionResolver):
        result = resolver._resolve_not(["TRUE"])
        assert result is False
