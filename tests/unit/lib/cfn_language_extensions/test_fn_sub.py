"""
Unit tests for the FnSubResolver class.

Tests cover:
- Short form string substitution
- Long form with variable map
- Parameter and pseudo-parameter substitution
- Resource attribute preservation in partial mode
- Error handling for invalid inputs

Requirements:
    - 10.2: WHEN Fn::Sub is applied to a string with ${} placeholders, THEN THE
            Resolver SHALL substitute the placeholders with the corresponding values
            from parameters, pseudo-parameters, or the variable map
"""

import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
    PseudoParameterValues,
)
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicResolver
from samcli.lib.cfn_language_extensions.resolvers.fn_sub import FnSubResolver, PLACEHOLDER_PATTERN
from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnSubResolverCanResolve:
    """Tests for FnSubResolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver for testing."""
        return FnSubResolver(context, None)

    def test_can_resolve_fn_sub(self, resolver: FnSubResolver):
        """Test that can_resolve returns True for Fn::Sub."""
        value = {"Fn::Sub": "Hello ${Name}"}
        assert resolver.can_resolve(value) is True

    def test_can_resolve_fn_sub_long_form(self, resolver: FnSubResolver):
        """Test that can_resolve returns True for Fn::Sub long form."""
        value = {"Fn::Sub": ["Hello ${Name}", {"Name": "World"}]}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnSubResolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnSubResolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_function_names_attribute(self, resolver: FnSubResolver):
        """Test that FUNCTION_NAMES contains Fn::Sub."""
        assert FnSubResolver.FUNCTION_NAMES == ["Fn::Sub"]


