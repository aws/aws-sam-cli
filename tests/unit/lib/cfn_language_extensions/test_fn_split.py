"""
Unit tests for the FnSplitResolver class.

Tests cover:
- Basic Fn::Split functionality with literal strings
- Nested intrinsic function resolution
- Error handling for invalid inputs
- Integration with IntrinsicResolver orchestrator

Requirements:
    - 10.4: WHEN Fn::Split is applied to a string with a delimiter, THEN THE
            Resolver SHALL return a list of strings split by the delimiter
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
from samcli.lib.cfn_language_extensions.resolvers.fn_split import FnSplitResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_sub import FnSubResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnSplitResolverCanResolve:
    """Tests for FnSplitResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSplitResolver:
        """Create a FnSplitResolver for testing."""
        return FnSplitResolver(context, None)

    def test_can_resolve_fn_split(self, resolver: FnSplitResolver):
        """Test that can_resolve returns True for Fn::Split."""
        value = {"Fn::Split": [",", "a,b,c"]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnSplitResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnSplitResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnSplitResolver):
        """Test that FUNCTION_NAMES contains Fn::Split."""
        assert FnSplitResolver.FUNCTION_NAMES == ["Fn::Split"]


class TestFnSplitResolverBasicFunctionality:
    """Tests for basic Fn::Split functionality.

    Requirement 10.4: WHEN Fn::Split is applied to a string with a delimiter,
    THEN THE Resolver SHALL return a list of strings split by the delimiter
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSplitResolver:
        """Create a FnSplitResolver for testing."""
        return FnSplitResolver(context, None)

    def test_split_with_comma_delimiter(self, resolver: FnSplitResolver):
        """Test Fn::Split with comma delimiter.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", "a,b,c"]}
        assert resolver.resolve(value) == ["a", "b", "c"]

    def test_split_with_hyphen_delimiter(self, resolver: FnSplitResolver):
        """Test Fn::Split with hyphen delimiter.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": ["-", "2023-01-15"]}
        assert resolver.resolve(value) == ["2023", "01", "15"]

    def test_split_with_empty_delimiter(self, resolver: FnSplitResolver):
        """Test Fn::Split with empty delimiter raises error.

        Kotlin implementation raises error for empty delimiter.
        """
        value = {"Fn::Split": ["", "abc"]}
        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)
        assert "delimiter cannot be empty" in str(exc_info.value)

    def test_split_with_space_delimiter(self, resolver: FnSplitResolver):
        """Test Fn::Split with space delimiter.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [" ", "Hello World"]}
        assert resolver.resolve(value) == ["Hello", "World"]

    def test_split_with_multi_char_delimiter(self, resolver: FnSplitResolver):
        """Test Fn::Split with multi-character delimiter.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [" :: ", "a :: b :: c"]}
        assert resolver.resolve(value) == ["a", "b", "c"]

    def test_split_empty_string(self, resolver: FnSplitResolver):
        """Test Fn::Split with empty string returns list with empty string.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", ""]}
        assert resolver.resolve(value) == [""]

    def test_split_no_delimiter_found(self, resolver: FnSplitResolver):
        """Test Fn::Split when delimiter not found returns single element list.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", "no-commas-here"]}
        assert resolver.resolve(value) == ["no-commas-here"]

    def test_split_consecutive_delimiters(self, resolver: FnSplitResolver):
        """Test Fn::Split with consecutive delimiters creates empty strings.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", "a,,b"]}
        assert resolver.resolve(value) == ["a", "", "b"]

    def test_split_delimiter_at_start(self, resolver: FnSplitResolver):
        """Test Fn::Split with delimiter at start.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", ",a,b"]}
        assert resolver.resolve(value) == ["", "a", "b"]

    def test_split_delimiter_at_end(self, resolver: FnSplitResolver):
        """Test Fn::Split with delimiter at end.

        Requirement 10.4: Return list of strings split by delimiter
        """
        value = {"Fn::Split": [",", "a,b,"]}
        assert resolver.resolve(value) == ["a", "b", ""]


class TestFnSplitResolverErrorHandling:
    """Tests for Fn::Split error handling."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSplitResolver:
        """Create a FnSplitResolver for testing."""
        return FnSplitResolver(context, None)

    def test_non_list_args_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with non-list args raises InvalidTemplateException."""
        value = {"Fn::Split": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_single_element_args_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with single element args raises InvalidTemplateException."""
        value = {"Fn::Split": [","]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_three_element_args_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with three element args raises InvalidTemplateException."""
        value = {"Fn::Split": [",", "a,b", "extra"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_non_string_delimiter_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with non-string delimiter raises InvalidTemplateException."""
        value = {"Fn::Split": [123, "a,b,c"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_non_string_source_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with non-string source raises InvalidTemplateException."""
        value = {"Fn::Split": [",", 123]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_list_source_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with list source raises InvalidTemplateException."""
        value = {"Fn::Split": [",", ["a", "b", "c"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_none_args_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with None args raises InvalidTemplateException."""
        value = {"Fn::Split": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)

    def test_dict_args_raises_exception(self, resolver: FnSplitResolver):
        """Test Fn::Split with dict args raises InvalidTemplateException."""
        value = {"Fn::Split": {"delimiter": ",", "string": "a,b,c"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Split layout is incorrect" in str(exc_info.value)


class TestFnSplitResolverNestedIntrinsics:
    """Tests for Fn::Split with nested intrinsic functions."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Delimiter": ",",
                "SourceString": "a,b,c",
            },
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnSplitResolver and FnRefResolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSplitResolver)
        orchestrator.register_resolver(FnRefResolver)
        orchestrator.register_resolver(FnSubResolver)
        return orchestrator

    def test_nested_ref_for_source_string(self, orchestrator: IntrinsicResolver):
        """Test Fn::Split with Ref resolving to source string."""
        value = {"Fn::Split": [",", {"Ref": "SourceString"}]}
        result = orchestrator.resolve_value(value)
        assert result == ["a", "b", "c"]

    def test_nested_sub_for_source_string(self, orchestrator: IntrinsicResolver):
        """Test Fn::Split with Fn::Sub for source string."""
        # Add parameter for Sub
        orchestrator.context.parameter_values["Prefix"] = "x"
        value = {"Fn::Split": [",", {"Fn::Sub": "${Prefix},y,z"}]}
        result = orchestrator.resolve_value(value)
        assert result == ["x", "y", "z"]


class TestFnSplitResolverWithOrchestrator:
    """Tests for FnSplitResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnSplitResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSplitResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Split through the orchestrator."""
        value = {"Fn::Split": [",", "a,b,c"]}
        result = orchestrator.resolve_value(value)
        assert result == ["a", "b", "c"]

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Split in a nested template structure."""
        value = {
            "Resources": {
                "MyResource": {
                    "Type": "AWS::CloudFormation::WaitConditionHandle",
                    "Properties": {"Tags": {"Fn::Split": [",", "tag1,tag2,tag3"]}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyResource"]["Properties"]["Tags"] == ["tag1", "tag2", "tag3"]

    def test_resolve_multiple_fn_split(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Split in same structure."""
        value = {
            "first": {"Fn::Split": [",", "a,b"]},
            "second": {"Fn::Split": ["-", "x-y-z"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "first": ["a", "b"],
            "second": ["x", "y", "z"],
        }

    def test_fn_split_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Split inside a list."""
        value = [
            {"Fn::Split": [",", "a"]},
            {"Fn::Split": [",", "a,b"]},
            {"Fn::Split": [",", "a,b,c"]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == [["a"], ["a", "b"], ["a", "b", "c"]]


class TestFnSplitResolverPartialMode:
    """Tests for FnSplitResolver in partial resolution mode."""

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnSplitResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnSplitResolver)
        return orchestrator

    def test_fn_split_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Split is resolved even in partial mode."""
        value = {"Fn::Split": [",", "a,b,c"]}
        result = orchestrator.resolve_value(value)

        assert result == ["a", "b", "c"]

    def test_fn_split_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::Split alongside preserved intrinsics in partial mode."""
        value = {
            "split": {"Fn::Split": ["-", "a-b"]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "split": ["a", "b"],
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


class TestFnSplitResolverRealWorldExamples:
    """Tests for Fn::Split with real-world CloudFormation patterns."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSplitResolver:
        """Create a FnSplitResolver for testing."""
        return FnSplitResolver(context, None)

    def test_split_arn(self, resolver: FnSplitResolver):
        """Test splitting an ARN."""
        value = {"Fn::Split": [":", "arn:aws:s3:::my-bucket"]}
        assert resolver.resolve(value) == ["arn", "aws", "s3", "", "", "my-bucket"]

    def test_split_comma_delimited_list(self, resolver: FnSplitResolver):
        """Test splitting a comma-delimited list (common parameter type)."""
        value = {"Fn::Split": [",", "subnet-123,subnet-456,subnet-789"]}
        assert resolver.resolve(value) == ["subnet-123", "subnet-456", "subnet-789"]

    def test_split_path(self, resolver: FnSplitResolver):
        """Test splitting a path."""
        value = {"Fn::Split": ["/", "/var/log/app"]}
        assert resolver.resolve(value) == ["", "var", "log", "app"]

    def test_split_cidr(self, resolver: FnSplitResolver):
        """Test splitting a CIDR block."""
        value = {"Fn::Split": [".", "10.0.0.0"]}
        assert resolver.resolve(value) == ["10", "0", "0", "0"]

    def test_split_availability_zones(self, resolver: FnSplitResolver):
        """Test splitting availability zones."""
        value = {"Fn::Split": [",", "us-east-1a,us-east-1b,us-east-1c"]}
        assert resolver.resolve(value) == ["us-east-1a", "us-east-1b", "us-east-1c"]


class TestFnJoinAndSplitIntegration:
    """Tests for Fn::Join and Fn::Split working together."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with both resolvers."""
        from samcli.lib.cfn_language_extensions.resolvers.fn_join import FnJoinResolver

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSplitResolver)
        orchestrator.register_resolver(FnJoinResolver)
        return orchestrator

    def test_split_then_join_with_different_delimiter(self, orchestrator: IntrinsicResolver):
        """Test splitting and then joining with a different delimiter."""
        # Split by comma, join by hyphen
        value = {"Fn::Join": ["-", {"Fn::Split": [",", "a,b,c"]}]}
        result = orchestrator.resolve_value(value)
        assert result == "a-b-c"

    def test_join_then_split_roundtrip(self, orchestrator: IntrinsicResolver):
        """Test joining and then splitting returns original list."""
        # Join with comma, split by comma
        value = {"Fn::Split": [",", {"Fn::Join": [",", ["a", "b", "c"]]}]}
        result = orchestrator.resolve_value(value)
        assert result == ["a", "b", "c"]


class TestFnSplitResolverMultiKeyDictSource:
    """Tests for Fn::Split with multi-key dict source string."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSplitResolver:
        return FnSplitResolver(context, None)

    def test_multi_key_dict_source_raises_exception(self, resolver: FnSplitResolver):
        """Test that multi-key dict source string raises InvalidTemplateException."""
        value = {"Fn::Split": [",", {"key1": "val1", "key2": "val2"}]}
        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)
        assert "Fn::Split layout is incorrect" in str(exc_info.value)
