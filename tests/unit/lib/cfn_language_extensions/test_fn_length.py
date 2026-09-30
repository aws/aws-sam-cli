"""
Unit tests for the FnLengthResolver class.

Tests cover:
- Basic Fn::Length functionality with literal lists
- Nested intrinsic function resolution
- Error handling for non-list inputs
- Integration with IntrinsicResolver orchestrator
- Property-based tests for universal correctness properties

Requirements:
    - 3.1: WHEN Fn::Length is applied to a list, THEN THE Resolver SHALL return
           the number of elements in the list
    - 3.2: WHEN Fn::Length is applied to a nested intrinsic function that resolves
           to a list, THEN THE Resolver SHALL first resolve the inner function
           and then return the length
    - 3.3: WHEN Fn::Length is applied to a non-list value, THEN THE Resolver SHALL
           raise an Invalid_Template_Exception indicating incorrect layout
    - 3.4: WHEN Fn::Length references a parameter that resolves to a CommaDelimitedList,
           THEN THE Resolver SHALL return the count of items in the list
"""

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
from samcli.lib.cfn_language_extensions.resolvers.fn_length import FnLengthResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnLengthResolverCanResolve:
    """Tests for FnLengthResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnLengthResolver:
        """Create a FnLengthResolver for testing."""
        return FnLengthResolver(context, None)

    def test_can_resolve_fn_length(self, resolver: FnLengthResolver):
        """Test that can_resolve returns True for Fn::Length."""
        value = {"Fn::Length": [1, 2, 3]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnLengthResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnLengthResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnLengthResolver):
        """Test that FUNCTION_NAMES contains Fn::Length."""
        assert FnLengthResolver.FUNCTION_NAMES == ["Fn::Length"]


class TestFnLengthResolverBasicFunctionality:
    """Tests for basic Fn::Length functionality.

    Requirement 3.1: WHEN Fn::Length is applied to a list, THEN THE Resolver
    SHALL return the number of elements in the list
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnLengthResolver:
        """Create a FnLengthResolver for testing."""
        return FnLengthResolver(context, None)

    def test_length_of_empty_list(self, resolver: FnLengthResolver):
        """Test Fn::Length with empty list returns 0.

        Requirement 3.1: Return the number of elements in the list
        """
        value: Dict[str, Any] = {"Fn::Length": []}
        assert resolver.resolve(value) == 0

    def test_length_of_single_element_list(self, resolver: FnLengthResolver):
        """Test Fn::Length with single element list returns 1.

        Requirement 3.1: Return the number of elements in the list
        """
        value = {"Fn::Length": ["single"]}
        assert resolver.resolve(value) == 1

    def test_length_of_multiple_element_list(self, resolver: FnLengthResolver):
        """Test Fn::Length with multiple elements returns correct count.

        Requirement 3.1: Return the number of elements in the list
        """
        value = {"Fn::Length": [1, 2, 3, 4, 5]}
        assert resolver.resolve(value) == 5

    def test_length_of_list_with_mixed_types(self, resolver: FnLengthResolver):
        """Test Fn::Length with mixed type elements.

        Requirement 3.1: Return the number of elements in the list
        """
        value = {"Fn::Length": [1, "two", {"three": 3}, [4], None]}
        assert resolver.resolve(value) == 5

    def test_length_of_list_with_nested_lists(self, resolver: FnLengthResolver):
        """Test Fn::Length counts top-level elements only.

        Requirement 3.1: Return the number of elements in the list
        """
        value = {"Fn::Length": [[1, 2], [3, 4, 5], [6]]}
        assert resolver.resolve(value) == 3  # 3 nested lists, not 6 elements


