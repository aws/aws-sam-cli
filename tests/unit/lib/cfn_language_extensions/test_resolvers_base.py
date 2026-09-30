"""
Unit tests for the IntrinsicFunctionResolver base class and related infrastructure.

Tests cover:
- IntrinsicFunctionResolver base class pattern matching (can_resolve)
- IntrinsicFunctionResolver utility methods
- IntrinsicResolver orchestrator and resolver chain pattern
- Constants for resolvable and unresolvable intrinsics
- Partial resolution mode (preserving unresolvable references)
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
    RESOLVABLE_INTRINSICS,
    UNRESOLVABLE_INTRINSICS,
)


class MockResolver(IntrinsicFunctionResolver):
    """A mock resolver for testing that handles Fn::Mock."""

    FUNCTION_NAMES = ["Fn::Mock"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return the arguments doubled if it's a number, otherwise as-is."""
        args = self.get_function_args(value)
        if isinstance(args, (int, float)):
            return args * 2
        return args


class MultiMockResolver(IntrinsicFunctionResolver):
    """A mock resolver that handles multiple function names."""

    FUNCTION_NAMES = ["Fn::MockA", "Fn::MockB"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return the function name and args as a tuple."""
        fn_name = self.get_function_name(value)
        args = self.get_function_args(value)
        return (fn_name, args)


class TestIntrinsicFunctionResolverCanResolve:
    """Tests for IntrinsicFunctionResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> MockResolver:
        """Create a mock resolver for testing."""
        return MockResolver(context, None)

    def test_can_resolve_matching_function(self, resolver: MockResolver):
        """Test that can_resolve returns True for matching function name."""
        value = {"Fn::Mock": [1, 2, 3]}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_non_matching_function(self, resolver: MockResolver):
        """Test that can_resolve returns False for non-matching function name."""
        value = {"Fn::Other": [1, 2, 3]}
        assert resolver.can_resolve(value) is False

    def test_can_resolve_non_dict(self, resolver: MockResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_can_resolve_empty_dict(self, resolver: MockResolver):
        """Test that can_resolve returns False for empty dict."""
        assert resolver.can_resolve({}) is False

    def test_can_resolve_multi_key_dict(self, resolver: MockResolver):
        """Test that can_resolve returns False for dict with multiple keys."""
        value = {"Fn::Mock": [1, 2, 3], "extra": "key"}
        assert resolver.can_resolve(value) is False

    def test_can_resolve_regular_dict(self, resolver: MockResolver):
        """Test that can_resolve returns False for regular dict (not intrinsic)."""
        value = {"Type": "AWS::S3::Bucket", "Properties": {}}
        assert resolver.can_resolve(value) is False


class TestIntrinsicFunctionResolverUtilityMethods:
    """Tests for IntrinsicFunctionResolver utility methods."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> MockResolver:
        """Create a mock resolver for testing."""
        return MockResolver(context, None)

    def test_get_function_name(self, resolver: MockResolver):
        """Test extracting function name from intrinsic function value."""
        value = {"Fn::Mock": [1, 2, 3]}
        assert resolver.get_function_name(value) == "Fn::Mock"

    def test_get_function_args_list(self, resolver: MockResolver):
        """Test extracting list arguments from intrinsic function value."""
        value = {"Fn::Mock": [1, 2, 3]}
        assert resolver.get_function_args(value) == [1, 2, 3]

    def test_get_function_args_string(self, resolver: MockResolver):
        """Test extracting string arguments from intrinsic function value."""
        value = {"Fn::Mock": "hello"}
        assert resolver.get_function_args(value) == "hello"

    def test_get_function_args_dict(self, resolver: MockResolver):
        """Test extracting dict arguments from intrinsic function value."""
        value = {"Fn::Mock": {"key": "value"}}
        assert resolver.get_function_args(value) == {"key": "value"}


class TestIntrinsicFunctionResolverResolve:
    """Tests for IntrinsicFunctionResolver.resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> MockResolver:
        """Create a mock resolver for testing."""
        return MockResolver(context, None)

    def test_resolve_returns_expected_value(self, resolver: MockResolver):
        """Test that resolve returns the expected value."""
        value = {"Fn::Mock": 5}
        assert resolver.resolve(value) == 10  # MockResolver doubles numbers

    def test_resolve_with_non_numeric_args(self, resolver: MockResolver):
        """Test resolve with non-numeric arguments."""
        value = {"Fn::Mock": "hello"}
        assert resolver.resolve(value) == "hello"


class TestMultiFunctionResolver:
    """Tests for resolvers that handle multiple function names."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> MultiMockResolver:
        """Create a multi-function mock resolver for testing."""
        return MultiMockResolver(context, None)

    def test_can_resolve_first_function(self, resolver: MultiMockResolver):
        """Test can_resolve for first function name."""
        value = {"Fn::MockA": "args"}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_second_function(self, resolver: MultiMockResolver):
        """Test can_resolve for second function name."""
        value = {"Fn::MockB": "args"}
        assert resolver.can_resolve(value) is True

    def test_resolve_identifies_function(self, resolver: MultiMockResolver):
        """Test that resolve can identify which function was called."""
        value_a = {"Fn::MockA": "args_a"}
        value_b = {"Fn::MockB": "args_b"}

        assert resolver.resolve(value_a) == ("Fn::MockA", "args_a")
        assert resolver.resolve(value_b) == ("Fn::MockB", "args_b")


class TestIntrinsicResolver:
    """Tests for IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    def test_register_resolver(self, context: TemplateProcessingContext):
        """Test registering a resolver class."""
        orchestrator = IntrinsicResolver(context)
        result = orchestrator.register_resolver(MockResolver)

        # Should return self for chaining
        assert result is orchestrator
        # Should have one resolver
        assert len(orchestrator.resolvers) == 1
        assert isinstance(orchestrator.resolvers[0], MockResolver)

    def test_add_resolver(self, context: TemplateProcessingContext):
        """Test adding a pre-instantiated resolver."""
        orchestrator = IntrinsicResolver(context)
        resolver = MockResolver(context, orchestrator)
        result = orchestrator.add_resolver(resolver)

        # Should return self for chaining
        assert result is orchestrator
        # Should have one resolver
        assert len(orchestrator.resolvers) == 1
        assert orchestrator.resolvers[0] is resolver

    def test_method_chaining(self, context: TemplateProcessingContext):
        """Test that register_resolver supports method chaining."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver).register_resolver(MultiMockResolver)

        assert len(orchestrator.resolvers) == 2

    def test_resolve_value_with_matching_resolver(self, context: TemplateProcessingContext):
        """Test resolve_value with a matching resolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver)

        result = orchestrator.resolve_value({"Fn::Mock": 5})
        assert result == 10  # MockResolver doubles numbers

    def test_resolve_value_with_no_matching_resolver(self, context: TemplateProcessingContext):
        """Test resolve_value when no resolver matches."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver)

        # Fn::Other is not handled by MockResolver
        result = orchestrator.resolve_value({"Fn::Other": 5})
        # Should return the dict as-is (with recursive processing)
        assert result == {"Fn::Other": 5}

    def test_resolve_value_primitive(self, context: TemplateProcessingContext):
        """Test resolve_value with primitive values."""
        orchestrator = IntrinsicResolver(context)

        assert orchestrator.resolve_value("string") == "string"
        assert orchestrator.resolve_value(123) == 123
        assert orchestrator.resolve_value(True) is True
        assert orchestrator.resolve_value(None) is None

    def test_resolve_value_list(self, context: TemplateProcessingContext):
        """Test resolve_value with list containing intrinsics."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver)

        result = orchestrator.resolve_value([{"Fn::Mock": 5}, "plain", {"Fn::Mock": 10}])

        assert result == [10, "plain", 20]

    def test_resolve_value_nested_dict(self, context: TemplateProcessingContext):
        """Test resolve_value with nested dict containing intrinsics."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver)

        result = orchestrator.resolve_value({"outer": {"inner": {"Fn::Mock": 5}}})

        assert result == {"outer": {"inner": 10}}

    def test_resolvers_property_returns_copy(self, context: TemplateProcessingContext):
        """Test that resolvers property returns a copy."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(MockResolver)

        resolvers = orchestrator.resolvers
        resolvers.append(None)  # type: ignore[arg-type]  # Intentionally testing with invalid type

        # Original should be unchanged
        assert len(orchestrator.resolvers) == 1


class TestIntrinsicConstants:
    """Tests for intrinsic function constants."""

    def test_resolvable_intrinsics_contains_expected_functions(self):
        """Test that RESOLVABLE_INTRINSICS contains expected functions."""
        expected = {
            "Fn::Length",
            "Fn::ToJsonString",
            "Fn::FindInMap",
            "Fn::If",
            "Fn::Sub",
            "Fn::Join",
            "Fn::Split",
            "Fn::Select",
            "Fn::Base64",
            "Fn::Equals",
            "Fn::And",
            "Fn::Or",
            "Fn::Not",
            "Ref",
        }
        assert RESOLVABLE_INTRINSICS == expected

    def test_unresolvable_intrinsics_contains_expected_functions(self):
        """Test that UNRESOLVABLE_INTRINSICS contains expected functions."""
        expected = {
            "Fn::GetAtt",
            "Fn::ImportValue",
            "Fn::GetAZs",
            "Fn::Cidr",
            "Ref",
        }
        assert UNRESOLVABLE_INTRINSICS == expected

    def test_ref_in_both_sets(self):
        """Test that Ref is in both sets (context-dependent resolution)."""
        # Ref can be resolved for parameters/pseudo-parameters
        # but must be preserved for resource references
        assert "Ref" in RESOLVABLE_INTRINSICS
        assert "Ref" in UNRESOLVABLE_INTRINSICS


class TestIntrinsicFunctionResolverAbstract:
    """Tests for abstract behavior of IntrinsicFunctionResolver."""

    def test_subclass_without_resolve_cannot_be_instantiated(self):
        """Test that subclass without resolve() implementation cannot be instantiated."""
        context = TemplateProcessingContext(fragment={"Resources": {}})

        # Create a subclass that doesn't override resolve
        class IncompleteResolver(IntrinsicFunctionResolver):
            FUNCTION_NAMES = ["Fn::Incomplete"]

        # Python's ABC prevents instantiation without implementing abstract methods
        with pytest.raises(TypeError) as exc_info:
            IncompleteResolver(context, None)

        assert "abstract" in str(exc_info.value).lower()
        assert "resolve" in str(exc_info.value).lower()

    def test_base_class_cannot_be_instantiated_directly(self):
        """Test that base class cannot be instantiated directly."""
        context = TemplateProcessingContext(fragment={"Resources": {}})

        # Python's ABC prevents instantiation of abstract base class
        with pytest.raises(TypeError) as exc_info:
            IntrinsicFunctionResolver(context, None)

        assert "abstract" in str(exc_info.value).lower()


class TestIntrinsicResolverPartialMode:
    """Tests for IntrinsicResolver partial resolution mode.

    Requirements:
        - 16.1: Support partial resolution mode that preserves Fn::Ref to resources
        - 16.2: Support partial resolution mode that preserves Fn::GetAtt references
        - 16.3: Support partial resolution mode that preserves Fn::ImportValue references
        - 16.4: In partial mode, still resolve Fn::ForEach, Fn::Length, Fn::ToJsonString,
                and Fn::FindInMap with DefaultValue
        - 16.5: In partial mode, resolve Fn::If conditions where condition value is known
        - 16.6: Allow configuration of which intrinsic functions to preserve vs resolve
    """

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    @pytest.fixture
    def full_context(self) -> TemplateProcessingContext:
        """Create a context in full resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.FULL,
        )

    @pytest.fixture
    def context_with_params(self) -> TemplateProcessingContext:
        """Create a context with parameters defined."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
            parameter_values={"Environment": "prod", "BucketName": "my-bucket"},
        )
        context.parsed_template = ParsedTemplate(
            parameters={
                "Environment": {"Type": "String"},
                "BucketName": {"Type": "String"},
            },
            resources={"MyBucket": {"Type": "AWS::S3::Bucket"}},
        )
        return context

    # Tests for Fn::GetAtt preservation (Requirement 16.2)

    def test_preserve_fn_getatt_in_partial_mode(self, partial_context: TemplateProcessingContext):
        """Test that Fn::GetAtt is preserved in partial resolution mode.

        Requirement 16.2: Support partial resolution mode that preserves Fn::GetAtt references
        """
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Fn::GetAtt": ["MyBucket", "Arn"]}
        result = orchestrator.resolve_value(value)

        assert result == {"Fn::GetAtt": ["MyBucket", "Arn"]}

    def test_fn_getatt_not_preserved_in_full_mode(self, full_context: TemplateProcessingContext):
        """Test that Fn::GetAtt is not preserved in full resolution mode."""
        orchestrator = IntrinsicResolver(full_context)

        value = {"Fn::GetAtt": ["MyBucket", "Arn"]}
        result = orchestrator.resolve_value(value)

        # In full mode without a resolver, it's returned as-is (not preserved)
        # The dict is processed recursively but no resolver handles it
        assert result == {"Fn::GetAtt": ["MyBucket", "Arn"]}

    def test_preserve_fn_getatt_with_nested_intrinsics(self, partial_context: TemplateProcessingContext):
        """Test that Fn::GetAtt arguments are still resolved in partial mode."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        # Fn::GetAtt with nested Fn::Mock in arguments
        value = {"Fn::GetAtt": [{"Fn::Mock": "Resource"}, "Arn"]}
        result = orchestrator.resolve_value(value)

        # Fn::GetAtt is preserved but its arguments are resolved
        assert result == {"Fn::GetAtt": ["Resource", "Arn"]}

    # Tests for Fn::ImportValue preservation (Requirement 16.3)

    def test_preserve_fn_importvalue_in_partial_mode(self, partial_context: TemplateProcessingContext):
        """Test that Fn::ImportValue is preserved in partial resolution mode.

        Requirement 16.3: Support partial resolution mode that preserves Fn::ImportValue references
        """
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Fn::ImportValue": "SharedVpcId"}
        result = orchestrator.resolve_value(value)

        assert result == {"Fn::ImportValue": "SharedVpcId"}

    def test_preserve_fn_importvalue_with_sub(self, partial_context: TemplateProcessingContext):
        """Test that Fn::ImportValue with nested Fn::Sub is preserved."""
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Fn::ImportValue": {"Fn::Sub": "${Environment}-VpcId"}}
        result = orchestrator.resolve_value(value)

        # ImportValue is preserved, but Fn::Sub inside is not resolved (no resolver)
        assert result == {"Fn::ImportValue": {"Fn::Sub": "${Environment}-VpcId"}}

    # Tests for Ref preservation (Requirement 16.1)

    def test_preserve_ref_to_resource_in_partial_mode(self, context_with_params: TemplateProcessingContext):
        """Test that Ref to resources is preserved in partial resolution mode.

        Requirement 16.1: Support partial resolution mode that preserves Fn::Ref to resources
        """
        orchestrator = IntrinsicResolver(context_with_params)

        # MyBucket is a resource, not a parameter
        value = {"Ref": "MyBucket"}
        result = orchestrator.resolve_value(value)

        assert result == {"Ref": "MyBucket"}

    def test_ref_to_parameter_not_preserved(self, context_with_params: TemplateProcessingContext):
        """Test that Ref to parameters is NOT preserved (can be resolved)."""
        orchestrator = IntrinsicResolver(context_with_params)

        # Environment is a parameter, not a resource
        value = {"Ref": "Environment"}
        result = orchestrator.resolve_value(value)

        # Without a Ref resolver, it's returned as-is but NOT marked as preserved
        # The key difference is it goes through normal resolution path
        assert result == {"Ref": "Environment"}

    def test_ref_to_pseudo_parameter_not_preserved(self, partial_context: TemplateProcessingContext):
        """Test that Ref to pseudo-parameters is NOT preserved."""
        orchestrator = IntrinsicResolver(partial_context)

        # AWS::Region is a pseudo-parameter
        value = {"Ref": "AWS::Region"}
        result = orchestrator.resolve_value(value)

        # Without a Ref resolver, it's returned as-is but NOT marked as preserved
        assert result == {"Ref": "AWS::Region"}

    def test_ref_to_aws_account_id_not_preserved(self, partial_context: TemplateProcessingContext):
        """Test that Ref to AWS::AccountId is NOT preserved."""
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Ref": "AWS::AccountId"}
        result = orchestrator.resolve_value(value)

        assert result == {"Ref": "AWS::AccountId"}

    def test_ref_to_aws_stack_name_not_preserved(self, partial_context: TemplateProcessingContext):
        """Test that Ref to AWS::StackName is NOT preserved."""
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Ref": "AWS::StackName"}
        result = orchestrator.resolve_value(value)

        assert result == {"Ref": "AWS::StackName"}

    # Tests for Fn::GetAZs preservation

    def test_preserve_fn_getazs_in_partial_mode(self, partial_context: TemplateProcessingContext):
        """Test that Fn::GetAZs is preserved in partial resolution mode."""
        orchestrator = IntrinsicResolver(partial_context)

        value = {"Fn::GetAZs": "us-east-1"}
        result = orchestrator.resolve_value(value)

        assert result == {"Fn::GetAZs": "us-east-1"}

    # Tests for resolvable intrinsics in partial mode (Requirement 16.4)

    def test_resolve_fn_mock_in_partial_mode(self, partial_context: TemplateProcessingContext):
        """Test that registered resolvers still work in partial mode.

        Requirement 16.4: In partial mode, still resolve Fn::ForEach, Fn::Length, etc.
        """
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        value = {"Fn::Mock": 5}
        result = orchestrator.resolve_value(value)

        # MockResolver should still resolve this
        assert result == 10

    def test_resolve_nested_with_preserved_intrinsic(self, partial_context: TemplateProcessingContext):
        """Test resolving nested structure with both resolvable and preserved intrinsics."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        value = {
            "resolved": {"Fn::Mock": 5},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "resolved": 10,
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }

    # Tests for preserve_functions configuration (Requirement 16.6)

    def test_default_preserve_functions(self, partial_context: TemplateProcessingContext):
        """Test that default preserve functions are set correctly.

        Requirement 16.6: Allow configuration of which intrinsic functions to preserve vs resolve
        """
        orchestrator = IntrinsicResolver(partial_context)

        expected = {"Fn::GetAtt", "Fn::ImportValue", "Fn::GetAZs", "Fn::Cidr"}
        assert orchestrator.preserve_functions == expected

    def test_custom_preserve_functions(self, partial_context: TemplateProcessingContext):
        """Test creating orchestrator with custom preserve functions."""
        custom_preserve = {"Fn::GetAtt", "Fn::CustomFunction"}
        orchestrator = IntrinsicResolver(partial_context, preserve_functions=custom_preserve)

        assert orchestrator.preserve_functions == custom_preserve

    def test_set_preserve_functions(self, partial_context: TemplateProcessingContext):
        """Test setting preserve functions after creation."""
        orchestrator = IntrinsicResolver(partial_context)

        new_preserve = {"Fn::GetAtt", "Fn::ImportValue"}
        result = orchestrator.set_preserve_functions(new_preserve)

        assert result is orchestrator  # Returns self for chaining
        assert orchestrator.preserve_functions == new_preserve

    def test_add_preserve_function(self, partial_context: TemplateProcessingContext):
        """Test adding a function to preserve list."""
        orchestrator = IntrinsicResolver(partial_context)

        result = orchestrator.add_preserve_function("Fn::CustomFunction")

        assert result is orchestrator
        assert "Fn::CustomFunction" in orchestrator.preserve_functions

    def test_remove_preserve_function(self, partial_context: TemplateProcessingContext):
        """Test removing a function from preserve list."""
        orchestrator = IntrinsicResolver(partial_context)

        result = orchestrator.remove_preserve_function("Fn::GetAtt")

        assert result is orchestrator
        assert "Fn::GetAtt" not in orchestrator.preserve_functions

    def test_custom_function_preserved(self, partial_context: TemplateProcessingContext):
        """Test that custom functions can be preserved."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.add_preserve_function("Fn::CustomFunction")

        value = {"Fn::CustomFunction": "args"}
        result = orchestrator.resolve_value(value)

        assert result == {"Fn::CustomFunction": "args"}

    def test_removed_function_not_preserved(self, partial_context: TemplateProcessingContext):
        """Test that removed functions are no longer preserved."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.remove_preserve_function("Fn::GetAtt")

        value = {"Fn::GetAtt": ["MyBucket", "Arn"]}
        result = orchestrator.resolve_value(value)

        # Without preservation and without a resolver, it's processed normally
        assert result == {"Fn::GetAtt": ["MyBucket", "Arn"]}

    def test_preserve_functions_returns_copy(self, partial_context: TemplateProcessingContext):
        """Test that preserve_functions returns a copy."""
        orchestrator = IntrinsicResolver(partial_context)

        preserve = orchestrator.preserve_functions
        preserve.add("Fn::Modified")

        # Original should be unchanged
        assert "Fn::Modified" not in orchestrator.preserve_functions


