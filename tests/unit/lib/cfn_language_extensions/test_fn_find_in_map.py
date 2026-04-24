"""
Unit tests for the FnFindInMapResolver class.

Tests cover:
- Basic Fn::FindInMap functionality with valid map lookups
- DefaultValue fallback when keys are not found
- Nested intrinsic function resolution in keys
- Error handling for invalid layouts and missing keys
- Integration with IntrinsicResolver orchestrator

Requirements:
    - 5.1: WHEN Fn::FindInMap is applied with valid map name, top-level key, and
           second-level key, THEN THE Resolver SHALL return the corresponding
           value from the Mappings section
    - 5.2: WHEN Fn::FindInMap includes a DefaultValue option and the top-level key
           is not found, THEN THE Resolver SHALL return the default value
    - 5.3: WHEN Fn::FindInMap includes a DefaultValue option and the second-level key
           is not found, THEN THE Resolver SHALL return the default value
    - 5.4: WHEN Fn::FindInMap keys contain nested intrinsic functions (Fn::Select,
           Fn::Split, Fn::If, Fn::Join, Fn::Sub), THEN THE Resolver SHALL resolve
           those intrinsics before performing the lookup
    - 5.5: WHEN Fn::FindInMap is applied with an invalid layout, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
    - 5.6: WHEN Fn::FindInMap lookup fails without a DefaultValue, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
"""

import pytest
from typing import Any, Dict, Optional

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicFunctionResolver,
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.fn_find_in_map import FnFindInMapResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException

# =============================================================================
# Test Fixtures and Helper Classes
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


class MockSelectResolver(IntrinsicFunctionResolver):
    """A mock resolver that implements Fn::Select for testing nested intrinsics."""

    FUNCTION_NAMES = ["Fn::Select"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Select an item from a list by index."""
        args = self.get_function_args(value)
        if not isinstance(args, list) or len(args) != 2:
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        index = args[0]
        items = args[1]

        # Resolve nested intrinsics
        if self.parent is not None:
            items = self.parent.resolve_value(items)

        if not isinstance(items, list):
            raise InvalidTemplateException("Fn::Select layout is incorrect")

        if not isinstance(index, int) or index < 0 or index >= len(items):
            raise InvalidTemplateException("Fn::Select index out of bounds")

        return items[index]


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


# =============================================================================
# Unit Tests for FnFindInMapResolver.can_resolve()
# =============================================================================


class TestFnFindInMapResolverCanResolve:
    """Tests for FnFindInMapResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}, "Mappings": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnFindInMapResolver:
        """Create a FnFindInMapResolver for testing."""
        return FnFindInMapResolver(context, None)

    def test_can_resolve_fn_find_in_map(self, resolver: FnFindInMapResolver):
        """Test that can_resolve returns True for Fn::FindInMap."""
        value = {"Fn::FindInMap": ["MapName", "TopKey", "SecondKey"]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnFindInMapResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnFindInMapResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnFindInMapResolver):
        """Test that FUNCTION_NAMES contains Fn::FindInMap."""
        assert FnFindInMapResolver.FUNCTION_NAMES == ["Fn::FindInMap"]


# =============================================================================
# Unit Tests for Basic Fn::FindInMap Functionality
# =============================================================================


class TestFnFindInMapResolverBasicFunctionality:
    """Tests for basic Fn::FindInMap functionality.

    Requirement 5.1: WHEN Fn::FindInMap is applied with valid map name, top-level
    key, and second-level key, THEN THE Resolver SHALL return the corresponding
    value from the Mappings section
    """

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {
            "RegionMap": {
                "us-east-1": {"AMI": "ami-12345678", "InstanceType": "t2.micro"},
                "us-west-2": {"AMI": "ami-87654321", "InstanceType": "t2.small"},
            },
            "EnvironmentMap": {"prod": {"Size": "large", "Count": 5}, "dev": {"Size": "small", "Count": 1}},
        }

    @pytest.fixture
    def context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnFindInMapResolver:
        """Create a FnFindInMapResolver for testing."""
        return FnFindInMapResolver(context, None)

    def test_basic_map_lookup(self, resolver: FnFindInMapResolver):
        """Test basic Fn::FindInMap lookup returns correct value.

        Requirement 5.1: Return the corresponding value from the Mappings section
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}
        result = resolver.resolve(value)
        assert result == "ami-12345678"

    def test_lookup_different_keys(self, resolver: FnFindInMapResolver):
        """Test Fn::FindInMap with different keys.

        Requirement 5.1: Return the corresponding value from the Mappings section
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-west-2", "InstanceType"]}
        result = resolver.resolve(value)
        assert result == "t2.small"

    def test_lookup_different_map(self, resolver: FnFindInMapResolver):
        """Test Fn::FindInMap with different map.

        Requirement 5.1: Return the corresponding value from the Mappings section
        """
        value = {"Fn::FindInMap": ["EnvironmentMap", "prod", "Size"]}
        result = resolver.resolve(value)
        assert result == "large"

    def test_lookup_returns_integer(self, resolver: FnFindInMapResolver):
        """Test Fn::FindInMap can return integer values.

        Requirement 5.1: Return the corresponding value from the Mappings section
        """
        value = {"Fn::FindInMap": ["EnvironmentMap", "prod", "Count"]}
        result = resolver.resolve(value)
        assert result == 5


# =============================================================================
# Unit Tests for DefaultValue Fallback
# =============================================================================


class TestFnFindInMapResolverDefaultValue:
    """Tests for Fn::FindInMap DefaultValue fallback.

    Requirement 5.2: WHEN Fn::FindInMap includes a DefaultValue option and the
    top-level key is not found, THEN THE Resolver SHALL return the default value

    Requirement 5.3: WHEN Fn::FindInMap includes a DefaultValue option and the
    second-level key is not found, THEN THE Resolver SHALL return the default value
    """

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}}

    @pytest.fixture
    def context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnFindInMapResolver:
        """Create a FnFindInMapResolver for testing."""
        return FnFindInMapResolver(context, None)

    def test_default_value_when_map_not_found(self, resolver: FnFindInMapResolver):
        """Test DefaultValue returned when map name not found.

        Requirement 5.2: Return default value when top-level key not found
        """
        value = {"Fn::FindInMap": ["NonExistentMap", "key1", "key2", {"DefaultValue": "fallback-value"}]}
        result = resolver.resolve(value)
        assert result == "fallback-value"

    def test_default_value_when_top_level_key_not_found(self, resolver: FnFindInMapResolver):
        """Test DefaultValue returned when top-level key not found.

        Requirement 5.2: Return default value when top-level key not found
        """
        value = {"Fn::FindInMap": ["RegionMap", "invalid-region", "AMI", {"DefaultValue": "ami-default"}]}
        result = resolver.resolve(value)
        assert result == "ami-default"

    def test_default_value_when_second_level_key_not_found(self, resolver: FnFindInMapResolver):
        """Test DefaultValue returned when second-level key not found.

        Requirement 5.3: Return default value when second-level key not found
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "NonExistentKey", {"DefaultValue": "default-value"}]}
        result = resolver.resolve(value)
        assert result == "default-value"

    def test_default_value_can_be_dict(self, resolver: FnFindInMapResolver):
        """Test DefaultValue can be a dictionary."""
        value = {"Fn::FindInMap": ["RegionMap", "invalid", "key", {"DefaultValue": {"nested": "object"}}]}
        result = resolver.resolve(value)
        assert result == {"nested": "object"}

    def test_default_value_can_be_list(self, resolver: FnFindInMapResolver):
        """Test DefaultValue can be a list."""
        value = {"Fn::FindInMap": ["RegionMap", "invalid", "key", {"DefaultValue": [1, 2, 3]}]}
        result = resolver.resolve(value)
        assert result == [1, 2, 3]

    def test_default_value_can_be_integer(self, resolver: FnFindInMapResolver):
        """Test DefaultValue can be an integer."""
        value = {"Fn::FindInMap": ["RegionMap", "invalid", "key", {"DefaultValue": 42}]}
        result = resolver.resolve(value)
        assert result == 42

    def test_default_value_can_be_null(self, resolver: FnFindInMapResolver):
        """Test DefaultValue can be null."""
        value = {"Fn::FindInMap": ["RegionMap", "invalid", "key", {"DefaultValue": None}]}
        result = resolver.resolve(value)
        assert result is None

    def test_successful_lookup_ignores_default_value(self, resolver: FnFindInMapResolver):
        """Test that successful lookup returns mapped value, not default.

        Requirement 5.1: Return the corresponding value from the Mappings section
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI", {"DefaultValue": "should-not-be-returned"}]}
        result = resolver.resolve(value)
        assert result == "ami-12345678"