class TestFnLengthResolverErrorHandling:
    """Tests for Fn::Length error handling.

    Requirement 3.3: WHEN Fn::Length is applied to a non-list value, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception indicating incorrect layout
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnLengthResolver:
        """Create a FnLengthResolver for testing."""
        return FnLengthResolver(context, None)

    def test_non_list_string_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with string raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_non_list_integer_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with integer raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": 42}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_non_list_dict_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with dict raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": {"key": "value"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_non_list_none_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with None raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_non_list_boolean_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with boolean raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": True}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_non_list_float_raises_exception(self, resolver: FnLengthResolver):
        """Test Fn::Length with float raises InvalidTemplateException.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        value = {"Fn::Length": 3.14}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_error_message_exact_format(self, resolver: FnLengthResolver):
        """Test that error message matches exact expected format.

        Requirement 3.3: Raise Invalid_Template_Exception indicating incorrect layout

        The error message must be exactly "Fn::Length layout is incorrect" to match
        the Kotlin implementation's error messages.
        """
        value = {"Fn::Length": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        # Verify exact error message format
        assert str(exc_info.value) == "Fn::Length layout is incorrect"


class MockListResolver(IntrinsicFunctionResolver):
    """A mock resolver that returns a list for testing nested resolution."""

    FUNCTION_NAMES = ["Fn::MockList"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return a list based on the argument."""
        args = self.get_function_args(value)
        if isinstance(args, int):
            return list(range(args))
        return args


class TestFnLengthResolverNestedIntrinsics:
    """Tests for Fn::Length with nested intrinsic functions.

    Requirement 3.2: WHEN Fn::Length is applied to a nested intrinsic function
    that resolves to a list, THEN THE Resolver SHALL first resolve the inner
    function and then return the length
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnLengthResolver and MockListResolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnLengthResolver)
        orchestrator.register_resolver(MockListResolver)
        return orchestrator

    def test_nested_intrinsic_resolved_first(self, orchestrator: IntrinsicResolver):
        """Test that nested intrinsic is resolved before length calculation.

        Requirement 3.2: Resolve inner function first, then return length
        """
        # Fn::MockList with arg 5 returns [0, 1, 2, 3, 4]
        value = {"Fn::Length": {"Fn::MockList": 5}}
        result = orchestrator.resolve_value(value)

        assert result == 5

    def test_nested_intrinsic_empty_list(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to empty list.

        Requirement 3.2: Resolve inner function first, then return length
        """
        # Fn::MockList with arg 0 returns []
        value = {"Fn::Length": {"Fn::MockList": 0}}
        result = orchestrator.resolve_value(value)

        assert result == 0

    def test_nested_intrinsic_non_list_raises_exception(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to non-list raises exception.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input
        """
        # Fn::MockList with string arg returns the string as-is
        value = {"Fn::Length": {"Fn::MockList": "not-a-list"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_nested_intrinsic_resolves_to_dict_raises_exception(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to dict raises exception.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input

        This tests the case where a nested intrinsic resolves to a dictionary,
        which is a common mistake when users confuse objects with arrays.
        """
        # Fn::MockList with dict arg returns the dict as-is
        value = {"Fn::Length": {"Fn::MockList": {"key": "value"}}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)

    def test_nested_intrinsic_resolves_to_integer_raises_exception(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to integer raises exception.

        Requirement 3.3: Raise Invalid_Template_Exception for non-list input

        This tests the case where a nested intrinsic resolves to an integer,
        which could happen if a user mistakenly uses a numeric parameter.
        """
        # Create a mock that returns an integer
        value = {"Fn::Length": {"Fn::MockList": {"not": "a list"}}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Fn::Length layout is incorrect" in str(exc_info.value)


class TestFnLengthResolverWithOrchestrator:
    """Tests for FnLengthResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnLengthResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnLengthResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Length through the orchestrator."""
        value = {"Fn::Length": [1, 2, 3]}
        result = orchestrator.resolve_value(value)

        assert result == 3

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Length in a nested template structure."""
        value = {
            "Resources": {
                "MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"DelaySeconds": {"Fn::Length": [1, 2, 3, 4, 5]}}}
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == 5

    def test_resolve_multiple_fn_length(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Length in same structure."""
        value = {
            "first": {"Fn::Length": [1, 2]},
            "second": {"Fn::Length": [1, 2, 3, 4]},
            "third": {"Fn::Length": []},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "first": 2,
            "second": 4,
            "third": 0,
        }

    def test_fn_length_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Length inside a list."""
        value = [
            {"Fn::Length": [1]},
            {"Fn::Length": [1, 2]},
            {"Fn::Length": [1, 2, 3]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == [1, 2, 3]


class TestFnLengthResolverPartialMode:
    """Tests for FnLengthResolver in partial resolution mode.

    Fn::Length should always be resolved, even in partial mode.
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
        """Create an orchestrator in partial mode with FnLengthResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnLengthResolver)
        return orchestrator

    def test_fn_length_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Length is resolved even in partial mode.

        Requirement 16.4: In partial mode, still resolve Fn::Length
        """
        value = {"Fn::Length": [1, 2, 3]}
        result = orchestrator.resolve_value(value)

        assert result == 3

    def test_fn_length_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::Length alongside preserved intrinsics in partial mode."""
        value = {
            "length": {"Fn::Length": [1, 2, 3]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "length": 3,
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


# =============================================================================
# Parametrized Tests for Fn::Length
# =============================================================================


class MockRefResolver(IntrinsicFunctionResolver):
    """A mock resolver that resolves Ref to parameter values for testing."""

    FUNCTION_NAMES = ["Ref"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Resolve Ref to parameter values from context."""
        ref_target = self.get_function_args(value)

        # Check parameter_values in context
        if ref_target in self.context.parameter_values:
            return self.context.parameter_values[ref_target]

        # Return the Ref unchanged if not found
        return value


class MockSplitResolver(IntrinsicFunctionResolver):
    """A mock resolver that implements Fn::Split for testing nested intrinsics."""

    FUNCTION_NAMES = ["Fn::Split"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Split a string by delimiter."""
        args = self.get_function_args(value)
        if not isinstance(args, list) or len(args) != 2:
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        delimiter = args[0]
        source_string = args[1]

        # Resolve nested intrinsics
        if self.parent is not None:
            source_string = self.parent.resolve_value(source_string)

        if not isinstance(source_string, str):
            raise InvalidTemplateException("Fn::Split layout is incorrect")

        return source_string.split(delimiter)


class TestFnLengthPropertyBasedTests:
    """
    Parametrized tests for Fn::Length intrinsic function.

    Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length

    These tests validate that for any list (including lists produced by resolving
    nested intrinsic functions), Fn::Length SHALL return the exact count of elements
    in that list.

    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    @staticmethod
    def _create_context() -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @staticmethod
    def _create_orchestrator(context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnLengthResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnLengthResolver)
        return orchestrator

    @pytest.mark.parametrize(
        "items",
        [
            [],
            [1, "two", None, True, {"k": "v"}],
            list(range(50)),
        ],
        ids=["empty-list", "mixed-types", "large-list"],
    )
    def test_fn_length_returns_exact_count_for_any_list(self, items: List[Any]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::Length": items}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "items",
        [
            [],
            ["alpha", "beta", "gamma"],
            ["subnet-abc", "subnet-def", "subnet-ghi", "subnet-jkl"],
        ],
        ids=["empty-strings", "three-strings", "four-subnet-ids"],
    )
    def test_fn_length_returns_exact_count_for_string_lists(self, items: List[str]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::Length": items}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "items",
        [
            [],
            [10, 20, 30],
            [-1, 0, 1, 2, 3, 4, 5],
        ],
        ids=["empty-ints", "three-ints", "seven-ints"],
    )
    def test_fn_length_returns_exact_count_for_integer_lists(self, items: List[int]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::Length": items}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "delimiter,items",
        [
            (",", ["a", "b", "c"]),
            ("|", ["x", "y"]),
            ("-", ["one", "two", "three", "four", "five"]),
        ],
        ids=["comma-3-items", "pipe-2-items", "dash-5-items"],
    )
    def test_fn_length_with_nested_fn_split_returns_correct_count(self, delimiter: str, items: List[str]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.2**
        """
        context = self._create_context()
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnLengthResolver)
        orchestrator.register_resolver(MockSplitResolver)

        delimited_string = delimiter.join(items)

        value = {"Fn::Length": {"Fn::Split": [delimiter, delimited_string]}}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "items",
        [
            [],
            ["us-east-1", "us-west-2"],
            ["a", "b", "c", "d", "e"],
        ],
        ids=["empty-cdl", "two-regions", "five-items"],
    )
    def test_fn_length_with_comma_delimited_list_parameter(self, items: List[str]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}}, parameter_values={"MyCommaDelimitedList": items}
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnLengthResolver)
        orchestrator.register_resolver(MockRefResolver)

        value = {"Fn::Length": {"Ref": "MyCommaDelimitedList"}}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "outer_items",
        [
            [],
            [[1, 2], [3, 4, 5]],
            [[10], [20, 30], [40, 50, 60]],
        ],
        ids=["empty-nested", "two-nested-lists", "three-nested-lists"],
    )
    def test_fn_length_counts_top_level_elements_only(self, outer_items: List[List[int]]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::Length": outer_items}
        result = orchestrator.resolve_value(value)

        assert result == len(outer_items)

    @pytest.mark.parametrize(
        "items",
        [
            [],
            [{"Key": "Env", "Value": "prod"}],
            [{"Key": "A", "Value": "1"}, {"Key": "B", "Value": "2"}, {"Key": "C", "Value": "3"}],
        ],
        ids=["empty-dicts", "single-tag", "three-tags"],
    )
    def test_fn_length_with_list_of_dicts(self, items: List[Dict[str, Any]]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::Length": items}
        result = orchestrator.resolve_value(value)

        assert result == len(items)

    @pytest.mark.parametrize(
        "items",
        [
            [],
            ["a", "b"],
            [1, 2, 3, 4, 5],
        ],
        ids=["empty-in-template", "two-in-template", "five-in-template"],
    )
    def test_fn_length_in_template_structure(self, items: List[Any]):
        """
        Feature: cfn-language-extensions-python, Property 5: Fn::Length Returns List Length
        **Validates: Requirements 3.1**
        """
        context = self._create_context()
        orchestrator = self._create_orchestrator(context)

        template_value = {
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {"DelaySeconds": {"Fn::Length": items}},
                }
            }
        }

        result = orchestrator.resolve_value(template_value)

        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == len(items)
