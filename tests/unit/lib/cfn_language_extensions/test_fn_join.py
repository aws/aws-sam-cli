"""
Unit tests for the FnJoinResolver class.

Tests cover:
- Basic Fn::Join functionality with literal lists
- Nested intrinsic function resolution
- Error handling for invalid inputs
- Integration with IntrinsicResolver orchestrator

Requirements:
    - 10.3: WHEN Fn::Join is applied to a list with a delimiter, THEN THE
            Resolver SHALL return a string with all list elements joined by
            the delimiter
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
from samcli.lib.cfn_language_extensions.resolvers.fn_join import FnJoinResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnJoinResolverCanResolve:
    """Tests for FnJoinResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnJoinResolver:
        """Create a FnJoinResolver for testing."""
        return FnJoinResolver(context, None)

    def test_can_resolve_fn_join(self, resolver: FnJoinResolver):
        """Test that can_resolve returns True for Fn::Join."""
        value = {"Fn::Join": [",", ["a", "b", "c"]]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnJoinResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Split": [",", "a,b,c"]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnJoinResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnJoinResolver):
        """Test that FUNCTION_NAMES contains Fn::Join."""
        assert FnJoinResolver.FUNCTION_NAMES == ["Fn::Join"]


class TestFnJoinResolverBasicFunctionality:
    """Tests for basic Fn::Join functionality.

    Requirement 10.3: WHEN Fn::Join is applied to a list with a delimiter,
    THEN THE Resolver SHALL return a string with all list elements joined
    by the delimiter
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnJoinResolver:
        """Create a FnJoinResolver for testing."""
        return FnJoinResolver(context, None)

    def test_join_with_comma_delimiter(self, resolver: FnJoinResolver):
        """Test Fn::Join with comma delimiter.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [",", ["a", "b", "c"]]}
        assert resolver.resolve(value) == "a,b,c"

    def test_join_with_hyphen_delimiter(self, resolver: FnJoinResolver):
        """Test Fn::Join with hyphen delimiter.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": ["-", ["2023", "01", "15"]]}
        assert resolver.resolve(value) == "2023-01-15"

    def test_join_with_empty_delimiter(self, resolver: FnJoinResolver):
        """Test Fn::Join with empty delimiter.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": ["", ["Hello", "World"]]}
        assert resolver.resolve(value) == "HelloWorld"

    def test_join_with_space_delimiter(self, resolver: FnJoinResolver):
        """Test Fn::Join with space delimiter.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [" ", ["Hello", "World"]]}
        assert resolver.resolve(value) == "Hello World"

    def test_join_with_multi_char_delimiter(self, resolver: FnJoinResolver):
        """Test Fn::Join with multi-character delimiter.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [" :: ", ["a", "b", "c"]]}
        assert resolver.resolve(value) == "a :: b :: c"

    def test_join_empty_list(self, resolver: FnJoinResolver):
        """Test Fn::Join with empty list returns empty string.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [",", []]}
        assert resolver.resolve(value) == ""

    def test_join_single_element_list(self, resolver: FnJoinResolver):
        """Test Fn::Join with single element list.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [",", ["single"]]}
        assert resolver.resolve(value) == "single"

    def test_join_with_numbers(self, resolver: FnJoinResolver):
        """Test Fn::Join with numeric elements.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": ["-", [1, 2, 3]]}
        assert resolver.resolve(value) == "1-2-3"

    def test_join_with_mixed_types(self, resolver: FnJoinResolver):
        """Test Fn::Join with mixed type elements.

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [",", ["string", 42, 3.14, True, False]]}
        assert resolver.resolve(value) == "string,42,3.14,true,false"

    def test_join_with_none_element(self, resolver: FnJoinResolver):
        """Test Fn::Join with None element (converts to empty string).

        Requirement 10.3: Return string with elements joined by delimiter
        """
        value = {"Fn::Join": [",", ["a", None, "b"]]}
        assert resolver.resolve(value) == "a,,b"