class TestFnSubResolverShortForm:
    """Tests for Fn::Sub short form (string only).

    Requirement 10.2: WHEN Fn::Sub is applied to a string with ${} placeholders,
    THEN THE Resolver SHALL substitute the placeholders with the corresponding
    values from parameters, pseudo-parameters, or the variable map
    """

    @pytest.fixture
    def context_with_params(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Environment": "production",
                "BucketName": "my-bucket",
                "MaxCount": 10,
            },
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
                stack_name="my-stack",
            ),
        )

    @pytest.fixture
    def resolver(self, context_with_params: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver with parameter context."""
        return FnSubResolver(context_with_params, None)

    def test_substitute_single_parameter(self, resolver: FnSubResolver):
        """Test substituting a single parameter.

        Requirement 10.2: Substitute placeholders with parameter values
        """
        value = {"Fn::Sub": "Environment is ${Environment}"}
        result = resolver.resolve(value)
        assert result == "Environment is production"

    def test_substitute_multiple_parameters(self, resolver: FnSubResolver):
        """Test substituting multiple parameters.

        Requirement 10.2: Substitute placeholders with parameter values
        """
        value = {"Fn::Sub": "Bucket ${BucketName} in ${Environment}"}
        result = resolver.resolve(value)
        assert result == "Bucket my-bucket in production"

    def test_substitute_pseudo_parameter(self, resolver: FnSubResolver):
        """Test substituting pseudo-parameters.

        Requirement 10.2: Substitute placeholders with pseudo-parameter values
        """
        value = {"Fn::Sub": "Region is ${AWS::Region}"}
        result = resolver.resolve(value)
        assert result == "Region is us-west-2"

    def test_substitute_multiple_pseudo_parameters(self, resolver: FnSubResolver):
        """Test substituting multiple pseudo-parameters.

        Requirement 10.2: Substitute placeholders with pseudo-parameter values
        """
        value = {"Fn::Sub": "arn:aws:s3:::${AWS::AccountId}-${AWS::Region}-bucket"}
        result = resolver.resolve(value)
        assert result == "arn:aws:s3:::123456789012-us-west-2-bucket"

    def test_substitute_mixed_params_and_pseudo_params(self, resolver: FnSubResolver):
        """Test substituting both parameters and pseudo-parameters.

        Requirement 10.2: Substitute placeholders with values
        """
        value = {"Fn::Sub": "${BucketName}-${AWS::Region}-${Environment}"}
        result = resolver.resolve(value)
        assert result == "my-bucket-us-west-2-production"

    def test_substitute_integer_parameter(self, resolver: FnSubResolver):
        """Test substituting an integer parameter.

        Requirement 10.2: Substitute placeholders with parameter values
        """
        value = {"Fn::Sub": "Max count is ${MaxCount}"}
        result = resolver.resolve(value)
        assert result == "Max count is 10"

    def test_no_placeholders(self, resolver: FnSubResolver):
        """Test string with no placeholders."""
        value = {"Fn::Sub": "Hello World"}
        result = resolver.resolve(value)
        assert result == "Hello World"

    def test_empty_string(self, resolver: FnSubResolver):
        """Test empty string."""
        value = {"Fn::Sub": ""}
        result = resolver.resolve(value)
        assert result == ""


class TestFnSubResolverLongForm:
    """Tests for Fn::Sub long form (with variable map).

    Requirement 10.2: WHEN Fn::Sub is applied to a string with ${} placeholders,
    THEN THE Resolver SHALL substitute the placeholders with the corresponding
    values from parameters, pseudo-parameters, or the variable map
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameter values."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Environment": "production",
            },
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
            ),
        )

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver with context."""
        return FnSubResolver(context, None)

    def test_substitute_from_variable_map(self, resolver: FnSubResolver):
        """Test substituting from variable map.

        Requirement 10.2: Substitute placeholders with variable map values
        """
        value = {"Fn::Sub": ["Hello ${Name}", {"Name": "World"}]}
        result = resolver.resolve(value)
        assert result == "Hello World"

    def test_variable_map_overrides_parameter(self, resolver: FnSubResolver):
        """Test that variable map takes precedence over parameters.

        Requirement 10.2: Variable map should be checked first
        """
        value = {"Fn::Sub": ["Env is ${Environment}", {"Environment": "staging"}]}
        result = resolver.resolve(value)
        assert result == "Env is staging"

    def test_fallback_to_parameter_when_not_in_map(self, resolver: FnSubResolver):
        """Test fallback to parameters when not in variable map.

        Requirement 10.2: Fall back to parameters if not in variable map
        """
        value = {"Fn::Sub": ["${Name} in ${Environment}", {"Name": "App"}]}
        result = resolver.resolve(value)
        assert result == "App in production"

    def test_fallback_to_pseudo_parameter(self, resolver: FnSubResolver):
        """Test fallback to pseudo-parameters.

        Requirement 10.2: Fall back to pseudo-parameters
        """
        value = {"Fn::Sub": ["${Name} in ${AWS::Region}", {"Name": "App"}]}
        result = resolver.resolve(value)
        assert result == "App in us-west-2"

    def test_multiple_variables_from_map(self, resolver: FnSubResolver):
        """Test multiple variables from variable map.

        Requirement 10.2: Substitute multiple placeholders
        """
        value = {"Fn::Sub": ["${Greeting} ${Name}!", {"Greeting": "Hello", "Name": "World"}]}
        result = resolver.resolve(value)
        assert result == "Hello World!"

    def test_empty_variable_map(self, resolver: FnSubResolver):
        """Test with empty variable map."""
        value = {"Fn::Sub": ["Region is ${AWS::Region}", {}]}
        result = resolver.resolve(value)
        assert result == "Region is us-west-2"


class TestFnSubResolverResourceAttributes:
    """Tests for Fn::Sub with resource attribute references.

    Resource attributes (e.g., ${MyResource.Arn}) cannot be resolved locally
    and should be preserved in partial mode.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context in partial mode."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
            parameter_values={"BucketName": "my-bucket"},
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
            ),
        )

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver in partial mode."""
        return FnSubResolver(context, None)

    def test_preserve_resource_attribute(self, resolver: FnSubResolver):
        """Test that resource attributes are preserved."""
        value = {"Fn::Sub": "Bucket ARN is ${MyBucket.Arn}"}
        result = resolver.resolve(value)
        assert result == "Bucket ARN is ${MyBucket.Arn}"

    def test_preserve_resource_attribute_with_resolved_params(self, resolver: FnSubResolver):
        """Test mixed resolved params and preserved resource attributes."""
        value = {"Fn::Sub": "${BucketName} has ARN ${MyBucket.Arn}"}
        result = resolver.resolve(value)
        assert result == "my-bucket has ARN ${MyBucket.Arn}"

    def test_resource_attribute_in_variable_map(self, resolver: FnSubResolver):
        """Test that resource attribute in variable map is used."""
        value = {"Fn::Sub": ["ARN is ${BucketArn}", {"BucketArn": "arn:aws:s3:::my-bucket"}]}
        result = resolver.resolve(value)
        assert result == "ARN is arn:aws:s3:::my-bucket"

    def test_preserve_unresolved_resource_reference(self, resolver: FnSubResolver):
        """Test that unresolved resource references are preserved."""
        value = {"Fn::Sub": "Resource ID is ${MyResource}"}
        result = resolver.resolve(value)
        assert result == "Resource ID is ${MyResource}"


class TestFnSubResolverEscapeSyntax:
    """Tests for Fn::Sub escape syntax (${!Literal})."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal context."""
        return TemplateProcessingContext(fragment={"Resources": {}}, parameter_values={"Name": "World"})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver."""
        return FnSubResolver(context, None)

    def test_escape_literal(self, resolver: FnSubResolver):
        """Test escape syntax produces literal ${...}."""
        value = {"Fn::Sub": "Use ${!Literal} for literal"}
        result = resolver.resolve(value)
        assert result == "Use ${Literal} for literal"

    def test_escape_with_substitution(self, resolver: FnSubResolver):
        """Test escape syntax alongside substitution."""
        value = {"Fn::Sub": "Hello ${Name}, use ${!Variable} syntax"}
        result = resolver.resolve(value)
        assert result == "Hello World, use ${Variable} syntax"


class TestFnSubResolverPseudoParameters:
    """Tests for Fn::Sub with pseudo-parameters."""

    @pytest.fixture
    def context_with_pseudo_params(self) -> TemplateProcessingContext:
        """Create a context with all pseudo-parameters."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
                stack_id="arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid",
                stack_name="my-stack",
                notification_arns=["arn:aws:sns:us-west-2:123456789012:topic"],
            ),
        )

    @pytest.fixture
    def resolver(self, context_with_pseudo_params: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver with pseudo-parameters."""
        return FnSubResolver(context_with_pseudo_params, None)

    def test_substitute_aws_region(self, resolver: FnSubResolver):
        """Test substituting AWS::Region."""
        value = {"Fn::Sub": "Region: ${AWS::Region}"}
        result = resolver.resolve(value)
        assert result == "Region: us-west-2"

    def test_substitute_aws_account_id(self, resolver: FnSubResolver):
        """Test substituting AWS::AccountId."""
        value = {"Fn::Sub": "Account: ${AWS::AccountId}"}
        result = resolver.resolve(value)
        assert result == "Account: 123456789012"

    def test_substitute_aws_stack_name(self, resolver: FnSubResolver):
        """Test substituting AWS::StackName."""
        value = {"Fn::Sub": "Stack: ${AWS::StackName}"}
        result = resolver.resolve(value)
        assert result == "Stack: my-stack"

    def test_substitute_aws_stack_id(self, resolver: FnSubResolver):
        """Test substituting AWS::StackId."""
        value = {"Fn::Sub": "StackId: ${AWS::StackId}"}
        result = resolver.resolve(value)
        assert result == "StackId: arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid"

    def test_substitute_aws_partition(self, resolver: FnSubResolver):
        """Test substituting AWS::Partition (derived from region)."""
        value = {"Fn::Sub": "Partition: ${AWS::Partition}"}
        result = resolver.resolve(value)
        assert result == "Partition: aws"

    def test_substitute_aws_url_suffix(self, resolver: FnSubResolver):
        """Test substituting AWS::URLSuffix (derived from region)."""
        value = {"Fn::Sub": "Suffix: ${AWS::URLSuffix}"}
        result = resolver.resolve(value)
        assert result == "Suffix: amazonaws.com"

    def test_build_arn_with_pseudo_params(self, resolver: FnSubResolver):
        """Test building an ARN with pseudo-parameters."""
        value = {"Fn::Sub": "arn:${AWS::Partition}:s3:::${AWS::AccountId}-${AWS::Region}-bucket"}
        result = resolver.resolve(value)
        assert result == "arn:aws:s3:::123456789012-us-west-2-bucket"


class TestFnSubResolverPartitionDerivation:
    """Tests for AWS::Partition and AWS::URLSuffix derivation in Fn::Sub."""

    def test_partition_for_china_region(self):
        """Test partition derivation for China region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="cn-north-1",
                account_id="123456789012",
            ),
        )
        resolver = FnSubResolver(context, None)

        result = resolver.resolve({"Fn::Sub": "${AWS::Partition}"})
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
        resolver = FnSubResolver(context, None)

        result = resolver.resolve({"Fn::Sub": "${AWS::Partition}"})
        assert result == "aws-us-gov"

    def test_url_suffix_for_china_region(self):
        """Test URL suffix derivation for China region."""
        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            pseudo_parameters=PseudoParameterValues(
                region="cn-northwest-1",
                account_id="123456789012",
            ),
        )
        resolver = FnSubResolver(context, None)

        result = resolver.resolve({"Fn::Sub": "${AWS::URLSuffix}"})
        assert result == "amazonaws.com.cn"


