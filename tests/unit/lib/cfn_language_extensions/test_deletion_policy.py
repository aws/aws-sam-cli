"""
Unit tests for the DeletionPolicyProcessor class.

Tests cover:
- String policy values (valid)
- Parameter reference resolution
- AWS::NoValue rejection
- Invalid policy value handling
- Error messages

Requirements:
    - 7.1: WHEN a resource has a DeletionPolicy attribute, THEN THE Processor
           SHALL resolve any parameter references in the policy value
    - 7.3: WHEN DeletionPolicy contains a Ref to a parameter, THEN THE Processor
           SHALL substitute the parameter's value
    - 7.4: WHEN DeletionPolicy resolves to AWS::NoValue, THEN THE Processor
           SHALL raise an Invalid_Template_Exception
    - 7.5: WHEN DeletionPolicy does not resolve to a valid string value, THEN
           THE Processor SHALL raise an Invalid_Template_Exception
"""

import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.processors.deletion_policy import DeletionPolicyProcessor
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestDeletionPolicyProcessorStringValues:
    """Tests for DeletionPolicyProcessor with string policy values."""

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_string_delete_policy_unchanged(self, processor: DeletionPolicyProcessor):
        """Test that string 'Delete' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": "Delete"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Delete"

    def test_string_retain_policy_unchanged(self, processor: DeletionPolicyProcessor):
        """Test that string 'Retain' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": "Retain"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Retain"

    def test_string_snapshot_policy_unchanged(self, processor: DeletionPolicyProcessor):
        """Test that string 'Snapshot' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyVolume": {"Type": "AWS::EC2::Volume", "DeletionPolicy": "Snapshot"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyVolume"]["DeletionPolicy"] == "Snapshot"

    def test_resource_without_deletion_policy_unchanged(self, processor: DeletionPolicyProcessor):
        """Test that resources without DeletionPolicy are unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}}}}
        )

        processor.process_template(context)

        assert "DeletionPolicy" not in context.fragment["Resources"]["MyBucket"]

    def test_multiple_resources_with_policies(self, processor: DeletionPolicyProcessor):
        """Test processing multiple resources with different policies."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "DeletionPolicy": "Retain"},
                    "Bucket2": {"Type": "AWS::S3::Bucket", "DeletionPolicy": "Delete"},
                    "Volume1": {"Type": "AWS::EC2::Volume", "DeletionPolicy": "Snapshot"},
                }
            }
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["DeletionPolicy"] == "Retain"
        assert context.fragment["Resources"]["Bucket2"]["DeletionPolicy"] == "Delete"
        assert context.fragment["Resources"]["Volume1"]["DeletionPolicy"] == "Snapshot"


class TestDeletionPolicyProcessorParameterResolution:
    """Tests for DeletionPolicyProcessor parameter reference resolution.

    Requirement 7.1: WHEN a resource has a DeletionPolicy attribute, THEN THE
    Processor SHALL resolve any parameter references in the policy value

    Requirement 7.3: WHEN DeletionPolicy contains a Ref to a parameter, THEN
    THE Processor SHALL substitute the parameter's value
    """

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_resolve_ref_to_parameter_retain(self, processor: DeletionPolicyProcessor):
        """Test resolving Ref to parameter with 'Retain' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}}},
            parameter_values={"PolicyParam": "Retain"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Retain"

    def test_resolve_ref_to_parameter_delete(self, processor: DeletionPolicyProcessor):
        """Test resolving Ref to parameter with 'Delete' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}}},
            parameter_values={"PolicyParam": "Delete"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Delete"

    def test_resolve_ref_to_parameter_snapshot(self, processor: DeletionPolicyProcessor):
        """Test resolving Ref to parameter with 'Snapshot' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyVolume": {"Type": "AWS::EC2::Volume", "DeletionPolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": "Snapshot"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyVolume"]["DeletionPolicy"] == "Snapshot"

    def test_resolve_ref_to_parameter_default_value(self, processor: DeletionPolicyProcessor):
        """Test resolving Ref to parameter using default value.

        Requirement 7.1: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}}},
            parameter_values={},
            parsed_template=ParsedTemplate(
                parameters={"PolicyParam": {"Type": "String", "Default": "Retain"}}, resources={}
            ),
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Retain"

    def test_resolve_multiple_refs_to_same_parameter(self, processor: DeletionPolicyProcessor):
        """Test resolving multiple Refs to the same parameter.

        Requirement 7.1: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}},
                    "Bucket2": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}},
                }
            },
            parameter_values={"PolicyParam": "Retain"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["DeletionPolicy"] == "Retain"
        assert context.fragment["Resources"]["Bucket2"]["DeletionPolicy"] == "Retain"

    def test_resolve_refs_to_different_parameters(self, processor: DeletionPolicyProcessor):
        """Test resolving Refs to different parameters.

        Requirement 7.1: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "BucketPolicy"}},
                    "Volume1": {"Type": "AWS::EC2::Volume", "DeletionPolicy": {"Ref": "VolumePolicy"}},
                }
            },
            parameter_values={"BucketPolicy": "Retain", "VolumePolicy": "Snapshot"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["DeletionPolicy"] == "Retain"
        assert context.fragment["Resources"]["Volume1"]["DeletionPolicy"] == "Snapshot"


class TestDeletionPolicyProcessorAwsNoValue:
    """Tests for DeletionPolicyProcessor AWS::NoValue rejection.

    Requirement 7.4: WHEN DeletionPolicy resolves to AWS::NoValue, THEN THE
    Processor SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_ref_to_aws_novalue_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that Ref to AWS::NoValue raises InvalidTemplateException.

        Requirement 7.4: Raise exception for AWS::NoValue references
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "AWS::NoValue"}}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "AWS::NoValue is not supported for DeletionPolicy or UpdateReplacePolicy" in str(exc_info.value)

    def test_aws_novalue_error_message_format(self, processor: DeletionPolicyProcessor):
        """Test that AWS::NoValue error message matches expected format.

        Requirement 7.4: Raise exception for AWS::NoValue references
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "AWS::NoValue"}}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        # Verify exact error message format
        error_message = str(exc_info.value)
        assert "AWS::NoValue" in error_message
        assert "DeletionPolicy" in error_message or "UpdateReplacePolicy" in error_message


class TestDeletionPolicyProcessorInvalidValues:
    """Tests for DeletionPolicyProcessor invalid value handling.

    Requirement 7.5: WHEN DeletionPolicy does not resolve to a valid string
    value, THEN THE Processor SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_list_policy_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that list policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": ["Retain", "Delete"]}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Every DeletionPolicy member must be a string" in str(exc_info.value)

    def test_integer_policy_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that integer policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": 123}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_boolean_policy_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that boolean policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": True}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_ref_to_nonexistent_parameter_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that Ref to non-existent parameter raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unresolvable references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "NonExistentParam"}}}
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)
        assert "MyBucket" in str(exc_info.value)

    def test_ref_to_resource_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that Ref to resource raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unresolvable references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "OtherResource"}},
                    "OtherResource": {"Type": "AWS::SNS::Topic"},
                }
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_parameter_resolves_to_non_string_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that parameter resolving to non-string raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string resolved values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}}},
            parameter_values={"PolicyParam": 123},  # Integer, not string
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_parameter_resolves_to_list_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that parameter resolving to list raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string resolved values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}}},
            parameter_values={"PolicyParam": ["Retain"]},  # List, not string
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_unsupported_intrinsic_function_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that unsupported intrinsic function raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Fn::Sub": "Retain"}}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_fn_if_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that Fn::If raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "DeletionPolicy": {"Fn::If": ["IsProd", "Retain", "Delete"]},
                    }
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)

    def test_fn_getatt_raises_exception(self, processor: DeletionPolicyProcessor):
        """Test that Fn::GetAtt raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "DeletionPolicy": {"Fn::GetAtt": ["SomeResource", "SomeAttribute"]},
                    }
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for DeletionPolicy" in str(exc_info.value)


class TestDeletionPolicyProcessorEdgeCases:
    """Tests for DeletionPolicyProcessor edge cases."""

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_empty_resources_section(self, processor: DeletionPolicyProcessor):
        """Test processing template with empty Resources section."""
        context = TemplateProcessingContext(fragment={"Resources": {}})

        # Should not raise any exception
        processor.process_template(context)

        assert context.fragment["Resources"] == {}

    def test_missing_resources_section(self, processor: DeletionPolicyProcessor):
        """Test processing template without Resources section."""
        context = TemplateProcessingContext(fragment={})

        # Should not raise any exception
        processor.process_template(context)

        assert "Resources" not in context.fragment

    def test_non_dict_resources_section(self, processor: DeletionPolicyProcessor):
        """Test processing template with non-dict Resources section."""
        context = TemplateProcessingContext(fragment={"Resources": "not a dict"})

        # Should not raise any exception (handled gracefully)
        processor.process_template(context)

    def test_non_dict_resource_definition(self, processor: DeletionPolicyProcessor):
        """Test processing template with non-dict resource definition."""
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": "not a dict"}})

        # Should not raise any exception (handled gracefully)
        processor.process_template(context)

    def test_null_deletion_policy(self, processor: DeletionPolicyProcessor):
        """Test processing resource with null DeletionPolicy."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": None}}}
        )

        # Should not raise any exception (None is skipped)
        processor.process_template(context)

        # DeletionPolicy should remain None
        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] is None

    def test_policy_name_attribute(self, processor: DeletionPolicyProcessor):
        """Test that POLICY_NAME attribute is correct."""
        assert processor.POLICY_NAME == "DeletionPolicy"

    def test_unsupported_pseudo_params_attribute(self, processor: DeletionPolicyProcessor):
        """Test that UNSUPPORTED_PSEUDO_PARAMS contains AWS::NoValue."""
        assert "AWS::NoValue" in processor.UNSUPPORTED_PSEUDO_PARAMS