class TestFnJoinResolverErrorHandling:
    """Tests for Fn::Join error handling."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnJoinResolver:
        """Create a FnJoinResolver for testing."""
        return FnJoinResolver(context, None)

    def test_non_list_args_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with non-list args raises InvalidTemplateException."""
        value = {"Fn::Join": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_single_element_args_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with single element args raises InvalidTemplateException."""
        value = {"Fn::Join": [","]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_three_element_args_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with three element args raises InvalidTemplateException."""
        value = {"Fn::Join": [",", ["a", "b"], "extra"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_non_string_delimiter_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with non-string delimiter raises InvalidTemplateException."""
        value = {"Fn::Join": [123, ["a", "b"]]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_non_list_second_arg_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with non-list second arg raises InvalidTemplateException."""
        value = {"Fn::Join": [",", "not-a-list"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_none_args_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with None args raises InvalidTemplateException."""
        value = {"Fn::Join": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)

    def test_dict_args_raises_exception(self, resolver: FnJoinResolver):
        """Test Fn::Join with dict args raises InvalidTemplateException."""
        value = {"Fn::Join": {"delimiter": ",", "list": ["a", "b"]}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Join layout is incorrect" in str(exc_info.value)


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


class TestFnJoinResolverNestedIntrinsics:
    """Tests for Fn::Join with nested intrinsic functions."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Delimiter": "-",
                "Items": ["a", "b", "c"],
            },
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnJoinResolver and FnRefResolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnJoinResolver)
        orchestrator.register_resolver(FnRefResolver)
        orchestrator.register_resolver(MockSplitResolver)
        return orchestrator

    def test_nested_ref_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Join with Ref in list items."""
        # Delimiter parameter is "-", so we join ["-", "value"] with "-"
        # Result: "-" + "-" + "value" = "--value"
        value = {"Fn::Join": ["-", [{"Ref": "Delimiter"}, "value"]]}
        result = orchestrator.resolve_value(value)
        assert result == "--value"

    def test_nested_ref_for_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Join with Ref resolving to list."""
        value = {"Fn::Join": [",", {"Ref": "Items"}]}
        result = orchestrator.resolve_value(value)
        assert result == "a,b,c"

    def test_nested_split_in_join(self, orchestrator: IntrinsicResolver):
        """Test Fn::Join with nested Fn::Split."""
        value = {"Fn::Join": ["-", {"Fn::Split": [",", "a,b,c"]}]}
        result = orchestrator.resolve_value(value)
        assert result == "a-b-c"


class TestFnJoinResolverWithOrchestrator:
    """Tests for FnJoinResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnJoinResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnJoinResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Join through the orchestrator."""
        value = {"Fn::Join": [",", ["a", "b", "c"]]}
        result = orchestrator.resolve_value(value)
        assert result == "a,b,c"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Join in a nested template structure."""
        value = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::Join": ["-", ["my", "bucket", "name"]]}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket-name"

    def test_resolve_multiple_fn_join(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Join in same structure."""
        value = {
            "first": {"Fn::Join": [",", ["a", "b"]]},
            "second": {"Fn::Join": ["-", ["x", "y", "z"]]},
            "third": {"Fn::Join": ["", ["Hello", "World"]]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "first": "a,b",
            "second": "x-y-z",
            "third": "HelloWorld",
        }

    def test_fn_join_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Join inside a list."""
        value = [
            {"Fn::Join": [",", ["a"]]},
            {"Fn::Join": [",", ["a", "b"]]},
            {"Fn::Join": [",", ["a", "b", "c"]]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == ["a", "a,b", "a,b,c"]


class TestFnJoinResolverPartialMode:
    """Tests for FnJoinResolver in partial resolution mode."""

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnJoinResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnJoinResolver)
        return orchestrator

    def test_fn_join_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Join is resolved even in partial mode."""
        value = {"Fn::Join": [",", ["a", "b", "c"]]}
        result = orchestrator.resolve_value(value)

        assert result == "a,b,c"

    def test_fn_join_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::Join alongside preserved intrinsics in partial mode."""
        value = {
            "joined": {"Fn::Join": ["-", ["a", "b"]]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "joined": "a-b",
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


class TestFnJoinResolverRealWorldExamples:
    """Tests for Fn::Join with real-world CloudFormation patterns."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnJoinResolver:
        """Create a FnJoinResolver for testing."""
        return FnJoinResolver(context, None)

    def test_join_arn_components(self, resolver: FnJoinResolver):
        """Test joining ARN components."""
        value = {"Fn::Join": [":", ["arn", "aws", "s3", "", "", "my-bucket"]]}
        assert resolver.resolve(value) == "arn:aws:s3:::my-bucket"

    def test_join_path_components(self, resolver: FnJoinResolver):
        """Test joining path components."""
        value = {"Fn::Join": ["/", ["", "var", "log", "app"]]}
        assert resolver.resolve(value) == "/var/log/app"

    def test_join_cidr_blocks(self, resolver: FnJoinResolver):
        """Test joining CIDR block components."""
        value = {"Fn::Join": [".", ["10", "0", "0", "0/16"]]}
        assert resolver.resolve(value) == "10.0.0.0/16"

    def test_join_tags(self, resolver: FnJoinResolver):
        """Test joining tag values."""
        value = {"Fn::Join": ["-", ["prod", "us-east-1", "app"]]}
        assert resolver.resolve(value) == "prod-us-east-1-app"


class TestFnJoinToStringEdgeCases:
    """Tests for FnJoinResolver._to_string() method edge cases (lines 134-138)."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnJoinResolver:
        return FnJoinResolver(context, None)

    def test_join_with_nested_list(self, resolver: FnJoinResolver):
        """Test Fn::Join with nested list elements (converts to comma-separated string)."""
        value = {"Fn::Join": ["-", [["a", "b"], "c"]]}
        result = resolver.resolve(value)
        assert result == "a,b-c"

    def test_join_with_dict_element(self, resolver: FnJoinResolver):
        """Test Fn::Join with dict element (converts to string representation)."""
        value = {"Fn::Join": ["-", ["prefix", {"key": "value"}, "suffix"]]}
        result = resolver.resolve(value)
        assert "prefix" in result
        assert "suffix" in result
        assert "key" in result

    def test_join_with_deeply_nested_list(self, resolver: FnJoinResolver):
        """Test Fn::Join with deeply nested list elements."""
        value = {"Fn::Join": ["-", [["x", ["y", "z"]], "end"]]}
        result = resolver.resolve(value)
        assert "x" in result
        assert "y" in result
        assert "z" in result
        assert "end" in result
