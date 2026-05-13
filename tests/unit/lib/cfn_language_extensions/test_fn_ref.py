"""
Unit tests for the FnRefResolver class.

Tests cover:
- Parameter reference resolution
- Pseudo-parameter reference resolution
- Resource reference preservation in partial mode
- Error handling for invalid inputs

Requirements:
    - 10.1: WHEN Ref is applied to a template parameter, THEN THE Resolver SHALL
            return the parameter's value from the context
    - 9.2: WHEN a pseudo-parameter (AWS::Region, AWS::AccountId, etc.) is referenced,
           THEN THE Resolver SHALL return the value from the PseudoParameterValues
           if provided
    - 9.3: WHEN a pseudo-parameter is referenced but no value is provided, THEN THE
           Resolver SHALL preserve the reference unresolved
"""

import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
    PseudoParameterValues,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver, PSEUDO_PARAMETERS
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnRefResolverCanResolve:
    """Tests for FnRefResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnRefResolver:
        """Create a FnRefResolver for testing."""
        return FnRefResolver(context, None)

    def test_can_resolve_ref(self, resolver: FnRefResolver):
        """Test that can_resolve returns True for Ref."""
        value = {"Ref": "MyParameter"}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnRefResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnRefResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnRefResolver):
        """Test that FUNCTION_NAMES contains Ref."""
        assert FnRefResolver.FUNCTION_NAMES == ["Ref"]


class TestFnRefResolverParameterResolution:
    """Tests for Ref parameter resolution.

    Requirement 10.1: WHEN Ref is applied to a template parameter, THEN THE
    Resolver SHALL return the parameter's value from the context
    """

    @pytest.fixture
    def context_with_params(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Environment": "production",
                "InstanceType": "t3.medium",
                "EnableFeature": True,
                "MaxCount": 10,
            },
        )

    @pytest.fixture
    def resolver(self, context_with_params: TemplateProcessingContext) -> FnRefResolver:
        """Create a FnRefResolver with parameter context."""
        return FnRefResolver(context_with_params, None)

    def test_resolve_string_parameter(self, resolver: FnRefResolver):
        """Test resolving a string parameter.

        Requirement 10.1: Return parameter value from context
        """
        value = {"Ref": "Environment"}
        result = resolver.resolve(value)
        assert result == "production"

    def test_resolve_another_string_parameter(self, resolver: FnRefResolver):
        """Test resolving another string parameter.

        Requirement 10.1: Return parameter value from context
        """
        value = {"Ref": "InstanceType"}
        result = resolver.resolve(value)
        assert result == "t3.medium"

    def test_resolve_boolean_parameter(self, resolver: FnRefResolver):
        """Test resolving a boolean parameter.

        Requirement 10.1: Return parameter value from context
        """
        value = {"Ref": "EnableFeature"}
        result = resolver.resolve(value)
        assert result is True

    def test_resolve_integer_parameter(self, resolver: FnRefResolver):
        """Test resolving an integer parameter.

        Requirement 10.1: Return parameter value from context
        """
        value = {"Ref": "MaxCount"}
        result = resolver.resolve(value)
        assert result == 10

    def test_resolve_parameter_with_default(self):
        """Test resolving a parameter with default value when no value provided.

        Requirement 10.1: Return parameter value from context
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
            parsed_template=ParsedTemplate(
                parameters={"Environment": {"Type": "String", "Default": "development"}}, resources={}
            ),
        )
        resolver = FnRefResolver(context, None)

        value = {"Ref": "Environment"}
        result = resolver.resolve(value)
        assert result == "development"