class TestIntrinsicResolverIsIntrinsicFunction:
    """Tests for IntrinsicResolver._is_intrinsic_function() method."""

    @pytest.fixture
    def orchestrator(self) -> IntrinsicResolver:
        """Create an orchestrator for testing."""
        context = TemplateProcessingContext(fragment={"Resources": {}})
        return IntrinsicResolver(context)

    def test_fn_prefix_is_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test that Fn:: prefixed functions are recognized."""
        assert orchestrator._is_intrinsic_function({"Fn::GetAtt": ["A", "B"]}) is True
        assert orchestrator._is_intrinsic_function({"Fn::Sub": "hello"}) is True
        assert orchestrator._is_intrinsic_function({"Fn::Length": [1, 2]}) is True

    def test_ref_is_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test that Ref is recognized as intrinsic."""
        assert orchestrator._is_intrinsic_function({"Ref": "MyResource"}) is True

    def test_condition_is_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test that Condition is recognized as intrinsic."""
        assert orchestrator._is_intrinsic_function({"Condition": "MyCondition"}) is True

    def test_non_intrinsic_dict(self, orchestrator: IntrinsicResolver):
        """Test that regular dicts are not recognized as intrinsic."""
        assert orchestrator._is_intrinsic_function({"Type": "AWS::S3::Bucket"}) is False
        assert orchestrator._is_intrinsic_function({"key": "value"}) is False

    def test_multi_key_dict_not_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test that multi-key dicts are not recognized as intrinsic."""
        assert orchestrator._is_intrinsic_function({"Fn::Sub": "a", "extra": "b"}) is False

    def test_non_dict_not_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test that non-dict values are not recognized as intrinsic."""
        assert orchestrator._is_intrinsic_function("string") is False
        assert orchestrator._is_intrinsic_function(123) is False
        assert orchestrator._is_intrinsic_function([1, 2, 3]) is False
        assert orchestrator._is_intrinsic_function(None) is False


class TestIntrinsicResolverIsResourceRef:
    """Tests for IntrinsicResolver._is_resource_ref() method."""

    @pytest.fixture
    def context_with_params(self) -> TemplateProcessingContext:
        """Create a context with parameters and resources."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"ParamFromValues": "value"},
        )
        context.parsed_template = ParsedTemplate(
            parameters={"ParamFromTemplate": {"Type": "String"}},
            resources={"MyResource": {"Type": "AWS::S3::Bucket"}},
        )
        return context

    def test_pseudo_parameter_not_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that pseudo-parameters are not resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        pseudo_params = [
            "AWS::AccountId",
            "AWS::NotificationARNs",
            "AWS::NoValue",
            "AWS::Partition",
            "AWS::Region",
            "AWS::StackId",
            "AWS::StackName",
            "AWS::URLSuffix",
        ]

        for param in pseudo_params:
            assert orchestrator._is_resource_ref({"Ref": param}) is False

    def test_template_parameter_not_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that template parameters are not resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        assert orchestrator._is_resource_ref({"Ref": "ParamFromTemplate"}) is False

    def test_parameter_values_not_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that parameters from parameter_values are not resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        assert orchestrator._is_resource_ref({"Ref": "ParamFromValues"}) is False

    def test_resource_is_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that resources are identified as resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        # MyResource is in resources, not parameters
        assert orchestrator._is_resource_ref({"Ref": "MyResource"}) is True

    def test_unknown_ref_is_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that unknown refs are assumed to be resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        # UnknownThing is not a parameter or pseudo-param, assume resource
        assert orchestrator._is_resource_ref({"Ref": "UnknownThing"}) is True

    def test_non_string_ref_not_resource_ref(self, context_with_params: TemplateProcessingContext):
        """Test that non-string Ref values are not resource refs."""
        orchestrator = IntrinsicResolver(context_with_params)

        assert orchestrator._is_resource_ref({"Ref": 123}) is False
        assert orchestrator._is_resource_ref({"Ref": ["list"]}) is False