# =============================================================================
# Unit Tests for Error Handling
# =============================================================================


class TestFnFindInMapResolverErrorHandling:
    """Tests for Fn::FindInMap error handling.

    Requirement 5.5: WHEN Fn::FindInMap is applied with an invalid layout, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception

    Requirement 5.6: WHEN Fn::FindInMap lookup fails without a DefaultValue, THEN THE
    Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}}

    @pytest.fixture
    def context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnFindInMapResolver:
        """Create a FnFindInMapResolver for testing."""
        return FnFindInMapResolver(context, None)

    def test_invalid_layout_not_a_list(self, resolver: FnFindInMapResolver):
        """Test error when argument is not a list.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::FindInMap": "not-a-list"}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_invalid_layout_too_few_elements(self, resolver: FnFindInMapResolver):
        """Test error when list has fewer than 3 elements.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::FindInMap": ["MapName", "TopKey"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_invalid_layout_empty_list(self, resolver: FnFindInMapResolver):
        """Test error when list is empty.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value: Dict[str, Any] = {"Fn::FindInMap": []}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_map_not_found_without_default(self, resolver: FnFindInMapResolver):
        """Test error when map not found and no DefaultValue.

        Requirement 5.6: Raise Invalid_Template_Exception when lookup fails without DefaultValue
        """
        value = {"Fn::FindInMap": ["NonExistentMap", "key1", "key2"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "cannot find map" in str(exc_info.value).lower()

    def test_top_level_key_not_found_without_default(self, resolver: FnFindInMapResolver):
        """Test error when top-level key not found and no DefaultValue.

        Requirement 5.6: Raise Invalid_Template_Exception when lookup fails without DefaultValue
        """
        value = {"Fn::FindInMap": ["RegionMap", "invalid-region", "AMI"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "cannot find key" in str(exc_info.value).lower()

    def test_second_level_key_not_found_without_default(self, resolver: FnFindInMapResolver):
        """Test error when second-level key not found and no DefaultValue.

        Requirement 5.6: Raise Invalid_Template_Exception when lookup fails without DefaultValue
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "NonExistentKey"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "cannot find key" in str(exc_info.value).lower()

    def test_non_string_map_name_raises_exception(self, resolver: FnFindInMapResolver):
        """Test error when map name is not a string.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::FindInMap": [123, "TopKey", "SecondKey"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_non_string_top_key_raises_exception(self, resolver: FnFindInMapResolver):
        """Test error when top-level key is not a string.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::FindInMap": ["RegionMap", 123, "SecondKey"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_non_string_second_key_raises_exception(self, resolver: FnFindInMapResolver):
        """Test error when second-level key is not a string.

        Requirement 5.5: Raise Invalid_Template_Exception for invalid layout
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", 123]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)


# =============================================================================
# Unit Tests for Nested Intrinsic Resolution
# =============================================================================


class TestFnFindInMapResolverNestedIntrinsics:
    """Tests for Fn::FindInMap with nested intrinsic functions.

    Requirement 5.4: WHEN Fn::FindInMap keys contain nested intrinsic functions
    (Fn::Select, Fn::Split, Fn::If, Fn::Join, Fn::Sub), THEN THE Resolver SHALL
    resolve those intrinsics before performing the lookup
    """

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {
            "RegionMap": {
                "us-east-1": {"AMI": "ami-12345678", "InstanceType": "t2.micro"},
                "us-west-2": {"AMI": "ami-87654321", "InstanceType": "t2.small"},
            }
        }

    @pytest.fixture
    def context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with mappings and parameters."""
        ctx = TemplateProcessingContext(
            fragment={"Resources": {}, "Mappings": mappings},
            parameter_values={"Region": "us-east-1", "MapName": "RegionMap", "KeyName": "AMI"},
        )
        ctx.parsed_template = ParsedTemplate(
            resources={},
            mappings=mappings,
            parameters={"Region": {"Type": "String"}, "MapName": {"Type": "String"}, "KeyName": {"Type": "String"}},
        )
        return ctx

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnFindInMapResolver and mock resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnFindInMapResolver)
        orchestrator.register_resolver(MockRefResolver)
        orchestrator.register_resolver(MockSelectResolver)
        orchestrator.register_resolver(MockSplitResolver)
        return orchestrator

    def test_ref_in_map_name(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Ref in map name.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": [{"Ref": "MapName"}, "us-east-1", "AMI"]}
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_ref_in_top_level_key(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Ref in top-level key.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": ["RegionMap", {"Ref": "Region"}, "AMI"]}
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_ref_in_second_level_key(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Ref in second-level key.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", {"Ref": "KeyName"}]}
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_ref_in_all_keys(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Ref in all keys.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": [{"Ref": "MapName"}, {"Ref": "Region"}, {"Ref": "KeyName"}]}
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_fn_select_in_key(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Fn::Select in key.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": ["RegionMap", {"Fn::Select": [0, ["us-east-1", "us-west-2"]]}, "AMI"]}
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_fn_split_with_fn_select_in_key(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with Fn::Split and Fn::Select in key.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {
            "Fn::FindInMap": ["RegionMap", {"Fn::Select": [1, {"Fn::Split": [",", "us-west-2,us-east-1"]}]}, "AMI"]
        }
        result = orchestrator.resolve_value(value)
        assert result == "ami-12345678"

    def test_nested_intrinsic_in_default_value(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with nested intrinsic in DefaultValue.

        Requirement 5.4: Resolve nested intrinsics before lookup
        """
        value = {"Fn::FindInMap": ["RegionMap", "invalid-region", "AMI", {"DefaultValue": {"Ref": "Region"}}]}
        result = orchestrator.resolve_value(value)
        # DefaultValue is {"Ref": "Region"} which resolves to "us-east-1"
        assert result == "us-east-1"


# =============================================================================
# Unit Tests for Integration with IntrinsicResolver Orchestrator
# =============================================================================


class TestFnFindInMapResolverWithOrchestrator:
    """Tests for FnFindInMapResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}, "us-west-2": {"AMI": "ami-87654321"}}}

    @pytest.fixture
    def context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnFindInMapResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnFindInMapResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::FindInMap through the orchestrator."""
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}
        result = orchestrator.resolve_value(value)

        assert result == "ami-12345678"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::FindInMap in a nested template structure."""
        value = {
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {"ImageId": {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyInstance"]["Properties"]["ImageId"] == "ami-12345678"

    def test_resolve_multiple_fn_find_in_map(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::FindInMap in same structure."""
        value = {
            "first": {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]},
            "second": {"Fn::FindInMap": ["RegionMap", "us-west-2", "AMI"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "first": "ami-12345678",
            "second": "ami-87654321",
        }

    def test_fn_find_in_map_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap inside a list."""
        value = [
            {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]},
            {"Fn::FindInMap": ["RegionMap", "us-west-2", "AMI"]},
        ]
        result = orchestrator.resolve_value(value)

        assert result == ["ami-12345678", "ami-87654321"]


# =============================================================================
# Unit Tests for Partial Resolution Mode
# =============================================================================


class TestFnFindInMapResolverPartialMode:
    """Tests for FnFindInMapResolver in partial resolution mode.

    Fn::FindInMap should always be resolved, even in partial mode.
    """

    @pytest.fixture
    def mappings(self) -> Dict[str, Any]:
        """Create sample mappings for testing."""
        return {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}}

    @pytest.fixture
    def partial_context(self, mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        ctx = TemplateProcessingContext(
            fragment={"Resources": {}, "Mappings": mappings},
            resolution_mode=ResolutionMode.PARTIAL,
        )
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnFindInMapResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnFindInMapResolver)
        return orchestrator

    def test_fn_find_in_map_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::FindInMap is resolved even in partial mode.

        Requirement 16.4: In partial mode, still resolve Fn::FindInMap
        """
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}
        result = orchestrator.resolve_value(value)

        assert result == "ami-12345678"

    def test_fn_find_in_map_with_default_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap with DefaultValue in partial mode."""
        value = {"Fn::FindInMap": ["RegionMap", "invalid-region", "AMI", {"DefaultValue": "ami-default"}]}
        result = orchestrator.resolve_value(value)

        assert result == "ami-default"

    def test_fn_find_in_map_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::FindInMap alongside preserved intrinsics in partial mode."""
        value = {
            "ami": {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "ami": "ami-12345678",
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


# =============================================================================
# Unit Tests for Edge Cases
# =============================================================================


class TestFnFindInMapResolverEdgeCases:
    """Tests for Fn::FindInMap edge cases."""

    @pytest.fixture
    def context_with_empty_mappings(self) -> TemplateProcessingContext:
        """Create a context with empty mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": {}})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings={})
        return ctx

    @pytest.fixture
    def context_without_parsed_template(self) -> TemplateProcessingContext:
        """Create a context without parsed template (uses fragment)."""
        return TemplateProcessingContext(
            fragment={"Resources": {}, "Mappings": {"TestMap": {"key1": {"key2": "value"}}}}
        )

    def test_empty_mappings_with_default(self, context_with_empty_mappings: TemplateProcessingContext):
        """Test Fn::FindInMap with empty mappings returns DefaultValue."""
        resolver = FnFindInMapResolver(context_with_empty_mappings, None)
        value = {"Fn::FindInMap": ["AnyMap", "anyKey", "anyKey2", {"DefaultValue": "fallback"}]}
        result = resolver.resolve(value)
        assert result == "fallback"

    def test_empty_mappings_without_default_raises(self, context_with_empty_mappings: TemplateProcessingContext):
        """Test Fn::FindInMap with empty mappings raises without DefaultValue."""
        resolver = FnFindInMapResolver(context_with_empty_mappings, None)
        value = {"Fn::FindInMap": ["AnyMap", "anyKey", "anyKey2"]}

        with pytest.raises(InvalidTemplateException):
            resolver.resolve(value)

    def test_uses_fragment_when_no_parsed_template(self, context_without_parsed_template: TemplateProcessingContext):
        """Test Fn::FindInMap uses fragment when parsed_template is None."""
        resolver = FnFindInMapResolver(context_without_parsed_template, None)
        value = {"Fn::FindInMap": ["TestMap", "key1", "key2"]}
        result = resolver.resolve(value)
        assert result == "value"

    def test_map_value_can_be_complex_object(self):
        """Test Fn::FindInMap can return complex objects."""
        mappings = {"ComplexMap": {"key1": {"key2": {"nested": {"deeply": "nested"}, "list": [1, 2, 3]}}}}
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)

        resolver = FnFindInMapResolver(ctx, None)
        value = {"Fn::FindInMap": ["ComplexMap", "key1", "key2"]}
        result = resolver.resolve(value)

        assert result == {"nested": {"deeply": "nested"}, "list": [1, 2, 3]}

    def test_fourth_argument_invalid_type_raises(self):
        """Test that invalid 4th argument type raises exception."""
        mappings = {"TestMap": {"key1": {"key2": "value"}}}
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)

        resolver = FnFindInMapResolver(ctx, None)
        # 4th argument is a string instead of dict with DefaultValue
        value = {"Fn::FindInMap": ["TestMap", "key1", "key2", "invalid"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::FindInMap layout is incorrect" in str(exc_info.value)

    def test_fourth_argument_dict_without_default_value_is_valid(self):
        """Test that 4th argument dict without DefaultValue key is treated as no default.

        When the 4th argument is a dict but doesn't contain "DefaultValue" key,
        it's treated as if no default was provided. The lookup proceeds normally
        and fails if the key is not found.
        """
        mappings = {"TestMap": {"key1": {"key2": "value"}}}
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)

        resolver = FnFindInMapResolver(ctx, None)
        # 4th argument is a dict but without DefaultValue key - treated as no default
        value = {"Fn::FindInMap": ["TestMap", "invalid", "key2", {"SomeOtherKey": "value"}]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        # Should fail because lookup fails and no DefaultValue was provided
        assert "cannot find key" in str(exc_info.value).lower()


# =============================================================================
# Property-Based Tests for Fn::FindInMap Default Value Fallback
# =============================================================================


# =============================================================================
# Parametrized Tests for Fn::FindInMap Default Value Fallback
# =============================================================================


class TestFnFindInMapDefaultValueFallbackPropertyTests:
    """
    Parametrized tests for Fn::FindInMap Default Value Fallback.

    Feature: cfn-language-extensions-python, Property 7: Fn::FindInMap Default Value Fallback

    These tests validate that for any Fn::FindInMap with a DefaultValue option
    where either the top-level key or second-level key is not found in the mappings,
    the resolver SHALL return the default value.

    **Validates: Requirements 5.2, 5.3**
    """

    @staticmethod
    def _create_context_with_mappings(mappings: Dict[str, Any]) -> TemplateProcessingContext:
        """Create a template processing context with the given mappings."""
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings)
        return ctx

    @staticmethod
    def _create_orchestrator(context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnFindInMapResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnFindInMapResolver)
        return orchestrator

    @pytest.mark.parametrize(
        "existing_map_name, existing_top_key, existing_second_key, existing_value, nonexistent_map_name, default_value",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "MissingMap", "fallback-ami"),
            ("EnvConfig", "prod", "Size", "large", "OtherConfig", 42),
            ("Settings", "alpha", "key1", "val1", "NoSuchMap", None),
        ],
    )
    def test_default_value_returned_when_map_not_found(
        self,
        existing_map_name,
        existing_top_key,
        existing_second_key,
        existing_value,
        nonexistent_map_name,
        default_value,
    ):
        """
        Property 7: For any Fn::FindInMap with a DefaultValue option where the map name
        is not found, the resolver SHALL return the default value.

        **Validates: Requirements 5.2**
        """
        mappings = {existing_map_name: {existing_top_key: {existing_second_key: existing_value}}}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {
            "Fn::FindInMap": [
                nonexistent_map_name,
                existing_top_key,
                existing_second_key,
                {"DefaultValue": default_value},
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, existing_top_key, existing_second_key, existing_value, nonexistent_top_key, default_value",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "eu-west-1", "ami-default"),
            ("EnvConfig", "prod", "Size", "large", "staging", {"nested": "default"}),
            ("Settings", "alpha", "key1", "val1", "beta", [1, 2, 3]),
        ],
    )
    def test_default_value_returned_when_top_level_key_not_found(
        self, map_name, existing_top_key, existing_second_key, existing_value, nonexistent_top_key, default_value
    ):
        """
        Property 7: For any Fn::FindInMap with a DefaultValue option where the top-level
        key is not found, the resolver SHALL return the default value.

        **Validates: Requirements 5.2**
        """
        mappings = {map_name: {existing_top_key: {existing_second_key: existing_value}}}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, nonexistent_top_key, existing_second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, top_key, existing_second_key, existing_value, nonexistent_second_key, default_value",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "InstanceType", "t2.micro"),
            ("EnvConfig", "prod", "Size", "large", "Color", None),
            ("Settings", "alpha", "key1", "val1", "key2", True),
        ],
    )
    def test_default_value_returned_when_second_level_key_not_found(
        self, map_name, top_key, existing_second_key, existing_value, nonexistent_second_key, default_value
    ):
        """
        Property 7: For any Fn::FindInMap with a DefaultValue option where the second-level
        key is not found, the resolver SHALL return the default value.

        **Validates: Requirements 5.3**
        """
        mappings = {map_name: {top_key: {existing_second_key: existing_value}}}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, nonexistent_second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, default_value",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "should-not-return"),
            ("EnvConfig", "prod", "Size", "large", 999),
            ("Settings", "alpha", "key1", "val1", None),
        ],
    )
    def test_mapped_value_returned_when_all_keys_found(
        self, map_name, top_key, second_key, mapped_value, default_value
    ):
        """
        Property 7: For any Fn::FindInMap with a DefaultValue option where all keys
        are found, the resolver SHALL return the mapped value, NOT the default.

        **Validates: Requirements 5.1**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "default_value",
        [
            "string-default",
            42,
            {"nested": "dict", "key": "value"},
            [1, 2, 3],
            None,
        ],
    )
    def test_default_value_supports_various_types(self, default_value):
        """
        Property 7: The default value can be of any JSON-compatible type.

        **Validates: Requirements 5.2, 5.3**
        """
        mappings: Dict[str, Any] = {}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": ["NonExistentMap", "key1", "key2", {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, default_value",
        [
            ("MyMap", "topKey", "secondKey", "fallback"),
            ("Config", "env", "setting", 0),
            ("Data", "region", "value", {"a": 1}),
        ],
    )
    def test_default_value_with_empty_mappings(self, map_name, top_key, second_key, default_value):
        """
        Property 7: When the Mappings section is empty, the resolver SHALL return
        the default value.

        **Validates: Requirements 5.2**
        """
        mappings: Dict[str, Any] = {}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value",
        [
            ("Config", "env", "settings", {"nested": {"deep": "value"}}),
            ("Data", "region", "list", [1, "two", True]),
            ("Simple", "k1", "k2", "plain-string"),
        ],
    )
    def test_complex_mapped_values_returned_correctly(self, map_name, top_key, second_key, mapped_value):
        """
        Property 7: Complex mapped values (dicts, lists) are returned correctly.

        **Validates: Requirements 5.1**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, second_key]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_keys, second_keys, default_value",
        [
            ("Config", ["prod", "dev"], ["size", "count"], "default-val"),
            ("RegionMap", ["us-east-1", "eu-west-1", "ap-south-1"], ["AMI", "Type"], None),
        ],
    )
    def test_default_value_with_multiple_keys_in_map(self, map_name, top_keys, second_keys, default_value):
        """
        Property 7: When the map has multiple keys but the requested key is not found,
        the resolver SHALL return the default value.

        **Validates: Requirements 5.2, 5.3**
        """
        mappings = {
            map_name: {
                top_key: {second_key: f"value_{top_key}_{second_key}" for second_key in second_keys}
                for top_key in top_keys
            }
        }
        context = self._create_context_with_mappings(mappings)
        orchestrator = self._create_orchestrator(context)

        nonexistent_top_key = "nonexistent_" + top_keys[0]
        value = {"Fn::FindInMap": [map_name, nonexistent_top_key, second_keys[0], {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value


# =============================================================================
# Parametrized Tests for Fn::FindInMap Key Resolution
# =============================================================================


class TestFnFindInMapKeyResolutionPropertyTests:
    """
    Parametrized tests for Fn::FindInMap Key Resolution.

    Feature: cfn-language-extensions-python, Property 8: Fn::FindInMap Key Resolution

    These tests validate that for any Fn::FindInMap where keys contain nested
    intrinsic functions, the resolver SHALL resolve those intrinsics before
    performing the map lookup.

    **Validates: Requirements 5.4**
    """

    @staticmethod
    def _create_context_with_mappings_and_params(
        mappings: Dict[str, Any],
        parameter_values: Optional[Dict[str, Any]] = None,
    ) -> TemplateProcessingContext:
        """Create a template processing context with mappings and parameters."""
        ctx = TemplateProcessingContext(
            fragment={"Resources": {}, "Mappings": mappings},
            parameter_values=parameter_values or {},
        )
        ctx.parsed_template = ParsedTemplate(
            resources={},
            mappings=mappings,
            parameters={k: {"Type": "String"} for k in (parameter_values or {}).keys()},
        )
        return ctx

    @staticmethod
    def _create_orchestrator(context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnFindInMapResolver and mock resolvers."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnFindInMapResolver)
        orchestrator.register_resolver(MockRefResolver)
        orchestrator.register_resolver(MockSelectResolver)
        orchestrator.register_resolver(MockSplitResolver)
        return orchestrator

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, param_name",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "MapParam"),
            ("EnvConfig", "prod", "Size", "large", "ConfigName"),
            ("Settings", "alpha", "key1", "val1", "SettingsMap"),
        ],
    )
    def test_ref_in_map_name_is_resolved_before_lookup(self, map_name, top_key, second_key, mapped_value, param_name):
        """
        Property 8: When the map name contains a Ref, the resolver SHALL resolve
        the Ref before performing the map lookup.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        parameter_values = {param_name: map_name}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [{"Ref": param_name}, top_key, second_key]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, param_name",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "Region"),
            ("EnvConfig", "prod", "Size", "large", "Environment"),
            ("Settings", "alpha", "key1", "val1", "Level"),
        ],
    )
    def test_ref_in_top_level_key_is_resolved_before_lookup(
        self, map_name, top_key, second_key, mapped_value, param_name
    ):
        """
        Property 8: When the top-level key contains a Ref, the resolver SHALL
        resolve the Ref before performing the lookup.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        parameter_values = {param_name: top_key}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, {"Ref": param_name}, second_key]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, param_name",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "KeyName"),
            ("EnvConfig", "prod", "Size", "large", "Property"),
            ("Settings", "alpha", "key1", "val1", "Field"),
        ],
    )
    def test_ref_in_second_level_key_is_resolved_before_lookup(
        self, map_name, top_key, second_key, mapped_value, param_name
    ):
        """
        Property 8: When the second-level key contains a Ref, the resolver SHALL
        resolve the Ref before performing the lookup.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        parameter_values = {param_name: second_key}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, {"Ref": param_name}]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, map_param, top_param, second_param",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "MapP", "TopP", "SecondP"),
            ("EnvConfig", "prod", "Size", "large", "CfgName", "EnvName", "PropName"),
        ],
    )
    def test_ref_in_all_keys_is_resolved_before_lookup(
        self, map_name, top_key, second_key, mapped_value, map_param, top_param, second_param
    ):
        """
        Property 8: When all keys contain Ref intrinsics, the resolver SHALL
        resolve all Refs before performing the map lookup.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        parameter_values = {map_param: map_name, top_param: top_key, second_param: second_key}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [{"Ref": map_param}, {"Ref": top_param}, {"Ref": second_param}]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_keys, second_key, mapped_value, select_index",
        [
            ("RegionMap", ["us-east-1", "us-west-2", "eu-west-1"], "AMI", "ami-selected", 0),
            ("Config", ["prod", "dev"], "Size", "large", 1),
        ],
    )
    def test_fn_select_in_top_level_key_is_resolved_before_lookup(
        self, map_name, top_keys, second_key, mapped_value, select_index
    ):
        """
        Property 8: When the top-level key contains Fn::Select, the resolver
        SHALL resolve it before lookup.

        **Validates: Requirements 5.4**
        """
        selected_top_key = top_keys[select_index]
        mappings = {map_name: {top_key: {second_key: f"value_for_{top_key}"} for top_key in top_keys}}
        mappings[map_name][selected_top_key][second_key] = mapped_value

        context = self._create_context_with_mappings_and_params(mappings, {})
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, {"Fn::Select": [select_index, top_keys]}, second_key]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_keys, mapped_value, select_index",
        [
            ("RegionMap", "us-east-1", ["AMI", "Type", "Size"], "ami-12345", 0),
            ("Config", "prod", ["key1", "key2"], "selected-val", 1),
        ],
    )
    def test_fn_select_in_second_level_key_is_resolved_before_lookup(
        self, map_name, top_key, second_keys, mapped_value, select_index
    ):
        """
        Property 8: When the second-level key contains Fn::Select, the resolver
        SHALL resolve it before lookup.

        **Validates: Requirements 5.4**
        """
        selected_second_key = second_keys[select_index]
        mappings = {map_name: {top_key: {sk: f"value_for_{sk}" for sk in second_keys}}}
        mappings[map_name][top_key][selected_second_key] = mapped_value

        context = self._create_context_with_mappings_and_params(mappings, {})
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, top_key, {"Fn::Select": [select_index, second_keys]}]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, delimiter",
        [
            ("RegionMap", "useast1", "AMI", "ami-12345", ","),
            ("Config", "prod", "Size", "large", ":"),
            ("Settings", "alpha", "key1", "val1", "/"),
        ],
    )
    def test_fn_split_with_fn_select_in_key_is_resolved_before_lookup(
        self, map_name, top_key, second_key, mapped_value, delimiter
    ):
        """
        Property 8: When a key contains nested Fn::Split and Fn::Select, the
        resolver SHALL resolve both before lookup.

        **Validates: Requirements 5.4**
        """
        delimited_string = delimiter.join(["other1", top_key, "other2"])
        mappings = {map_name: {top_key: {second_key: mapped_value}}}

        context = self._create_context_with_mappings_and_params(mappings, {})
        orchestrator = self._create_orchestrator(context)

        value = {
            "Fn::FindInMap": [map_name, {"Fn::Select": [1, {"Fn::Split": [delimiter, delimited_string]}]}, second_key]
        }
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, default_value, param_name",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "ami-default", "Region"),
            ("Config", "prod", "Size", "large", "small", "Env"),
        ],
    )
    def test_ref_in_key_with_default_value_resolves_correctly(
        self, map_name, top_key, second_key, mapped_value, default_value, param_name
    ):
        """
        Property 8: When keys have nested intrinsics AND a DefaultValue is provided,
        the resolver SHALL resolve intrinsics and return the mapped value.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {top_key: {second_key: mapped_value}}}
        parameter_values = {param_name: top_key}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, {"Ref": param_name}, second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == mapped_value

    @pytest.mark.parametrize(
        "map_name, existing_top_key, second_key, mapped_value, default_value, nonexistent_key, param_name",
        [
            ("RegionMap", "us-east-1", "AMI", "ami-12345", "ami-default", "eu-west-1", "Region"),
            ("Config", "prod", "Size", "large", "medium", "staging", "Env"),
        ],
    )
    def test_ref_resolving_to_nonexistent_key_returns_default(
        self, map_name, existing_top_key, second_key, mapped_value, default_value, nonexistent_key, param_name
    ):
        """
        Property 8: When a Ref in a key resolves to a non-existent key and a
        DefaultValue is provided, the resolver SHALL return the default value.

        **Validates: Requirements 5.4**
        """
        mappings = {map_name: {existing_top_key: {second_key: mapped_value}}}
        parameter_values = {param_name: nonexistent_key}
        context = self._create_context_with_mappings_and_params(mappings, parameter_values)
        orchestrator = self._create_orchestrator(context)

        value = {"Fn::FindInMap": [map_name, {"Ref": param_name}, second_key, {"DefaultValue": default_value}]}
        result = orchestrator.resolve_value(value)
        assert result == default_value

    @pytest.mark.parametrize(
        "map_name, top_key, second_key, mapped_value, delimiter",
        [
            ("RegionMap", "useast1", "AMI", "ami-12345", ","),
            ("Config", "prod", "Size", "large", "/"),
        ],
    )
    def test_multiple_nested_intrinsics_in_different_keys(self, map_name, top_key, second_key, mapped_value, delimiter):
        """
        Property 8: When different keys contain different nested intrinsic functions,
        the resolver SHALL resolve all of them correctly.

        **Validates: Requirements 5.4**
        """
        second_keys = [second_key, "other1", "other2"]
        delimited_string = delimiter.join(["prefix", top_key, "suffix"])
        mappings = {map_name: {top_key: {second_key: mapped_value}}}

        context = self._create_context_with_mappings_and_params(mappings, {})
        orchestrator = self._create_orchestrator(context)

        value = {
            "Fn::FindInMap": [
                map_name,
                {"Fn::Select": [1, {"Fn::Split": [delimiter, delimited_string]}]},
                {"Fn::Select": [0, second_keys]},
            ]
        }
        result = orchestrator.resolve_value(value)
        assert result == mapped_value