class TestFnRefResolverPseudoParameterResolution:
    """Tests for Ref pseudo-parameter resolution.

    Requirement 9.2: WHEN a pseudo-parameter (AWS::Region, AWS::AccountId, etc.)
    is referenced, THEN THE Resolver SHALL return the value from the
    PseudoParameterValues if provided
    """

    @pytest.fixture
    def context_with_pseudo_params(self) -> TemplateProcessingContext:
        """Create a context with pseudo-parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
                stack_id="arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid",
                stack_name="my-stack",
                notification_arns=["arn:aws:sns:us-west-2:123456789012:my-topic"],
            ),
        )

    @pytest.fixture
    def resolver(self, context_with_pseudo_params: TemplateProcessingContext) -> FnRefResolver:
        """Create a FnRefResolver with pseudo-parameter context."""
        return FnRefResolver(context_with_pseudo_params, None)

    def test_resolve_aws_region(self, resolver: FnRefResolver):
        """Test resolving AWS::Region pseudo-parameter.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::Region"}
        result = resolver.resolve(value)
        assert result == "us-west-2"

    def test_resolve_aws_account_id(self, resolver: FnRefResolver):
        """Test resolving AWS::AccountId pseudo-parameter.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::AccountId"}
        result = resolver.resolve(value)
        assert result == "123456789012"

    def test_resolve_aws_stack_id(self, resolver: FnRefResolver):
        """Test resolving AWS::StackId pseudo-parameter.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::StackId"}
        result = resolver.resolve(value)
        assert result == "arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid"

    def test_resolve_aws_stack_name(self, resolver: FnRefResolver):
        """Test resolving AWS::StackName pseudo-parameter.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::StackName"}
        result = resolver.resolve(value)
        assert result == "my-stack"

    def test_resolve_aws_notification_arns(self, resolver: FnRefResolver):
        """Test resolving AWS::NotificationARNs pseudo-parameter.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::NotificationARNs"}
        result = resolver.resolve(value)
        assert result == ["arn:aws:sns:us-west-2:123456789012:my-topic"]

    def test_resolve_aws_partition_derived(self, resolver: FnRefResolver):
        """Test resolving AWS::Partition derived from region.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::Partition"}
        result = resolver.resolve(value)
        assert result == "aws"

    def test_resolve_aws_url_suffix_derived(self, resolver: FnRefResolver):
        """Test resolving AWS::URLSuffix derived from region.

        Requirement 9.2: Return pseudo-parameter value if provided
        """
        value = {"Ref": "AWS::URLSuffix"}
        result = resolver.resolve(value)
        assert result == "amazonaws.com"


class TestFnRefResolverPartitionDerivation:
    """Tests for AWS::Partition and AWS::URLSuffix derivation from region."""

    def test_partition_for_standard_region(self):
        """Test partition derivation for standard AWS region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-east-1",
                account_id="123456789012",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws"

    def test_partition_for_china_region(self):
        """Test partition derivation for China region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="cn-north-1",
                account_id="123456789012",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws-cn"

    def test_partition_for_govcloud_region(self):
        """Test partition derivation for GovCloud region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-gov-west-1",
                account_id="123456789012",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws-us-gov"

    def test_url_suffix_for_standard_region(self):
        """Test URL suffix derivation for standard AWS region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="eu-west-1",
                account_id="123456789012",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "amazonaws.com"

    def test_url_suffix_for_china_region(self):
        """Test URL suffix derivation for China region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="cn-northwest-1",
                account_id="123456789012",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "amazonaws.com.cn"

    def test_explicit_partition_overrides_derived(self):
        """Test that explicit partition value overrides derived value."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-east-1",
                account_id="123456789012",
                partition="custom-partition",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "custom-partition"

    def test_explicit_url_suffix_overrides_derived(self):
        """Test that explicit URL suffix value overrides derived value."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-east-1",
                account_id="123456789012",
                url_suffix="custom.amazonaws.com",
            ),
        )
        resolver = FnRefResolver(context, None)

        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "custom.amazonaws.com"