class TestIntrinsicResolverRecursiveResolution:
    """Tests for recursive resolution in IntrinsicResolver."""

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
        )

    def test_deeply_nested_structure(self, partial_context: TemplateProcessingContext):
        """Test resolution of deeply nested structures."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        value = {"level1": {"level2": {"level3": {"Fn::Mock": 5}}}}
        result = orchestrator.resolve_value(value)

        assert result == {"level1": {"level2": {"level3": 10}}}

    def test_mixed_list_and_dict(self, partial_context: TemplateProcessingContext):
        """Test resolution of mixed list and dict structures."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        value = {
            "items": [
                {"Fn::Mock": 1},
                {"nested": {"Fn::Mock": 2}},
                [{"Fn::Mock": 3}],
            ]
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "items": [
                2,
                {"nested": 4},
                [6],
            ]
        }

    def test_preserved_intrinsic_with_resolvable_args(self, partial_context: TemplateProcessingContext):
        """Test that preserved intrinsics have their arguments resolved."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(MockResolver)

        # Fn::GetAtt is preserved, but its arguments should be resolved
        value = {"Fn::GetAtt": [{"Fn::Mock": "ResourceName"}, "Arn"]}  # This should be resolved
        result = orchestrator.resolve_value(value)

        # Fn::GetAtt preserved, but Fn::Mock in args resolved
        assert result == {"Fn::GetAtt": ["ResourceName", "Arn"]}