class TestFnFindInMapWithDefaultValueIntegration:
    """
    Unit tests for Fn::FindInMap with DefaultValue integration scenarios.

    These tests validate the integration of Fn::FindInMap with DefaultValue
    in various SAM CLI scenarios including sam validate and sam build.

    **Validates: Requirements 5A.1, 5A.2, 5A.3, 5A.4**
    """

    def test_map_lookup_returns_value_when_key_exists(self):
        """
        Test that Fn::FindInMap returns the mapped value when the key exists.

        **Validates: Requirements 5A.1**

        WHEN a template uses Fn::FindInMap with a DefaultValue option,
        THE SAM_CLI SHALL return the mapped value if the key exists.
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "RegionConfig": {
                    "us-east-1": {"InstanceType": "t2.micro", "AMI": "ami-12345"},
                    "us-west-2": {"InstanceType": "t2.small", "AMI": "ami-67890"},
                }
            },
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        "InstanceType": {
                            "Fn::FindInMap": [
                                "RegionConfig",
                                "us-east-1",
                                "InstanceType",
                                {"DefaultValue": "t2.nano"},
                            ]
                        }
                    },
                }
            },
        }

        result = process_template(template)

        # Should return the mapped value, not the default
        assert result["Resources"]["MyInstance"]["Properties"]["InstanceType"] == "t2.micro"

    def test_map_lookup_returns_default_value_when_key_does_not_exist(self):
        """
        Test that Fn::FindInMap returns DefaultValue when the key does not exist.

        **Validates: Requirements 5A.2**

        WHEN a template uses Fn::FindInMap with a DefaultValue option and the key
        does NOT exist, THE SAM_CLI SHALL return the DefaultValue.
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "RegionConfig": {
                    "us-east-1": {"InstanceType": "t2.micro"},
                }
            },
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        # Region eu-west-1 does not exist in mappings
                        "InstanceType": {
                            "Fn::FindInMap": [
                                "RegionConfig",
                                "eu-west-1",
                                "InstanceType",
                                {"DefaultValue": "t2.nano"},
                            ]
                        }
                    },
                }
            },
        }

        result = process_template(template)

        # Should return the default value since eu-west-1 doesn't exist
        assert result["Resources"]["MyInstance"]["Properties"]["InstanceType"] == "t2.nano"

    def test_map_lookup_returns_default_when_second_level_key_missing(self):
        """
        Test that Fn::FindInMap returns DefaultValue when second-level key is missing.

        **Validates: Requirements 5A.2**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "RegionConfig": {
                    "us-east-1": {"InstanceType": "t2.micro"},
                    # AMI key is missing for us-east-1
                }
            },
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        "ImageId": {
                            "Fn::FindInMap": [
                                "RegionConfig",
                                "us-east-1",
                                "AMI",  # This key doesn't exist
                                {"DefaultValue": "ami-default"},
                            ]
                        }
                    },
                }
            },
        }

        result = process_template(template)

        # Should return the default value since AMI key doesn't exist
        assert result["Resources"]["MyInstance"]["Properties"]["ImageId"] == "ami-default"

    def test_validate_accepts_valid_find_in_map_with_default_value(self):
        """
        Test that sam validate accepts templates with valid Fn::FindInMap with DefaultValue.

        **Validates: Requirements 5A.3**

        WHEN sam validate processes a template with valid Fn::FindInMap with
        DefaultValue syntax, THE Validate_Command SHALL report the template as valid.
        """
        from samcli.lib.cfn_language_extensions import process_template

        # This template should be valid and process without errors
        template = {
            "Mappings": {
                "EnvConfig": {
                    "prod": {"LogLevel": "ERROR"},
                    "dev": {"LogLevel": "DEBUG"},
                }
            },
            "Parameters": {
                "Environment": {"Type": "String", "Default": "dev"},
            },
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Runtime": "python3.9",
                        "Handler": "index.handler",
                        "Code": {"ZipFile": "def handler(event, context): pass"},
                        "Environment": {
                            "Variables": {
                                "LOG_LEVEL": {
                                    "Fn::FindInMap": [
                                        "EnvConfig",
                                        {"Ref": "Environment"},
                                        "LogLevel",
                                        {"DefaultValue": "INFO"},
                                    ]
                                }
                            }
                        },
                    },
                }
            },
        }

        # Should process without raising an exception
        result = process_template(template)

        # Verify the template was processed correctly
        assert "MyFunction" in result["Resources"]
        assert result["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]["LOG_LEVEL"] == "DEBUG"

    def test_build_correctly_resolves_find_in_map_with_default_value(self):
        """
        Test that sam build correctly resolves Fn::FindInMap with DefaultValue.

        **Validates: Requirements 5A.4**

        WHEN sam build processes a template using Fn::FindInMap with DefaultValue,
        THE Build_Command SHALL correctly resolve the map lookup.
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "RuntimeConfig": {
                    "python": {"Runtime": "python3.9", "Handler": "app.handler"},
                    "nodejs": {"Runtime": "nodejs18.x", "Handler": "index.handler"},
                }
            },
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Runtime": {
                            "Fn::FindInMap": [
                                "RuntimeConfig",
                                "python",
                                "Runtime",
                                {"DefaultValue": "python3.8"},
                            ]
                        },
                        "Handler": {
                            "Fn::FindInMap": [
                                "RuntimeConfig",
                                "python",
                                "Handler",
                                {"DefaultValue": "handler.main"},
                            ]
                        },
                    },
                }
            },
        }

        result = process_template(template)

        # Verify the map lookups were resolved correctly
        assert result["Resources"]["MyFunction"]["Properties"]["Runtime"] == "python3.9"
        assert result["Resources"]["MyFunction"]["Properties"]["Handler"] == "app.handler"

    def test_default_value_with_complex_types(self):
        """
        Test that Fn::FindInMap DefaultValue works with complex types (dict, list).

        **Validates: Requirements 5A.2**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "Config": {
                    "existing": {"Tags": {"Environment": "prod"}},
                }
            },
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "Tags": {
                            "Fn::FindInMap": [
                                "Config",
                                "nonexistent",
                                "Tags",
                                {"DefaultValue": {"Environment": "default", "Project": "test"}},
                            ]
                        }
                    },
                }
            },
        }

        result = process_template(template)

        # Should return the complex default value
        assert result["Resources"]["MyBucket"]["Properties"]["Tags"] == {
            "Environment": "default",
            "Project": "test",
        }


# =============================================================================
# Unit Tests for Fn::ForEach with Fn::FindInMap Integration
# =============================================================================


class TestFnForEachWithFnFindInMapIntegration:
    """
    Unit tests for Fn::ForEach integration with Fn::FindInMap.

    These tests validate that Fn::FindInMap works correctly within Fn::ForEach
    loops, including scenarios where the loop variable is used in the map lookup.

    **Validates: Requirements 5A.1, 5A.2, 5A.3, 5A.4**
    """

    def test_foreach_with_find_in_map_using_loop_variable(self):
        """
        Test Fn::ForEach with Fn::FindInMap using the loop variable as a key.

        This tests the integration where Fn::ForEach generates resources and
        Fn::FindInMap uses the loop variable to look up configuration.

        **Validates: Requirements 5A.1, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "FunctionConfig": {
                    "Alpha": {"Runtime": "python3.9", "Memory": "128"},
                    "Beta": {"Runtime": "nodejs18.x", "Memory": "256"},
                    "Gamma": {"Runtime": "python3.11", "Memory": "512"},
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    ["Alpha", "Beta", "Gamma"],
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Lambda::Function",
                            "Properties": {
                                "FunctionName": {"Fn::Sub": "${FunctionName}-handler"},
                                "Runtime": {"Fn::FindInMap": ["FunctionConfig", "${FunctionName}", "Runtime"]},
                                "MemorySize": {"Fn::FindInMap": ["FunctionConfig", "${FunctionName}", "Memory"]},
                                "Handler": "index.handler",
                                "Code": {"ZipFile": "def handler(event, context): pass"},
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "AlphaFunction" in result["Resources"]
        assert "BetaFunction" in result["Resources"]
        assert "GammaFunction" in result["Resources"]
        assert "Fn::ForEach::Functions" not in result["Resources"]

        # Verify Fn::FindInMap resolved correctly for each function
        assert result["Resources"]["AlphaFunction"]["Properties"]["Runtime"] == "python3.9"
        assert result["Resources"]["AlphaFunction"]["Properties"]["MemorySize"] == "128"

        assert result["Resources"]["BetaFunction"]["Properties"]["Runtime"] == "nodejs18.x"
        assert result["Resources"]["BetaFunction"]["Properties"]["MemorySize"] == "256"

        assert result["Resources"]["GammaFunction"]["Properties"]["Runtime"] == "python3.11"
        assert result["Resources"]["GammaFunction"]["Properties"]["MemorySize"] == "512"

    def test_foreach_with_find_in_map_default_value(self):
        """
        Test Fn::ForEach with Fn::FindInMap using DefaultValue for missing keys.

        This tests the scenario where some loop values don't have corresponding
        entries in the mappings, and DefaultValue is used as a fallback.

        **Validates: Requirements 5A.2, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "FunctionConfig": {
                    # Only Alpha and Beta have configurations
                    "Alpha": {"Timeout": "30"},
                    "Beta": {"Timeout": "60"},
                    # Gamma is missing - will use DefaultValue
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta", "Gamma"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Lambda::Function",
                            "Properties": {
                                "FunctionName": {"Fn::Sub": "${Name}-function"},
                                "Timeout": {
                                    "Fn::FindInMap": [
                                        "FunctionConfig",
                                        "${Name}",
                                        "Timeout",
                                        {"DefaultValue": "120"},  # Default for missing entries
                                    ]
                                },
                                "Runtime": "python3.9",
                                "Handler": "index.handler",
                                "Code": {"ZipFile": "def handler(event, context): pass"},
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "AlphaFunction" in result["Resources"]
        assert "BetaFunction" in result["Resources"]
        assert "GammaFunction" in result["Resources"]

        # Alpha and Beta should use mapped values
        assert result["Resources"]["AlphaFunction"]["Properties"]["Timeout"] == "30"
        assert result["Resources"]["BetaFunction"]["Properties"]["Timeout"] == "60"

        # Gamma should use the DefaultValue since it's not in the mappings
        assert result["Resources"]["GammaFunction"]["Properties"]["Timeout"] == "120"

    def test_foreach_with_nested_find_in_map(self):
        """
        Test Fn::ForEach with nested Fn::FindInMap lookups.

        This tests a more complex scenario where Fn::FindInMap is used
        multiple times within a ForEach loop for different properties.

        **Validates: Requirements 5A.1, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "ServiceConfig": {
                    "Users": {"Port": "8080", "Protocol": "HTTP"},
                    "Orders": {"Port": "8081", "Protocol": "HTTPS"},
                },
                "EnvironmentConfig": {
                    "Users": {"LogLevel": "INFO"},
                    "Orders": {"LogLevel": "DEBUG"},
                },
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "ServiceName",
                    ["Users", "Orders"],
                    {
                        "${ServiceName}Service": {
                            "Type": "AWS::ECS::Service",
                            "Properties": {
                                "ServiceName": {"Fn::Sub": "${ServiceName}-service"},
                                "DesiredCount": 1,
                                "TaskDefinition": {
                                    "Fn::Sub": "arn:aws:ecs:us-east-1:123456789012:task-definition/${ServiceName}"
                                },
                            },
                            "Metadata": {
                                "Port": {"Fn::FindInMap": ["ServiceConfig", "${ServiceName}", "Port"]},
                                "Protocol": {"Fn::FindInMap": ["ServiceConfig", "${ServiceName}", "Protocol"]},
                                "LogLevel": {"Fn::FindInMap": ["EnvironmentConfig", "${ServiceName}", "LogLevel"]},
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "UsersService" in result["Resources"]
        assert "OrdersService" in result["Resources"]

        # Verify multiple Fn::FindInMap lookups resolved correctly
        assert result["Resources"]["UsersService"]["Metadata"]["Port"] == "8080"
        assert result["Resources"]["UsersService"]["Metadata"]["Protocol"] == "HTTP"
        assert result["Resources"]["UsersService"]["Metadata"]["LogLevel"] == "INFO"

        assert result["Resources"]["OrdersService"]["Metadata"]["Port"] == "8081"
        assert result["Resources"]["OrdersService"]["Metadata"]["Protocol"] == "HTTPS"
        assert result["Resources"]["OrdersService"]["Metadata"]["LogLevel"] == "DEBUG"

    def test_foreach_with_find_in_map_and_fn_sub(self):
        """
        Test Fn::ForEach with Fn::FindInMap combined with Fn::Sub.

        This tests the integration where Fn::FindInMap result is used
        within Fn::Sub for string interpolation.

        **Validates: Requirements 5A.1, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "DomainConfig": {
                    "Api": {"Subdomain": "api"},
                    "Web": {"Subdomain": "www"},
                }
            },
            "Resources": {
                "Fn::ForEach::Endpoints": [
                    "EndpointName",
                    ["Api", "Web"],
                    {
                        "${EndpointName}Endpoint": {
                            "Type": "AWS::Route53::RecordSet",
                            "Properties": {
                                "Name": {
                                    "Fn::Sub": [
                                        "${Subdomain}.example.com",
                                        {
                                            "Subdomain": {
                                                "Fn::FindInMap": ["DomainConfig", "${EndpointName}", "Subdomain"]
                                            }
                                        },
                                    ]
                                },
                                "Type": "A",
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "ApiEndpoint" in result["Resources"]
        assert "WebEndpoint" in result["Resources"]

        # Verify Fn::Sub with Fn::FindInMap resolved correctly
        assert result["Resources"]["ApiEndpoint"]["Properties"]["Name"] == "api.example.com"
        assert result["Resources"]["WebEndpoint"]["Properties"]["Name"] == "www.example.com"

    def test_foreach_with_find_in_map_in_conditions(self):
        """
        Test Fn::ForEach with Fn::FindInMap used in conditional logic.

        This tests the scenario where Fn::FindInMap is used to look up
        values that affect resource configuration within a ForEach loop.

        **Validates: Requirements 5A.1, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "QueueConfig": {
                    "HighPriority": {"VisibilityTimeout": "300", "DelaySeconds": "0"},
                    "LowPriority": {"VisibilityTimeout": "60", "DelaySeconds": "30"},
                }
            },
            "Resources": {
                "Fn::ForEach::Queues": [
                    "Priority",
                    ["HighPriority", "LowPriority"],
                    {
                        "${Priority}Queue": {
                            "Type": "AWS::SQS::Queue",
                            "Properties": {
                                "QueueName": {"Fn::Sub": "${Priority}-queue"},
                                "VisibilityTimeout": {
                                    "Fn::FindInMap": ["QueueConfig", "${Priority}", "VisibilityTimeout"]
                                },
                                "DelaySeconds": {"Fn::FindInMap": ["QueueConfig", "${Priority}", "DelaySeconds"]},
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "HighPriorityQueue" in result["Resources"]
        assert "LowPriorityQueue" in result["Resources"]

        # Verify Fn::FindInMap resolved correctly for each queue
        assert result["Resources"]["HighPriorityQueue"]["Properties"]["VisibilityTimeout"] == "300"
        assert result["Resources"]["HighPriorityQueue"]["Properties"]["DelaySeconds"] == "0"

        assert result["Resources"]["LowPriorityQueue"]["Properties"]["VisibilityTimeout"] == "60"
        assert result["Resources"]["LowPriorityQueue"]["Properties"]["DelaySeconds"] == "30"

    def test_foreach_with_find_in_map_partial_defaults(self):
        """
        Test Fn::ForEach with Fn::FindInMap where some properties use defaults.

        This tests a mixed scenario where some properties exist in mappings
        and others fall back to DefaultValue.

        **Validates: Requirements 5A.1, 5A.2, 5A.3, 5A.4**
        """
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Mappings": {
                "BucketConfig": {
                    "Logs": {"Versioning": "Enabled"},
                    "Data": {"Versioning": "Suspended", "Encryption": "AES256"},
                    # Assets has no configuration - will use all defaults
                }
            },
            "Resources": {
                "Fn::ForEach::Buckets": [
                    "BucketName",
                    ["Logs", "Data", "Assets"],
                    {
                        "${BucketName}Bucket": {
                            "Type": "AWS::S3::Bucket",
                            "Properties": {
                                "BucketName": {"Fn::Sub": "${BucketName}-bucket"},
                                "VersioningConfiguration": {
                                    "Status": {
                                        "Fn::FindInMap": [
                                            "BucketConfig",
                                            "${BucketName}",
                                            "Versioning",
                                            {"DefaultValue": "Suspended"},
                                        ]
                                    }
                                },
                                "BucketEncryption": {
                                    "ServerSideEncryptionConfiguration": [
                                        {
                                            "ServerSideEncryptionByDefault": {
                                                "SSEAlgorithm": {
                                                    "Fn::FindInMap": [
                                                        "BucketConfig",
                                                        "${BucketName}",
                                                        "Encryption",
                                                        {"DefaultValue": "aws:kms"},
                                                    ]
                                                }
                                            }
                                        }
                                    ]
                                },
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # Verify ForEach was expanded
        assert "LogsBucket" in result["Resources"]
        assert "DataBucket" in result["Resources"]
        assert "AssetsBucket" in result["Resources"]

        # Logs: Versioning from map, Encryption from default
        assert result["Resources"]["LogsBucket"]["Properties"]["VersioningConfiguration"]["Status"] == "Enabled"
        encryption_config = result["Resources"]["LogsBucket"]["Properties"]["BucketEncryption"]
        assert (
            encryption_config["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"]
            == "aws:kms"
        )

        # Data: Both from map
        assert result["Resources"]["DataBucket"]["Properties"]["VersioningConfiguration"]["Status"] == "Suspended"
        encryption_config = result["Resources"]["DataBucket"]["Properties"]["BucketEncryption"]
        assert (
            encryption_config["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"]
            == "AES256"
        )

        # Assets: Both from defaults (not in mappings)
        assert result["Resources"]["AssetsBucket"]["Properties"]["VersioningConfiguration"]["Status"] == "Suspended"
        encryption_config = result["Resources"]["AssetsBucket"]["Properties"]["BucketEncryption"]
        assert (
            encryption_config["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"]
            == "aws:kms"
        )


class TestFnFindInMapNullValues:
    """Tests for FnFindInMapResolver handling of null values in mappings."""

    @pytest.fixture
    def mappings_with_null(self) -> Dict[str, Any]:
        return {
            "RegionMap": {
                "us-east-1": {"AMI": None, "InstanceType": "t2.micro"},
                "us-west-2": {"AMI": "ami-87654321"},
            }
        }

    @pytest.fixture
    def context(self, mappings_with_null: Dict[str, Any]) -> TemplateProcessingContext:
        ctx = TemplateProcessingContext(
            fragment={"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance"}}, "Mappings": mappings_with_null}
        )
        ctx.parsed_template = ParsedTemplate(resources={}, mappings=mappings_with_null)
        return ctx

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnFindInMapResolver:
        return FnFindInMapResolver(context, None)

    def test_null_value_without_default_raises_exception(self, resolver: FnFindInMapResolver):
        """Test that null value in mapping without DefaultValue raises exception."""
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}
        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)
        assert "us-east-1" in str(exc_info.value) or "AMI" in str(exc_info.value)

    def test_null_value_with_default_returns_default(self, resolver: FnFindInMapResolver):
        """Test that null value in mapping with DefaultValue returns the default."""
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI", {"DefaultValue": "ami-default"}]}
        result = resolver.resolve(value)
        assert result == "ami-default"


class TestFnFindInMapFallbackToFragment:
    """Tests for FnFindInMapResolver fallback to fragment mappings."""

    def test_fallback_to_fragment_when_no_parsed_template(self):
        """Test that resolver falls back to fragment mappings when parsed_template is None."""
        mappings = {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}}
        ctx = TemplateProcessingContext(fragment={"Resources": {}, "Mappings": mappings})
        ctx.parsed_template = None
        resolver = FnFindInMapResolver(ctx, None)
        value = {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}
        result = resolver.resolve(value)
        assert result == "ami-12345678"