class TestFnRefResolverPreserveUnresolved:
    """Tests for preserving unresolved references.

    Requirement 9.3: WHEN a pseudo-parameter is referenced but no value is
    provided, THEN THE Resolver SHALL preserve the reference unresolved
    """

    @pytest.fixture
    def context_no_pseudo_params(self) -> TemplateProcessingContext:
        """Create a context without pseudo-parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )

    @pytest.fixture
    def resolver(self, context_no_pseudo_params: TemplateProcessingContext) -> FnRefResolver:
        """Create a FnRefResolver without pseudo-parameters."""
        return FnRefResolver(context_no_pseudo_params, None)

    def test_preserve_aws_region_without_value(self, resolver: FnRefResolver):
        """Test that AWS::Region is preserved when no value provided.

        Requirement 9.3: Preserve pseudo-parameter reference if no value provided
        """
        value = {"Ref": "AWS::Region"}
        result = resolver.resolve(value)
        assert result == {"Ref": "AWS::Region"}

    def test_preserve_aws_account_id_without_value(self, resolver: FnRefResolver):
        """Test that AWS::AccountId is preserved when no value provided.

        Requirement 9.3: Preserve pseudo-parameter reference if no value provided
        """
        value = {"Ref": "AWS::AccountId"}
        result = resolver.resolve(value)
        assert result == {"Ref": "AWS::AccountId"}

    def test_preserve_aws_stack_name_without_value(self, resolver: FnRefResolver):
        """Test that AWS::StackName is preserved when no value provided.

        Requirement 9.3: Preserve pseudo-parameter reference if no value provided
        """
        value = {"Ref": "AWS::StackName"}
        result = resolver.resolve(value)
        assert result == {"Ref": "AWS::StackName"}

    def test_preserve_resource_reference(self, resolver: FnRefResolver):
        """Test that resource references are preserved.

        Resource references cannot be resolved locally and should be preserved.
        """
        value = {"Ref": "MyBucket"}
        result = resolver.resolve(value)
        assert result == {"Ref": "MyBucket"}

    def test_preserve_unknown_reference(self, resolver: FnRefResolver):
        """Test that unknown references are preserved."""
        value = {"Ref": "UnknownResource"}
        result = resolver.resolve(value)
        assert result == {"Ref": "UnknownResource"}


class TestFnRefResolverPartialMode:
    """Tests for FnRefResolver in partial resolution mode.

    In partial mode, resource references should be preserved while
    parameter and pseudo-parameter references should be resolved.
    """

    @pytest.fixture
    def partial_context(self) -> TemplateProcessingContext:
        """Create a context in partial resolution mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
            parameter_values={"Environment": "prod"},
            pseudo_parameters=PseudoParameterValues(
                region="us-east-1",
                account_id="123456789012",
            ),
            parsed_template=ParsedTemplate(
                parameters={"Environment": {"Type": "String"}}, resources={"MyBucket": {"Type": "AWS::S3::Bucket"}}
            ),
        )

    @pytest.fixture
    def orchestrator(self, partial_context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator in partial mode with FnRefResolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnRefResolver)
        return orchestrator

    def test_parameter_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that parameters are resolved in partial mode."""
        value = {"Ref": "Environment"}
        result = orchestrator.resolve_value(value)
        assert result == "prod"

    def test_pseudo_parameter_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that pseudo-parameters are resolved in partial mode."""
        value = {"Ref": "AWS::Region"}
        result = orchestrator.resolve_value(value)
        assert result == "us-east-1"

    def test_resource_reference_preserved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that resource references are preserved in partial mode."""
        value = {"Ref": "MyBucket"}
        result = orchestrator.resolve_value(value)
        assert result == {"Ref": "MyBucket"}


class TestFnRefResolverErrorHandling:
    """Tests for FnRefResolver error handling."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnRefResolver:
        """Create a FnRefResolver for testing."""
        return FnRefResolver(context, None)

    def test_non_string_ref_target_raises_exception(self, resolver: FnRefResolver):
        """Test that non-string Ref target raises InvalidTemplateException."""
        value = {"Ref": 123}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Ref layout is incorrect" in str(exc_info.value)

    def test_list_ref_target_raises_exception(self, resolver: FnRefResolver):
        """Test that list Ref target raises InvalidTemplateException."""
        value = {"Ref": ["a", "b"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Ref layout is incorrect" in str(exc_info.value)

    def test_dict_ref_target_raises_exception(self, resolver: FnRefResolver):
        """Test that dict Ref target raises InvalidTemplateException."""
        value = {"Ref": {"key": "value"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Ref layout is incorrect" in str(exc_info.value)

    def test_none_ref_target_raises_exception(self, resolver: FnRefResolver):
        """Test that None Ref target raises InvalidTemplateException."""
        value = {"Ref": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Ref layout is incorrect" in str(exc_info.value)


class TestFnRefResolverWithOrchestrator:
    """Tests for FnRefResolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameters and pseudo-parameters."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Environment": "production",
                "BucketName": "my-bucket",
            },
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
            ),
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnRefResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnRefResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Ref through the orchestrator."""
        value = {"Ref": "Environment"}
        result = orchestrator.resolve_value(value)
        assert result == "production"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Ref in a nested template structure."""
        value = {
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": "BucketName"}}}}
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket"

    def test_resolve_multiple_refs(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Refs in same structure."""
        value = {
            "env": {"Ref": "Environment"},
            "region": {"Ref": "AWS::Region"},
            "account": {"Ref": "AWS::AccountId"},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "env": "production",
            "region": "us-west-2",
            "account": "123456789012",
        }

    def test_ref_in_list(self, orchestrator: IntrinsicResolver):
        """Test Ref inside a list."""
        value = [
            {"Ref": "Environment"},
            {"Ref": "AWS::Region"},
            {"Ref": "BucketName"},
        ]
        result = orchestrator.resolve_value(value)

        assert result == ["production", "us-west-2", "my-bucket"]


class TestPseudoParametersConstant:
    """Tests for the PSEUDO_PARAMETERS constant."""

    def test_contains_all_pseudo_parameters(self):
        """Test that PSEUDO_PARAMETERS contains all expected pseudo-parameters."""
        expected = {
            "AWS::AccountId",
            "AWS::NotificationARNs",
            "AWS::NoValue",
            "AWS::Partition",
            "AWS::Region",
            "AWS::StackId",
            "AWS::StackName",
            "AWS::URLSuffix",
        }
        assert PSEUDO_PARAMETERS == expected


# =============================================================================
# Parametrized Tests for Pseudo-Parameter Resolution
# =============================================================================


def _make_stack_id(region: str, account_id: str, stack_name: str) -> str:
    """Generate a valid CloudFormation stack ID ARN."""
    return f"arn:aws:cloudformation:{region}:{account_id}:stack/{stack_name}/guid-1234-5678"


class TestFnRefPseudoParameterPropertyBasedTests:
    """
    Parametrized tests for pseudo-parameter resolution.

    Feature: cfn-language-extensions-python, Property 14: Pseudo-Parameter Resolution

    These tests validate that for any Ref to a pseudo-parameter (AWS::Region,
    AWS::AccountId, etc.) where a value is provided in the context, the resolver
    SHALL substitute that value; where no value is provided, the Ref SHALL be
    preserved unresolved.

    **Validates: Requirements 9.2, 9.3**
    """

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("cn-north-1", "987654321098"),
            ("us-gov-west-1", "111222333444"),
        ],
    )
    def test_aws_region_resolved_when_provided(self, region: str, account_id: str):
        """
        Property 14: For any Ref to AWS::Region where a value is provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Region"})
        assert result == region

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-west-2", "123456789012"),
            ("eu-west-1", "999888777666"),
            ("ap-northeast-1", "555444333222"),
        ],
    )
    def test_aws_account_id_resolved_when_provided(self, region: str, account_id: str):
        """
        Property 14: For any Ref to AWS::AccountId where a value is provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::AccountId"})
        assert result == account_id

    @pytest.mark.parametrize(
        "region, account_id, stack_name",
        [
            ("us-east-1", "123456789012", "my-stack"),
            ("eu-west-1", "999888777666", "prod-app-stack"),
            ("ap-southeast-1", "555444333222", "A1-test"),
        ],
    )
    def test_aws_stack_name_resolved_when_provided(self, region: str, account_id: str, stack_name: str):
        """
        Property 14: For any Ref to AWS::StackName where a value is provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, stack_name=stack_name),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::StackName"})
        assert result == stack_name

    @pytest.mark.parametrize(
        "region, account_id, stack_name",
        [
            ("us-east-1", "123456789012", "my-stack"),
            ("eu-central-1", "999888777666", "prod-stack"),
            ("us-gov-east-1", "555444333222", "gov-stack"),
        ],
    )
    def test_aws_stack_id_resolved_when_provided(self, region: str, account_id: str, stack_name: str):
        """
        Property 14: For any Ref to AWS::StackId where a value is provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        stack_id = _make_stack_id(region, account_id, stack_name)
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, stack_id=stack_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::StackId"})
        assert result == stack_id

    @pytest.mark.parametrize(
        "region, account_id, partition",
        [
            ("us-east-1", "123456789012", "aws"),
            ("cn-north-1", "987654321098", "aws-cn"),
            ("us-gov-west-1", "555444333222", "aws-us-gov"),
        ],
    )
    def test_aws_partition_resolved_when_explicitly_provided(self, region: str, account_id: str, partition: str):
        """
        Property 14: For any Ref to AWS::Partition where a value is explicitly provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, partition=partition),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == partition

    @pytest.mark.parametrize(
        "region, account_id, url_suffix",
        [
            ("us-east-1", "123456789012", "amazonaws.com"),
            ("cn-north-1", "987654321098", "amazonaws.com.cn"),
            ("us-gov-west-1", "555444333222", "amazonaws.com"),
        ],
    )
    def test_aws_url_suffix_resolved_when_explicitly_provided(self, region: str, account_id: str, url_suffix: str):
        """
        Property 14: For any Ref to AWS::URLSuffix where a value is explicitly provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, url_suffix=url_suffix),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == url_suffix

    @pytest.mark.parametrize(
        "pseudo_param",
        [
            "AWS::Region",
            "AWS::AccountId",
            "AWS::StackName",
            "AWS::StackId",
            "AWS::Partition",
            "AWS::URLSuffix",
            "AWS::NotificationARNs",
        ],
    )
    def test_pseudo_parameter_preserved_when_no_context_provided(self, pseudo_param: str):
        """
        Property 14: For any Ref to a pseudo-parameter where no PseudoParameterValues
        context is provided, the resolver SHALL preserve the Ref unresolved.

        **Validates: Requirements 9.3**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=None,
        )
        resolver = FnRefResolver(context, None)
        value = {"Ref": pseudo_param}
        result = resolver.resolve(value)
        assert result == value

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("eu-west-1", "999888777666"),
            ("ap-south-1", "555444333222"),
        ],
    )
    def test_aws_stack_name_preserved_when_not_provided(self, region: str, account_id: str):
        """
        Property 14: For any Ref to AWS::StackName where the stack_name is not provided,
        the resolver SHALL preserve the Ref unresolved.

        **Validates: Requirements 9.3**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, stack_name=None),
        )
        resolver = FnRefResolver(context, None)
        value = {"Ref": "AWS::StackName"}
        result = resolver.resolve(value)
        assert result == value

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-west-2", "123456789012"),
            ("cn-northwest-1", "987654321098"),
        ],
    )
    def test_aws_stack_id_preserved_when_not_provided(self, region: str, account_id: str):
        """
        Property 14: For any Ref to AWS::StackId where the stack_id is not provided,
        the resolver SHALL preserve the Ref unresolved.

        **Validates: Requirements 9.3**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, stack_id=None),
        )
        resolver = FnRefResolver(context, None)
        value = {"Ref": "AWS::StackId"}
        result = resolver.resolve(value)
        assert result == value

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("eu-central-1", "999888777666"),
        ],
    )
    def test_aws_notification_arns_preserved_when_not_provided(self, region: str, account_id: str):
        """
        Property 14: For any Ref to AWS::NotificationARNs where the notification_arns
        is not provided, the resolver SHALL preserve the Ref unresolved.

        **Validates: Requirements 9.3**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id, notification_arns=None),
        )
        resolver = FnRefResolver(context, None)
        value = {"Ref": "AWS::NotificationARNs"}
        result = resolver.resolve(value)
        assert result == value

    @pytest.mark.parametrize(
        "region, account_id, num_arns",
        [
            ("us-east-1", "123456789012", 1),
            ("eu-west-1", "999888777666", 3),
            ("ap-northeast-1", "555444333222", 5),
        ],
    )
    def test_aws_notification_arns_resolved_when_provided(self, region: str, account_id: str, num_arns: int):
        """
        Property 14: For any Ref to AWS::NotificationARNs where a value is provided,
        the resolver SHALL substitute that value.

        **Validates: Requirements 9.2**
        """
        notification_arns = [f"arn:aws:sns:{region}:{account_id}:topic-{i}" for i in range(num_arns)]
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region=region, account_id=account_id, notification_arns=notification_arns
            ),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::NotificationARNs"})
        assert result == notification_arns

    @pytest.mark.parametrize(
        "region, account_id, stack_name",
        [
            ("us-east-1", "123456789012", "my-stack"),
            ("eu-west-2", "999888777666", "prod-app"),
            ("ap-southeast-2", "555444333222", "test-stack"),
        ],
    )
    def test_all_provided_pseudo_parameters_resolved_correctly(self, region: str, account_id: str, stack_name: str):
        """
        Property 14: For any template with multiple Refs to different pseudo-parameters
        where values are provided, all SHALL be resolved to their respective values.

        **Validates: Requirements 9.2**
        """
        stack_id = _make_stack_id(region, account_id, stack_name)
        notification_arns = [f"arn:aws:sns:{region}:{account_id}:my-topic"]

        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region=region,
                account_id=account_id,
                stack_id=stack_id,
                stack_name=stack_name,
                notification_arns=notification_arns,
            ),
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnRefResolver)

        template_value = {
            "region": {"Ref": "AWS::Region"},
            "account": {"Ref": "AWS::AccountId"},
            "stack_name": {"Ref": "AWS::StackName"},
            "stack_id": {"Ref": "AWS::StackId"},
            "notification_arns": {"Ref": "AWS::NotificationARNs"},
        }

        result = orchestrator.resolve_value(template_value)

        assert result["region"] == region
        assert result["account"] == account_id
        assert result["stack_name"] == stack_name
        assert result["stack_id"] == stack_id
        assert result["notification_arns"] == notification_arns

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("eu-west-1", "999888777666"),
            ("ap-south-1", "555444333222"),
        ],
    )
    def test_mixed_provided_and_unprovided_pseudo_parameters(self, region: str, account_id: str):
        """
        Property 14: For any template with Refs to both provided and unprovided
        pseudo-parameters, provided values SHALL be resolved while unprovided
        values SHALL be preserved.

        **Validates: Requirements 9.2, 9.3**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnRefResolver)

        template_value = {
            "region": {"Ref": "AWS::Region"},
            "account": {"Ref": "AWS::AccountId"},
            "stack_name": {"Ref": "AWS::StackName"},
            "stack_id": {"Ref": "AWS::StackId"},
        }

        result = orchestrator.resolve_value(template_value)

        assert result["region"] == region
        assert result["account"] == account_id
        assert result["stack_name"] == {"Ref": "AWS::StackName"}
        assert result["stack_id"] == {"Ref": "AWS::StackId"}


# =============================================================================
# Parametrized Tests for Partition Derivation from Region
# =============================================================================


class TestFnRefPartitionDerivationPropertyBasedTests:
    """
    Parametrized tests for partition derivation from region.

    Feature: cfn-language-extensions-python, Property 15: Partition Derivation from Region

    **Validates: Requirements 9.4**
    """

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("eu-west-1", "999888777666"),
            ("ap-southeast-2", "555444333222"),
        ],
    )
    def test_standard_region_derives_aws_partition(self, region: str, account_id: str):
        """
        Property 15: For any standard AWS region, the resolver SHALL derive
        AWS::Partition as "aws".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws"

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("cn-north-1", "123456789012"),
            ("cn-northwest-1", "987654321098"),
        ],
    )
    def test_china_region_derives_aws_cn_partition(self, region: str, account_id: str):
        """
        Property 15: For any China region, the resolver SHALL derive
        AWS::Partition as "aws-cn".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws-cn"

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-gov-west-1", "123456789012"),
            ("us-gov-east-1", "987654321098"),
        ],
    )
    def test_govcloud_region_derives_aws_us_gov_partition(self, region: str, account_id: str):
        """
        Property 15: For any GovCloud region, the resolver SHALL derive
        AWS::Partition as "aws-us-gov".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == "aws-us-gov"

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-east-1", "123456789012"),
            ("eu-central-1", "999888777666"),
            ("sa-east-1", "555444333222"),
        ],
    )
    def test_standard_region_derives_amazonaws_com_url_suffix(self, region: str, account_id: str):
        """
        Property 15: For any standard AWS region, the resolver SHALL derive
        AWS::URLSuffix as "amazonaws.com".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "amazonaws.com"

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("cn-north-1", "123456789012"),
            ("cn-northwest-1", "987654321098"),
        ],
    )
    def test_china_region_derives_amazonaws_com_cn_url_suffix(self, region: str, account_id: str):
        """
        Property 15: For any China region, the resolver SHALL derive
        AWS::URLSuffix as "amazonaws.com.cn".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "amazonaws.com.cn"

    @pytest.mark.parametrize(
        "region, account_id",
        [
            ("us-gov-west-1", "123456789012"),
            ("us-gov-east-1", "987654321098"),
        ],
    )
    def test_govcloud_region_derives_amazonaws_com_url_suffix(self, region: str, account_id: str):
        """
        Property 15: For any GovCloud region, the resolver SHALL derive
        AWS::URLSuffix as "amazonaws.com".

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id=account_id),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == "amazonaws.com"

    @pytest.mark.parametrize(
        "region, expected_partition",
        [
            ("us-east-1", "aws"),
            ("eu-west-1", "aws"),
            ("cn-north-1", "aws-cn"),
            ("cn-northwest-1", "aws-cn"),
            ("us-gov-west-1", "aws-us-gov"),
            ("us-gov-east-1", "aws-us-gov"),
        ],
    )
    def test_partition_derivation_consistent_with_region_prefix(self, region: str, expected_partition: str):
        """
        Property 15: For any AWS region, the derived partition SHALL be consistent
        with the region's prefix.

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id="123456789012"),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::Partition"})
        assert result == expected_partition

    @pytest.mark.parametrize(
        "region, expected_url_suffix",
        [
            ("us-east-1", "amazonaws.com"),
            ("eu-west-1", "amazonaws.com"),
            ("cn-north-1", "amazonaws.com.cn"),
            ("cn-northwest-1", "amazonaws.com.cn"),
            ("us-gov-west-1", "amazonaws.com"),
            ("us-gov-east-1", "amazonaws.com"),
        ],
    )
    def test_url_suffix_derivation_consistent_with_region_prefix(self, region: str, expected_url_suffix: str):
        """
        Property 15: For any AWS region, the derived URL suffix SHALL be consistent
        with the region's prefix.

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id="123456789012"),
        )
        resolver = FnRefResolver(context, None)
        result = resolver.resolve({"Ref": "AWS::URLSuffix"})
        assert result == expected_url_suffix

    @pytest.mark.parametrize(
        "region, expected_partition, expected_url_suffix",
        [
            ("us-east-1", "aws", "amazonaws.com"),
            ("cn-north-1", "aws-cn", "amazonaws.com.cn"),
            ("us-gov-west-1", "aws-us-gov", "amazonaws.com"),
        ],
    )
    def test_partition_and_url_suffix_both_derived_correctly(
        self, region: str, expected_partition: str, expected_url_suffix: str
    ):
        """
        Property 15: For any AWS region, both AWS::Partition and AWS::URLSuffix
        SHALL be correctly derived when not explicitly provided.

        **Validates: Requirements 9.4**
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(region=region, account_id="123456789012"),
        )

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnRefResolver)

        template_value = {
            "partition": {"Ref": "AWS::Partition"},
            "url_suffix": {"Ref": "AWS::URLSuffix"},
        }

        result = orchestrator.resolve_value(template_value)

        assert result["partition"] == expected_partition
        assert result["url_suffix"] == expected_url_suffix


