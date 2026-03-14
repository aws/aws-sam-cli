"""
Unit tests for the FnSelectResolver class.

Tests cover:
- Basic Fn::Select functionality with literal lists
- Nested intrinsic function resolution
- Error handling for invalid inputs and out-of-bounds index
- Integration with IntrinsicResolver orchestrator

Requirements:
    - 10.5: WHEN Fn::Select is applied to a list with an index, THEN THE
            Resolver SHALL return the element at that index
    - 10.9: WHEN Fn::Select is applied with an out-of-bounds index, THEN THE
            Resolver SHALL raise an Invalid_Template_Exception
"""

import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicFunctionResolver,
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.fn_select import FnSelectResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_split import FnSplitResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_join import FnJoinResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnSelectResolverCanResolve:
    """Tests for FnSelectResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSelectResolver:
        """Create a FnSelectResolver for testing."""
        return FnSelectResolver(context, None)

    def test_can_resolve_fn_select(self, resolver: FnSelectResolver):
        """Test that can_resolve returns True for Fn::Select."""
        value = {"Fn::Select": [0, ["a", "b", "c"]]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnSelectResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False
        assert resolver.can_resolve({"Fn::Split": [",", "a,b"]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnSelectResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnSelectResolver):
        """Test that FUNCTION_NAMES contains Fn::Select."""
        assert FnSelectResolver.FUNCTION_NAMES == ["Fn::Select"]


class TestFnSelectResolverBasicFunctionality:
    """Tests for basic Fn::Select functionality.

    Requirement 10.5: WHEN Fn::Select is applied to a list with an index,
    THEN THE Resolver SHALL return the element at that index
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSelectResolver:
        """Create a FnSelectResolver for testing."""
        return FnSelectResolver(context, None)

    def test_select_first_element(self, resolver: FnSelectResolver):
        """Test Fn::Select with index 0 returns first element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [0, ["a", "b", "c"]]}
        assert resolver.resolve(value) == "a"

    def test_select_middle_element(self, resolver: FnSelectResolver):
        """Test Fn::Select with middle index returns correct element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [1, ["a", "b", "c"]]}
        assert resolver.resolve(value) == "b"

    def test_select_last_element(self, resolver: FnSelectResolver):
        """Test Fn::Select with last index returns last element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [2, ["a", "b", "c"]]}
        assert resolver.resolve(value) == "c"

    def test_select_from_single_element_list(self, resolver: FnSelectResolver):
        """Test Fn::Select from single element list.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [0, ["only"]]}
        assert resolver.resolve(value) == "only"

    def test_select_integer_element(self, resolver: FnSelectResolver):
        """Test Fn::Select returns integer element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [1, [10, 20, 30]]}
        assert resolver.resolve(value) == 20

    def test_select_dict_element(self, resolver: FnSelectResolver):
        """Test Fn::Select returns dict element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [0, [{"key": "value"}, "other"]]}
        assert resolver.resolve(value) == {"key": "value"}

    def test_select_list_element(self, resolver: FnSelectResolver):
        """Test Fn::Select returns nested list element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [1, ["first", ["nested", "list"]]]}
        assert resolver.resolve(value) == ["nested", "list"]

    def test_select_with_string_index(self, resolver: FnSelectResolver):
        """Test Fn::Select with string index that can be converted to int.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": ["1", ["a", "b", "c"]]}
        assert resolver.resolve(value) == "b"

    def test_select_with_string_index_zero(self, resolver: FnSelectResolver):
        """Test Fn::Select with string index "0".

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": ["0", ["first", "second"]]}
        assert resolver.resolve(value) == "first"

    def test_select_null_element(self, resolver: FnSelectResolver):
        """Test Fn::Select returns null element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [1, ["a", None, "c"]]}
        assert resolver.resolve(value) is None

    def test_select_boolean_element(self, resolver: FnSelectResolver):
        """Test Fn::Select returns boolean element.

        Requirement 10.5: Return the element at that index
        """
        value = {"Fn::Select": [0, [True, False]]}
        assert resolver.resolve(value) is True


