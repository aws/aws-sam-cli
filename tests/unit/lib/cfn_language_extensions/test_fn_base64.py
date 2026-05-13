"""
Unit tests for the FnBase64Resolver class.

Tests cover:
- Basic Fn::Base64 functionality with literal strings
- Nested intrinsic function resolution
- Error handling for non-string inputs
- Integration with IntrinsicResolver orchestrator
- Edge cases (empty strings, unicode, special characters)

Requirements:
    - 10.8: THE Resolver SHALL support Fn::Base64 for base64 encoding strings
"""

import base64
import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
)
from samcli.lib.cfn_language_extensions.resolvers.base import (
    IntrinsicFunctionResolver,
    IntrinsicResolver,
)
from samcli.lib.cfn_language_extensions.resolvers.fn_base64 import FnBase64Resolver
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestFnBase64ResolverCanResolve:
    """Tests for FnBase64Resolver.can_resolve() method."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnBase64Resolver:
        """Create a FnBase64Resolver for testing."""
        return FnBase64Resolver(context, None)

    def test_can_resolve_fn_base64(self, resolver: FnBase64Resolver):
        """Test that can_resolve returns True for Fn::Base64."""
        value = {"Fn::Base64": "hello"}
        assert resolver.can_resolve(value) is True

    def test_cannot_resolve_other_functions(self, resolver: FnBase64Resolver):
        """Test that can_resolve returns False for other functions."""
        assert resolver.can_resolve({"Fn::Sub": "hello"}) is False
        assert resolver.can_resolve({"Fn::Join": [",", ["a", "b"]]}) is False
        assert resolver.can_resolve({"Ref": "MyParam"}) is False
        assert resolver.can_resolve({"Fn::Length": [1, 2, 3]}) is False

    def test_cannot_resolve_non_dict(self, resolver: FnBase64Resolver):
        """Test that can_resolve returns False for non-dict values."""
        assert resolver.can_resolve("string") is False
        assert resolver.can_resolve(123) is False
        assert resolver.can_resolve([1, 2, 3]) is False
        assert resolver.can_resolve(None) is False

    def test_cannot_resolve_multi_key_dict(self, resolver: FnBase64Resolver):
        """Test that can_resolve returns False for dicts with multiple keys."""
        assert resolver.can_resolve({"Fn::Base64": "hello", "extra": "key"}) is False

    def test_function_names_attribute(self, resolver: FnBase64Resolver):
        """Test that FUNCTION_NAMES contains Fn::Base64."""
        assert FnBase64Resolver.FUNCTION_NAMES == ["Fn::Base64"]


class TestFnBase64ResolverBasicFunctionality:
    """Tests for basic Fn::Base64 functionality.

    Requirement 10.8: THE Resolver SHALL support Fn::Base64 for base64 encoding strings
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnBase64Resolver:
        """Create a FnBase64Resolver for testing."""
        return FnBase64Resolver(context, None)

    def test_base64_encode_simple_string(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with simple string.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": "hello"}
        result = resolver.resolve(value)

        # "hello" in base64 is "aGVsbG8="
        assert result == "aGVsbG8="

    def test_base64_encode_empty_string(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with empty string returns empty string.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": ""}
        result = resolver.resolve(value)

        assert result == ""

    def test_base64_encode_with_spaces(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with string containing spaces.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": "hello world"}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "hello world"

    def test_base64_encode_with_newlines(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with string containing newlines.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": "line1\nline2\nline3"}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "line1\nline2\nline3"

    def test_base64_encode_with_special_characters(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with special characters.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": "!@#$%^&*()_+-=[]{}|;':\",./<>?"}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "!@#$%^&*()_+-=[]{}|;':\",./<>?"

    def test_base64_encode_with_unicode(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with unicode characters.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        value = {"Fn::Base64": "Hello 世界 🌍"}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "Hello 世界 🌍"

    def test_base64_encode_long_string(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with a longer string.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        long_string = "A" * 1000
        value = {"Fn::Base64": long_string}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == long_string

    def test_base64_encode_json_like_string(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with JSON-like string content.

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings

        This is a common use case in CloudFormation for encoding user data scripts.
        """
        json_string = '{"key": "value", "number": 123}'
        value = {"Fn::Base64": json_string}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == json_string

    def test_base64_encode_script_content(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with script content (common EC2 UserData use case).

        Requirement 10.8: Support Fn::Base64 for base64 encoding strings
        """
        script = """#!/bin/bash
echo "Hello World"
yum update -y
"""
        value = {"Fn::Base64": script}
        result = resolver.resolve(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == script


class TestFnBase64ResolverErrorHandling:
    """Tests for Fn::Base64 error handling.

    Fn::Base64 should raise InvalidTemplateException for non-string inputs.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def resolver(self, context: TemplateProcessingContext) -> FnBase64Resolver:
        """Create a FnBase64Resolver for testing."""
        return FnBase64Resolver(context, None)

    def test_non_string_integer_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with integer raises InvalidTemplateException."""
        value = {"Fn::Base64": 42}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_non_string_list_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with list raises InvalidTemplateException."""
        value = {"Fn::Base64": [1, 2, 3]}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_non_string_dict_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with dict raises InvalidTemplateException.

        Note: A dict that is not an intrinsic function should raise an error.
        """
        value = {"Fn::Base64": {"key": "value"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_non_string_none_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with None raises InvalidTemplateException."""
        value = {"Fn::Base64": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_non_string_boolean_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with boolean raises InvalidTemplateException."""
        value = {"Fn::Base64": True}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_non_string_float_raises_exception(self, resolver: FnBase64Resolver):
        """Test Fn::Base64 with float raises InvalidTemplateException."""
        value = {"Fn::Base64": 3.14}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_error_message_exact_format(self, resolver: FnBase64Resolver):
        """Test that error message matches exact expected format.

        The error message must be exactly "Fn::Base64 layout is incorrect" to match
        the Kotlin implementation's error messages.
        """
        value = {"Fn::Base64": 123}

        with pytest.raises(InvalidTemplateException) as exc_info:
            resolver.resolve(value)

        # Verify exact error message format
        assert str(exc_info.value) == "Fn::Base64 layout is incorrect"


class MockStringResolver(IntrinsicFunctionResolver):
    """A mock resolver that returns a string for testing nested resolution."""

    FUNCTION_NAMES = ["Fn::MockString"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """Return the argument as-is (for testing)."""
        return self.get_function_args(value)


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


class TestFnBase64ResolverNestedIntrinsics:
    """Tests for Fn::Base64 with nested intrinsic functions.

    Fn::Base64 should resolve nested intrinsics before encoding.
    """

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnBase64Resolver and MockStringResolver."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnBase64Resolver)
        orchestrator.register_resolver(MockStringResolver)
        return orchestrator

    def test_nested_intrinsic_resolved_first(self, orchestrator: IntrinsicResolver):
        """Test that nested intrinsic is resolved before base64 encoding."""
        value = {"Fn::Base64": {"Fn::MockString": "hello"}}
        result = orchestrator.resolve_value(value)

        # "hello" in base64 is "aGVsbG8="
        assert result == "aGVsbG8="

    def test_nested_intrinsic_empty_string(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to empty string."""
        value = {"Fn::Base64": {"Fn::MockString": ""}}
        result = orchestrator.resolve_value(value)

        assert result == ""

    def test_nested_intrinsic_non_string_raises_exception(self, orchestrator: IntrinsicResolver):
        """Test nested intrinsic that resolves to non-string raises exception."""
        value = {"Fn::Base64": {"Fn::MockString": 123}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            orchestrator.resolve_value(value)

        assert "Fn::Base64 layout is incorrect" in str(exc_info.value)

    def test_nested_ref_to_parameter(self):
        """Test Fn::Base64 with nested Ref to a parameter."""
        context = TemplateProcessingContext(fragment={"Resources": {}}, parameter_values={"MyParam": "parameter value"})

        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnBase64Resolver)
        orchestrator.register_resolver(MockRefResolver)

        value = {"Fn::Base64": {"Ref": "MyParam"}}
        result = orchestrator.resolve_value(value)

        # Verify by decoding
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "parameter value"


class TestFnBase64ResolverWithOrchestrator:
    """Tests for FnBase64Resolver integration with IntrinsicResolver orchestrator."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnBase64Resolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnBase64Resolver)
        return orchestrator

    def test_resolve_via_orchestrator(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Base64 through the orchestrator."""
        value = {"Fn::Base64": "hello"}
        result = orchestrator.resolve_value(value)

        assert result == "aGVsbG8="

    def test_resolve_in_nested_structure(self, orchestrator: IntrinsicResolver):
        """Test resolving Fn::Base64 in a nested template structure."""
        value = {
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {"UserData": {"Fn::Base64": "#!/bin/bash\necho hello"}},
                }
            }
        }
        result = orchestrator.resolve_value(value)

        user_data = result["Resources"]["MyInstance"]["Properties"]["UserData"]
        decoded = base64.b64decode(user_data).decode("utf-8")
        assert decoded == "#!/bin/bash\necho hello"

    def test_resolve_multiple_fn_base64(self, orchestrator: IntrinsicResolver):
        """Test resolving multiple Fn::Base64 in same structure."""
        value = {
            "first": {"Fn::Base64": "one"},
            "second": {"Fn::Base64": "two"},
            "third": {"Fn::Base64": "three"},
        }
        result = orchestrator.resolve_value(value)

        assert base64.b64decode(result["first"]).decode("utf-8") == "one"
        assert base64.b64decode(result["second"]).decode("utf-8") == "two"
        assert base64.b64decode(result["third"]).decode("utf-8") == "three"

    def test_fn_base64_in_list(self, orchestrator: IntrinsicResolver):
        """Test Fn::Base64 inside a list."""
        value = [
            {"Fn::Base64": "a"},
            {"Fn::Base64": "b"},
            {"Fn::Base64": "c"},
        ]
        result = orchestrator.resolve_value(value)

        decoded = [base64.b64decode(r).decode("utf-8") for r in result]
        assert decoded == ["a", "b", "c"]


class TestFnBase64ResolverPartialMode:
    """Tests for FnBase64Resolver in partial resolution mode.

    Fn::Base64 should always be resolved, even in partial mode.
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
        """Create an orchestrator in partial mode with FnBase64Resolver."""
        orchestrator = IntrinsicResolver(partial_context)
        orchestrator.register_resolver(FnBase64Resolver)
        return orchestrator

    def test_fn_base64_resolved_in_partial_mode(self, orchestrator: IntrinsicResolver):
        """Test that Fn::Base64 is resolved even in partial mode."""
        value = {"Fn::Base64": "hello"}
        result = orchestrator.resolve_value(value)

        assert result == "aGVsbG8="

    def test_fn_base64_with_preserved_intrinsic(self, orchestrator: IntrinsicResolver):
        """Test Fn::Base64 alongside preserved intrinsics in partial mode."""
        value = {
            "encoded": {"Fn::Base64": "hello"},
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }
        result = orchestrator.resolve_value(value)

        assert result == {
            "encoded": "aGVsbG8=",
            "preserved": {"Fn::GetAtt": ["MyBucket", "Arn"]},
        }


class TestFnBase64ResolverRealWorldScenarios:
    """Tests for real-world CloudFormation scenarios using Fn::Base64."""

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    @pytest.fixture
    def orchestrator(self, context: TemplateProcessingContext) -> IntrinsicResolver:
        """Create an orchestrator with FnBase64Resolver registered."""
        orchestrator = IntrinsicResolver(context)
        orchestrator.register_resolver(FnBase64Resolver)
        return orchestrator

    def test_ec2_userdata_script(self, orchestrator: IntrinsicResolver):
        """Test Fn::Base64 for EC2 UserData script encoding.

        This is the most common use case for Fn::Base64 in CloudFormation.
        """
        userdata_script = """#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
echo "Hello World" > /var/www/html/index.html
"""

        template = {
            "Resources": {
                "WebServer": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        "ImageId": "ami-12345678",
                        "InstanceType": "t2.micro",
                        "UserData": {"Fn::Base64": userdata_script},
                    },
                }
            }
        }

        result = orchestrator.resolve_value(template)

        # Verify the UserData is properly encoded
        encoded_userdata = result["Resources"]["WebServer"]["Properties"]["UserData"]
        decoded = base64.b64decode(encoded_userdata).decode("utf-8")
        assert decoded == userdata_script

    def test_lambda_inline_code(self, orchestrator: IntrinsicResolver):
        """Test Fn::Base64 for Lambda inline code encoding."""
        lambda_code = """
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
"""

        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Runtime": "python3.9",
                        "Handler": "index.handler",
                        "Code": {"ZipFile": {"Fn::Base64": lambda_code}},
                    },
                }
            }
        }

        result = orchestrator.resolve_value(template)

        # Verify the code is properly encoded
        encoded_code = result["Resources"]["MyFunction"]["Properties"]["Code"]["ZipFile"]
        decoded = base64.b64decode(encoded_code).decode("utf-8")
        assert decoded == lambda_code

    def test_launch_template_userdata(self, orchestrator: IntrinsicResolver):
        """Test Fn::Base64 for Launch Template UserData."""
        userdata = "#!/bin/bash\necho 'Starting instance...'"

        template = {
            "Resources": {
                "MyLaunchTemplate": {
                    "Type": "AWS::EC2::LaunchTemplate",
                    "Properties": {"LaunchTemplateData": {"UserData": {"Fn::Base64": userdata}}},
                }
            }
        }

        result = orchestrator.resolve_value(template)

        encoded = result["Resources"]["MyLaunchTemplate"]["Properties"]["LaunchTemplateData"]["UserData"]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == userdata