# =============================================================================
# Tests for Ref with nested intrinsic functions (e.g., Fn::Sub inside Ref)
# =============================================================================


class TestFnRefResolverNestedIntrinsic:
    """Tests for FnRefResolver when Ref target is a nested intrinsic function.

    This covers the case where Fn::ForEach expansion produces constructs like
    {"Ref": {"Fn::Sub": "uploadsBucket"}} which need to be resolved to
    {"Ref": "uploadsBucket"}.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
            parameter_values={"MyParam": "my-value"},
            pseudo_parameters=PseudoParameterValues(
                region="us-east-1",
                account_id="123456789012",
            ),
            parsed_template=ParsedTemplate(
                parameters={"MyParam": {"Type": "String"}},
                resources={"uploadsBucket": {"Type": "AWS::S3::Bucket"}},
            ),
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        from samcli.lib.cfn_language_extensions.resolvers.fn_sub import FnSubResolver

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnRefResolver)
        orchestrator.register_resolver(FnSubResolver)
        return orchestrator

    def test_ref_with_nested_fn_sub_resolves_to_resource_ref(self, orchestrator: IntrinsicResolver):
        """Ref containing Fn::Sub that resolves to a resource name should produce {"Ref": "resourceName"}."""
        value = {"Ref": {"Fn::Sub": "uploadsBucket"}}
        result = orchestrator.resolve_value(value)
        assert result == {"Ref": "uploadsBucket"}

    def test_ref_with_nested_fn_sub_resolves_to_parameter(self, orchestrator: IntrinsicResolver):
        """Ref containing Fn::Sub that resolves to a parameter name should resolve the parameter value."""
        value = {"Ref": {"Fn::Sub": "MyParam"}}
        result = orchestrator.resolve_value(value)
        assert result == "my-value"

    def test_ref_with_nested_fn_sub_resolves_to_pseudo_parameter(self, orchestrator: IntrinsicResolver):
        """Ref containing Fn::Sub that resolves to a pseudo-parameter should resolve its value."""
        value = {"Ref": {"Fn::Sub": "AWS::Region"}}
        result = orchestrator.resolve_value(value)
        assert result == "us-east-1"

    def test_ref_with_nested_fn_sub_preserves_unresolved_pseudo_parameter(self, orchestrator: IntrinsicResolver):
        """Ref containing Fn::Sub that resolves to a pseudo-parameter without value should preserve it."""
        value = {"Ref": {"Fn::Sub": "AWS::StackName"}}
        result = orchestrator.resolve_value(value)
        assert result == {"Ref": "AWS::StackName"}

    def test_ref_with_nested_fn_sub_in_s3_event_structure(self, orchestrator: IntrinsicResolver):
        """End-to-end: S3 event Bucket property with nested Fn::Sub inside Ref."""
        value = {
            "S3Event": {
                "Type": "S3",
                "Properties": {
                    "Bucket": {"Ref": {"Fn::Sub": "uploadsBucket"}},
                    "Events": "s3:ObjectCreated:*",
                },
            }
        }
        result = orchestrator.resolve_value(value)
        assert result["S3Event"]["Properties"]["Bucket"] == {"Ref": "uploadsBucket"}