class TestFnSelectResolverOutOfBounds:
    """Tests for Fn::Select out-of-bounds error handling.

    Requirement 10.9: WHEN Fn::Select is applied with an out-of-bounds index,
    THEN THE Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSelectResolver:
        """Create a FnSelectResolver for testing."""
        return FnSelectResolver(context, None)

    def test_index_equals_list_length_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with index equal to list length raises exception.

        Requirement 10.9: Raise exception for out-of-bounds index
        """
        value = {"Fn::Select": [3, ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select index out of bounds" in str(exc_info.value)

    def test_index_greater_than_list_length_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with index greater than list length raises exception.

        Requirement 10.9: Raise exception for out-of-bounds index
        """
        value = {"Fn::Select": [10, ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select index out of bounds" in str(exc_info.value)

    def test_negative_index_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with negative index raises exception.

        Requirement 10.9: Raise exception for out-of-bounds index
        """
        value = {"Fn::Select": [-1, ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select index out of bounds" in str(exc_info.value)

    def test_index_on_empty_list_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select on empty list raises exception.

        Requirement 10.9: Raise exception for out-of-bounds index
        """
        value = {"Fn::Select": [0, []]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select index out of bounds" in str(exc_info.value)

    def test_string_index_out_of_bounds_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with string index out of bounds raises exception.

        Requirement 10.9: Raise exception for out-of-bounds index
        """
        value = {"Fn::Select": ["5", ["a", "b"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select index out of bounds" in str(exc_info.value)


class TestFnSelectResolverErrorHandling:
    """Tests for Fn::Select error handling for invalid layouts."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSelectResolver:
        """Create a FnSelectResolver for testing."""
        return FnSelectResolver(context, None)

    def test_non_list_args_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with non-list args raises InvalidTemplateException."""
        value = {"Fn::Select": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_single_element_args_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with single element args raises InvalidTemplateException."""
        value = {"Fn::Select": [0]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_three_element_args_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with three element args raises InvalidTemplateException."""
        value = {"Fn::Select": [0, ["a", "b"], "extra"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_non_integer_index_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with non-integer index raises InvalidTemplateException."""
        value = {"Fn::Select": ["abc", ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_float_index_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with float index raises InvalidTemplateException."""
        value = {"Fn::Select": [1.5, ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_non_list_source_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with non-list source raises InvalidTemplateException."""
        value = {"Fn::Select": [0, "not-a-list"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_dict_source_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with dict source raises InvalidTemplateException."""
        value = {"Fn::Select": [0, {"key": "value"}]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_none_args_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with None args raises InvalidTemplateException."""
        value = {"Fn::Select": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_dict_args_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with dict args raises InvalidTemplateException."""
        value = {"Fn::Select": {"index": 0, "list": ["a", "b"]}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_list_index_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with list as index raises InvalidTemplateException."""
        value = {"Fn::Select": [[0], ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)

    def test_none_index_raises_exception(self, resolver: FnSelectResolver):
        """Test Fn::Select with None index raises InvalidTemplateException."""
        value = {"Fn::Select": [None, ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Select layout is incorrect" in str(exc_info.value)


class TestFnSelectResolverNestedIntrinsics:
    """Tests for Fn::Select with nested intrinsic functions."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Index": "1",
                "MyList": "a,b,c",
            },
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnSelectResolver and other resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSelectResolver)
        orchestrator.register_resolver(FnRefResolver)
        orchestrator.register_resolver(FnSplitResolver)
        orchestrator.register_resolver(FnJoinResolver)
        return orchestrator

    def test_nested_split_for_source_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select with Fn::Split resolving to source list."""
        value = {"Fn::Select": [1, {"Fn::Split": [",", "a,b,c"]}]}
        result = orchestrator.resolve_value(value)
        assert result == "b"

    def test_nested_ref_for_index(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select with Ref resolving to index."""
        value = {"Fn::Select": [{"Ref": "Index"}, ["x", "y", "z"]]}
        result = orchestrator.resolve_value(value)
        assert result == "y"

    def test_nested_split_and_ref(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select with both nested Fn::Split and Ref."""
        value = {"Fn::Select": [{"Ref": "Index"}, {"Fn::Split": [",", "x,y,z"]}]}
        result = orchestrator.resolve_value(value)
        assert result == "y"

    def test_select_from_ref_comma_delimited_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select from a Ref that resolves to comma-delimited list."""
        value = {"Fn::Select": [0, {"Fn::Split": [",", {"Ref": "MyList"}]}]}
        result = orchestrator.resolve_value(value)
        assert result == "a"


class TestFnSelectResolverWithOrchestrator:
    """Tests for FnSelectResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnSelectResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSelectResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Select through the orchestrator."""
        value = {"Fn::Select": [0, ["a", "b", "c"]]}
        result = orchestrator.resolve_value(value)
        assert result == "a"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Select in a nested template structure."""
        value = {
            "Resources": {
                "MyResource": {
                    "Type": "AWS::CloudFormation::WaitConditionHandle",
                    "Properties": {"SelectedValue": {"Fn::Select": [1, ["first", "second", "third"]]}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyResource"]["Properties"]["SelectedValue"] == "second"

    def test_resolve_multiple_fn_select(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Select in same structure."""
        value = {
            "first": {"Fn::Select": [0, ["a", "b"]]},
            "second": {"Fn::Select": [1, ["x", "y", "z"]]},
            "third": {"Fn::Select": [2, [1, 2, 3]]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "first": "a",
            "second": "y",
            "third": 3,
        }

    def test_fn_select_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select inside a list."""
        value = [
            {"Fn::Select": [0, ["a"]]},
            {"Fn::Select": [0, ["b", "c"]]},
            {"Fn::Select": [2, ["x", "y", "z"]]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == ["a", "b", "z"]


class TestFnSelectResolverPartialMode:
    """Tests for FnSelectResolver in partial resolution mode."""

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnSelectResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnSelectResolver)
        return orchestrator

    def test_fn_select_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Select is resolved even in partial mode."""
        value = {"Fn::Select": [1, ["a", "b", "c"]]}
        result = orchestrator.resolve_value(value)

        assert result == "b"

    def test_fn_select_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::Select alongside preserved intrinsics in partial mode."""
        value = {
            "selected": {"Fn::Select": [0, ["first", "second"]]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "selected": "first",
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


class TestFnSelectResolverRealWorldExamples:
    """Tests for Fn::Select with real-world CloudFormation patterns."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with multiple resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSelectResolver)
        orchestrator.register_resolver(FnSplitResolver)
        return orchestrator

    def test_select_availability_zone(self, orchestrator: IntrinsicResolver):
        """Test selecting an availability zone from a list."""
        value = {"Fn::Select": [0, ["us-east-1a", "us-east-1b", "us-east-1c"]]}
        assert orchestrator.resolve_value(value) == "us-east-1a"

    def test_select_subnet_from_comma_delimited(self, orchestrator: IntrinsicResolver):
        """Test selecting a subnet from comma-delimited list."""
        value = {"Fn::Select": [1, {"Fn::Split": [",", "subnet-123,subnet-456,subnet-789"]}]}
        assert orchestrator.resolve_value(value) == "subnet-456"

    def test_select_from_arn_parts(self, orchestrator: IntrinsicResolver):
        """Test selecting a part from a split ARN."""
        # Select the service name from an ARN
        value = {"Fn::Select": [2, {"Fn::Split": [":", "arn:aws:s3:::my-bucket"]}]}
        assert orchestrator.resolve_value(value) == "s3"

    def test_select_region_from_arn(self, orchestrator: IntrinsicResolver):
        """Test selecting region from an ARN (empty for S3)."""
        value = {"Fn::Select": [3, {"Fn::Split": [":", "arn:aws:s3:::my-bucket"]}]}
        assert orchestrator.resolve_value(value) == ""

    def test_select_bucket_name_from_arn(self, orchestrator: IntrinsicResolver):
        """Test selecting bucket name from an S3 ARN."""
        value = {"Fn::Select": [5, {"Fn::Split": [":", "arn:aws:s3:::my-bucket"]}]}
        assert orchestrator.resolve_value(value) == "my-bucket"

    def test_select_cidr_octet(self, orchestrator: IntrinsicResolver):
        """Test selecting an octet from a CIDR block."""
        value = {"Fn::Select": [0, {"Fn::Split": [".", "10.0.0.0"]}]}
        assert orchestrator.resolve_value(value) == "10"


class TestFnSelectAndJoinIntegration:
    """Tests for Fn::Select and Fn::Join working together."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with both resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSelectResolver)
        orchestrator.register_resolver(FnJoinResolver)
        orchestrator.register_resolver(FnSplitResolver)
        return orchestrator

    def test_join_selected_elements(self, orchestrator: IntrinsicResolver):
        """Test joining selected elements."""
        value = {
            "Fn::Join": [
                "-",
                [
                    {"Fn::Select": [0, ["prefix", "other"]]},
                    {"Fn::Select": [1, ["x", "middle", "y"]]},
                    {"Fn::Select": [0, ["suffix"]]},
                ],
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result == "prefix-middle-suffix"

    def test_select_from_split_then_join(self, orchestrator: IntrinsicResolver):
        """Test selecting from split result and joining."""
        # Split "a-b-c", select first two, join with comma
        value = {
            "Fn::Join": [
                ",",
                [
                    {"Fn::Select": [0, {"Fn::Split": ["-", "a-b-c"]}]},
                    {"Fn::Select": [1, {"Fn::Split": ["-", "a-b-c"]}]},
                ],
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result == "a,b"