class TestFnSubResolverPreserveUnresolved:
    """Tests for preserving unresolved placeholders."""

    @pytest.fixture
    def context_no_pseudo_params(self) -> TemplateProcessingContext:
        """Create a context without pseudo-parameters."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )

    @pytest.fixture
    def resolver(self, context_no_pseudo_params: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver without pseudo-parameters."""
        return FnSubResolver(context_no_pseudo_params, None)

    def test_preserve_pseudo_param_without_value(self, resolver: FnSubResolver):
        """Test that pseudo-parameters without values are preserved."""
        value = {"Fn::Sub": "Region: ${AWS::Region}"}
        result = resolver.resolve(value)
        assert result == "Region: ${AWS::Region}"

    def test_preserve_unknown_variable(self, resolver: FnSubResolver):
        """Test that unknown variables are preserved."""
        value = {"Fn::Sub": "Value: ${UnknownVar}"}
        result = resolver.resolve(value)
        assert result == "Value: ${UnknownVar}"


class TestFnSubResolverErrorHandling:
    """Tests for FnSubResolver error handling."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver."""
        return FnSubResolver(context, None)

    def test_invalid_type_raises_exception(self, resolver: FnSubResolver):
        """Test that non-string/list argument raises exception."""
        value = {"Fn::Sub": 123}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_dict_argument_raises_exception(self, resolver: FnSubResolver):
        """Test that dict argument raises exception."""
        value = {"Fn::Sub": {"key": "value"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_list_wrong_length_raises_exception(self, resolver: FnSubResolver):
        """Test that list with wrong length raises exception."""
        value = {"Fn::Sub": ["only one element"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_list_three_elements_raises_exception(self, resolver: FnSubResolver):
        """Test that list with three elements raises exception."""
        value = {"Fn::Sub": ["template", {"var": "val"}, "extra"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_list_non_string_template_raises_exception(self, resolver: FnSubResolver):
        """Test that non-string template in list raises exception."""
        value = {"Fn::Sub": [123, {"var": "val"}]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_list_non_dict_variable_map_raises_exception(self, resolver: FnSubResolver):
        """Test that non-dict variable map raises exception."""
        value = {"Fn::Sub": ["template", "not a dict"]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)

    def test_none_argument_raises_exception(self, resolver: FnSubResolver):
        """Test that None argument raises exception."""
        value = {"Fn::Sub": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Sub layout is incorrect" in str(exc_info.value)


class TestFnSubResolverWithOrchestrator:
    """Tests for FnSubResolver integration with IntrinsicResolver orchestrator."""

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
        """Create an orchestrator with FnSubResolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSubResolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Sub through the orchestrator."""
        value = {"Fn::Sub": "Env: ${Environment}"}
        result = orchestrator.resolve_value(value)
        assert result == "Env: production"

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Sub in a nested template structure."""
        value = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::Sub": "${BucketName}-${AWS::Region}"}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket-us-west-2"

    def test_resolve_multiple_fn_sub(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Sub in same structure."""
        value = {
            "name": {"Fn::Sub": "${BucketName}"},
            "region": {"Fn::Sub": "${AWS::Region}"},
            "combined": {"Fn::Sub": "${BucketName}-${AWS::Region}"},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "name": "my-bucket",
            "region": "us-west-2",
            "combined": "my-bucket-us-west-2",
        }

    def test_fn_sub_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Sub inside a list."""
        value = [
            {"Fn::Sub": "${Environment}"},
            {"Fn::Sub": "${AWS::Region}"},
            {"Fn::Sub": "${BucketName}"},
        ]
        result = orchestrator.resolve_value(value)

        assert result == ["production", "us-west-2", "my-bucket"]


class TestFnSubResolverNestedIntrinsics:
    """Tests for Fn::Sub with nested intrinsic functions in variable map."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with parameters."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "Environment": "production",
                "Prefix": "app",
            },
            pseudo_parameters=PseudoParameterValues(
                region="us-west-2",
                account_id="123456789012",
            ),
        )

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnSubResolver and FnRefResolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnSubResolver)
        orchestrator.register_resolver(FnRefResolver)
        return orchestrator

    def test_nested_ref_in_variable_map(self, orchestrator: IntrinsicResolver):
        """Test Fn::Sub with Ref in variable map."""
        value = {"Fn::Sub": ["Name is ${Name}", {"Name": {"Ref": "Environment"}}]}
        result = orchestrator.resolve_value(value)
        assert result == "Name is production"

    def test_multiple_nested_refs_in_variable_map(self, orchestrator: IntrinsicResolver):
        """Test Fn::Sub with multiple Refs in variable map."""
        value = {"Fn::Sub": ["${Prefix}-${Env}", {"Prefix": {"Ref": "Prefix"}, "Env": {"Ref": "Environment"}}]}
        result = orchestrator.resolve_value(value)
        assert result == "app-production"


class TestFnSubResolverValueConversion:
    """Tests for value-to-string conversion in Fn::Sub."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a context with various parameter types."""
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={
                "StringParam": "hello",
                "IntParam": 42,
                "FloatParam": 3.14,
                "BoolTrue": True,
                "BoolFalse": False,
                "ListParam": ["a", "b", "c"],
            },
        )

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        """Create a FnSubResolver."""
        return FnSubResolver(context, None)

    def test_string_value(self, resolver: FnSubResolver):
        """Test string value substitution."""
        value = {"Fn::Sub": "Value: ${StringParam}"}
        result = resolver.resolve(value)
        assert result == "Value: hello"

    def test_integer_value(self, resolver: FnSubResolver):
        """Test integer value substitution."""
        value = {"Fn::Sub": "Value: ${IntParam}"}
        result = resolver.resolve(value)
        assert result == "Value: 42"

    def test_float_value(self, resolver: FnSubResolver):
        """Test float value substitution."""
        value = {"Fn::Sub": "Value: ${FloatParam}"}
        result = resolver.resolve(value)
        assert result == "Value: 3.14"

    def test_boolean_true_value(self, resolver: FnSubResolver):
        """Test boolean true value substitution."""
        value = {"Fn::Sub": "Value: ${BoolTrue}"}
        result = resolver.resolve(value)
        assert result == "Value: true"

    def test_boolean_false_value(self, resolver: FnSubResolver):
        """Test boolean false value substitution."""
        value = {"Fn::Sub": "Value: ${BoolFalse}"}
        result = resolver.resolve(value)
        assert result == "Value: false"

    def test_list_value(self, resolver: FnSubResolver):
        """Test list value substitution (joined with comma)."""
        value = {"Fn::Sub": "Value: ${ListParam}"}
        result = resolver.resolve(value)
        assert result == "Value: a,b,c"


class TestPlaceholderPattern:
    """Tests for the PLACEHOLDER_PATTERN regex."""

    def test_simple_placeholder(self):
        """Test matching simple placeholder."""
        match = PLACEHOLDER_PATTERN.search("${Name}")
        assert match is not None
        assert match.group(1) == "Name"

    def test_pseudo_parameter_placeholder(self):
        """Test matching pseudo-parameter placeholder."""
        match = PLACEHOLDER_PATTERN.search("${AWS::Region}")
        assert match is not None
        assert match.group(1) == "AWS::Region"

    def test_resource_attribute_placeholder(self):
        """Test matching resource attribute placeholder."""
        match = PLACEHOLDER_PATTERN.search("${MyBucket.Arn}")
        assert match is not None
        assert match.group(1) == "MyBucket.Arn"

    def test_escape_placeholder(self):
        """Test matching escape placeholder."""
        match = PLACEHOLDER_PATTERN.search("${!Literal}")
        assert match is not None
        assert match.group(1) == "!Literal"

    def test_multiple_placeholders(self):
        """Test finding all placeholders."""
        matches = PLACEHOLDER_PATTERN.findall("${A} and ${B} and ${C}")
        assert matches == ["A", "B", "C"]

    def test_no_placeholder(self):
        """Test no match for non-placeholder."""
        match = PLACEHOLDER_PATTERN.search("Hello World")
        assert match is None


class TestFnSubResolverGetAttStyleInVariableMap:
    """Tests for Fn::Sub with GetAtt-style references in variable map."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={},
        )

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnSubResolver:
        return FnSubResolver(context, None)

    def test_getatt_style_ref_in_variable_map(self, resolver: FnSubResolver):
        """Test Fn::Sub with GetAtt-style reference provided in variable map."""
        value = {
            "Fn::Sub": [
                "ARN is ${MyResource.Arn}",
                {"MyResource.Arn": "arn:aws:s3:::my-bucket"},
            ]
        }
        result = resolver.resolve(value)
        assert result == "ARN is arn:aws:s3:::my-bucket"