class TestDeletionPolicyProcessorErrorMessages:
    """Tests for DeletionPolicyProcessor error message formatting."""

    @pytest.fixture
    def processor(self) -> DeletionPolicyProcessor:
        """Create a DeletionPolicyProcessor for testing."""
        return DeletionPolicyProcessor()

    def test_error_message_includes_resource_logical_id(self, processor: DeletionPolicyProcessor):
        """Test that error message includes the resource logical ID."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MySpecialBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "NonExistent"}}}
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "MySpecialBucket" in str(exc_info.value)

    def test_error_message_includes_policy_name(self, processor: DeletionPolicyProcessor):
        """Test that error message includes the policy name."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "NonExistent"}}}},
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "DeletionPolicy" in str(exc_info.value)


# =============================================================================
# Parametrized Tests for DeletionPolicy Parameter Resolution
# =============================================================================


class TestDeletionPolicyPropertyBasedTests:
    """
    Parametrized tests for DeletionPolicy parameter resolution.

    Feature: cfn-language-extensions-python, Property 12: Policy Parameter Resolution

    These tests validate that for any valid policy value (Delete, Retain, Snapshot)
    passed as a parameter, the DeletionPolicyProcessor correctly resolves the Ref
    to that value.

    **Validates: Requirements 7.1, 7.2**
    """

    @pytest.mark.parametrize(
        "policy_value,param_name,resource_id",
        [
            ("Delete", "DeletionParam", "MyBucket"),
            ("Retain", "RetainPolicy", "ProdDatabase"),
            ("Snapshot", "SnapParam", "Volume01"),
        ],
        ids=["delete-policy", "retain-policy", "snapshot-policy"],
    )
    def test_deletion_policy_resolves_parameter_ref_to_value(
        self,
        policy_value: str,
        param_name: str,
        resource_id: str,
    ):
        """
        Property 12: Policy Parameter Resolution

        For any valid policy value (Delete, Retain, Snapshot) passed as a parameter,
        the DeletionPolicyProcessor correctly resolves the Ref to that value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = DeletionPolicyProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {resource_id: {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": param_name}}}},
            parameter_values={param_name: policy_value},
        )

        processor.process_template(context)

        assert context.fragment["Resources"][resource_id]["DeletionPolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_value,param_name",
        [
            ("Delete", "DefaultDeleteParam"),
            ("Retain", "DefaultRetainParam"),
            ("Snapshot", "DefaultSnapParam"),
        ],
        ids=["default-delete", "default-retain", "default-snapshot"],
    )
    def test_deletion_policy_resolves_parameter_default_value(
        self,
        policy_value: str,
        param_name: str,
    ):
        """
        Property 12: Policy Parameter Resolution

        For any valid policy value (Delete, Retain, Snapshot) set as a parameter
        default, the DeletionPolicyProcessor correctly resolves the Ref to that value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = DeletionPolicyProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyResource": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": param_name}}}},
            parameter_values={},
            parsed_template=ParsedTemplate(
                parameters={param_name: {"Type": "String", "Default": policy_value}}, resources={}
            ),
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyResource"]["DeletionPolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_value,num_resources",
        [
            ("Delete", 1),
            ("Retain", 3),
            ("Snapshot", 5),
        ],
        ids=["delete-1-resource", "retain-3-resources", "snapshot-5-resources"],
    )
    def test_deletion_policy_resolves_same_parameter_across_multiple_resources(
        self,
        policy_value: str,
        num_resources: int,
    ):
        """
        Property 12: Policy Parameter Resolution

        For any valid policy value passed as a parameter, the DeletionPolicyProcessor
        correctly resolves the Ref to that value across multiple resources.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = DeletionPolicyProcessor()
        resources = {}
        for i in range(num_resources):
            resources[f"Resource{i}"] = {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "PolicyParam"}}

        context = TemplateProcessingContext(
            fragment={"Resources": resources}, parameter_values={"PolicyParam": policy_value}
        )

        processor.process_template(context)

        for i in range(num_resources):
            assert context.fragment["Resources"][f"Resource{i}"]["DeletionPolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_values",
        [
            ["Delete"],
            ["Retain", "Snapshot"],
            ["Delete", "Retain", "Snapshot"],
        ],
        ids=["single-value", "two-values", "three-values"],
    )
    def test_deletion_policy_resolves_different_parameters_to_different_values(
        self,
        policy_values: List[str],
    ):
        """
        Property 12: Policy Parameter Resolution

        For any set of valid policy values passed as different parameters, the
        DeletionPolicyProcessor correctly resolves each Ref to its respective value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = DeletionPolicyProcessor()
        resources = {}
        parameter_values = {}

        for i, policy_value in enumerate(policy_values):
            param_name = f"PolicyParam{i}"
            resources[f"Resource{i}"] = {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": param_name}}
            parameter_values[param_name] = policy_value

        context = TemplateProcessingContext(fragment={"Resources": resources}, parameter_values=parameter_values)

        processor.process_template(context)

        for i, policy_value in enumerate(policy_values):
            assert context.fragment["Resources"][f"Resource{i}"]["DeletionPolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_value",
        ["Delete", "Retain", "Snapshot"],
        ids=["string-delete", "string-retain", "string-snapshot"],
    )
    def test_deletion_policy_string_value_unchanged(
        self,
        policy_value: str,
    ):
        """
        Property 12: Policy Parameter Resolution

        For any valid policy value already set as a string, the DeletionPolicyProcessor
        leaves it unchanged.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = DeletionPolicyProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyResource": {"Type": "AWS::S3::Bucket", "DeletionPolicy": policy_value}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyResource"]["DeletionPolicy"] == policy_value
