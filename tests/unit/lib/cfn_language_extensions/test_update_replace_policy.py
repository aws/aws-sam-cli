"""
Unit tests for the UpdateReplacePolicyProcessor class.

Tests cover:
- String policy values (valid)
- Parameter reference resolution
- AWS::NoValue rejection
- Invalid policy value handling
- Error messages

Requirements:
    - 7.2: WHEN a resource has an UpdateReplacePolicy attribute, THEN THE Processor
           SHALL resolve any parameter references in the policy value
    - 7.3: WHEN UpdateReplacePolicy contains a Ref to a parameter, THEN THE Processor
           SHALL substitute the parameter's value
    - 7.4: WHEN UpdateReplacePolicy resolves to AWS::NoValue, THEN THE Processor
           SHALL raise an Invalid_Template_Exception
    - 7.5: WHEN UpdateReplacePolicy does not resolve to a valid string value, THEN
           THE Processor SHALL raise an Invalid_Template_Exception
"""

import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.processors.update_replace_policy import UpdateReplacePolicyProcessor
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestUpdateReplacePolicyProcessorStringValues:
    """Tests for UpdateReplacePolicyProcessor with string policy values."""

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_string_delete_policy_unchanged(self, processor: UpdateReplacePolicyProcessor):
        """Test that string 'Delete' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": "Delete"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Delete"

    def test_string_retain_policy_unchanged(self, processor: UpdateReplacePolicyProcessor):
        """Test that string 'Retain' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": "Retain"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Retain"

    def test_string_snapshot_policy_unchanged(self, processor: UpdateReplacePolicyProcessor):
        """Test that string 'Snapshot' policy is left unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyVolume": {"Type": "AWS::EC2::Volume", "UpdateReplacePolicy": "Snapshot"}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyVolume"]["UpdateReplacePolicy"] == "Snapshot"

    def test_resource_without_update_replace_policy_unchanged(self, processor: UpdateReplacePolicyProcessor):
        """Test that resources without UpdateReplacePolicy are unchanged."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}}}}
        )

        processor.process_template(context)

        assert "UpdateReplacePolicy" not in context.fragment["Resources"]["MyBucket"]

    def test_multiple_resources_with_policies(self, processor: UpdateReplacePolicyProcessor):
        """Test processing multiple resources with different policies."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": "Retain"},
                    "Bucket2": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": "Delete"},
                    "Volume1": {"Type": "AWS::EC2::Volume", "UpdateReplacePolicy": "Snapshot"},
                }
            }
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["UpdateReplacePolicy"] == "Retain"
        assert context.fragment["Resources"]["Bucket2"]["UpdateReplacePolicy"] == "Delete"
        assert context.fragment["Resources"]["Volume1"]["UpdateReplacePolicy"] == "Snapshot"


class TestUpdateReplacePolicyProcessorParameterResolution:
    """Tests for UpdateReplacePolicyProcessor parameter reference resolution.

    Requirement 7.2: WHEN a resource has an UpdateReplacePolicy attribute, THEN THE
    Processor SHALL resolve any parameter references in the policy value

    Requirement 7.3: WHEN UpdateReplacePolicy contains a Ref to a parameter, THEN
    THE Processor SHALL substitute the parameter's value
    """

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_resolve_ref_to_parameter_retain(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving Ref to parameter with 'Retain' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": "Retain"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Retain"

    def test_resolve_ref_to_parameter_delete(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving Ref to parameter with 'Delete' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": "Delete"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Delete"

    def test_resolve_ref_to_parameter_snapshot(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving Ref to parameter with 'Snapshot' value.

        Requirement 7.3: Substitute parameter value for Ref
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyVolume": {"Type": "AWS::EC2::Volume", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": "Snapshot"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyVolume"]["UpdateReplacePolicy"] == "Snapshot"

    def test_resolve_ref_to_parameter_default_value(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving Ref to parameter using default value.

        Requirement 7.2: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={},
            parsed_template=ParsedTemplate(
                parameters={"PolicyParam": {"Type": "String", "Default": "Retain"}}, resources={}
            ),
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Retain"

    def test_resolve_multiple_refs_to_same_parameter(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving multiple Refs to the same parameter.

        Requirement 7.2: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}},
                    "Bucket2": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}},
                }
            },
            parameter_values={"PolicyParam": "Retain"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["UpdateReplacePolicy"] == "Retain"
        assert context.fragment["Resources"]["Bucket2"]["UpdateReplacePolicy"] == "Retain"

    def test_resolve_refs_to_different_parameters(self, processor: UpdateReplacePolicyProcessor):
        """Test resolving Refs to different parameters.

        Requirement 7.2: Resolve parameter references in policy
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Bucket1": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "BucketPolicy"}},
                    "Volume1": {"Type": "AWS::EC2::Volume", "UpdateReplacePolicy": {"Ref": "VolumePolicy"}},
                }
            },
            parameter_values={"BucketPolicy": "Retain", "VolumePolicy": "Snapshot"},
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["Bucket1"]["UpdateReplacePolicy"] == "Retain"
        assert context.fragment["Resources"]["Volume1"]["UpdateReplacePolicy"] == "Snapshot"


class TestUpdateReplacePolicyProcessorAwsNoValue:
    """Tests for UpdateReplacePolicyProcessor AWS::NoValue rejection.

    Requirement 7.4: WHEN UpdateReplacePolicy resolves to AWS::NoValue, THEN THE
    Processor SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_ref_to_aws_novalue_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that Ref to AWS::NoValue raises InvalidTemplateException.

        Requirement 7.4: Raise exception for AWS::NoValue references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "AWS::NoValue"}}}
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "AWS::NoValue is not supported for DeletionPolicy or UpdateReplacePolicy" in str(exc_info.value)

    def test_aws_novalue_error_message_format(self, processor: UpdateReplacePolicyProcessor):
        """Test that AWS::NoValue error message matches expected format.

        Requirement 7.4: Raise exception for AWS::NoValue references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "AWS::NoValue"}}}
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        # Verify exact error message format
        error_message = str(exc_info.value)
        assert "AWS::NoValue" in error_message
        assert "DeletionPolicy" in error_message or "UpdateReplacePolicy" in error_message


class TestUpdateReplacePolicyProcessorInvalidValues:
    """Tests for UpdateReplacePolicyProcessor invalid value handling.

    Requirement 7.5: WHEN UpdateReplacePolicy does not resolve to a valid string
    value, THEN THE Processor SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_list_policy_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that list policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": ["Retain", "Delete"]}}
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Every UpdateReplacePolicy member must be a string" in str(exc_info.value)

    def test_integer_policy_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that integer policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": 123}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_boolean_policy_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that boolean policy value raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string values
        """
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": True}}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_ref_to_nonexistent_parameter_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that Ref to non-existent parameter raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unresolvable references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "NonExistentParam"}}
                }
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)
        assert "MyBucket" in str(exc_info.value)

    def test_ref_to_resource_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that Ref to resource raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unresolvable references
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "OtherResource"}},
                    "OtherResource": {"Type": "AWS::SNS::Topic"},
                }
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_parameter_resolves_to_non_string_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that parameter resolving to non-string raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string resolved values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": 123},  # Integer, not string
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_parameter_resolves_to_list_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that parameter resolving to list raises InvalidTemplateException.

        Requirement 7.5: Raise exception for non-string resolved values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}}
            },
            parameter_values={"PolicyParam": ["Retain"]},  # List, not string
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_unsupported_intrinsic_function_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that unsupported intrinsic function raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Fn::Sub": "Retain"}}}
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_fn_if_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that Fn::If raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "UpdateReplacePolicy": {"Fn::If": ["IsProd", "Retain", "Delete"]},
                    }
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)

    def test_fn_getatt_raises_exception(self, processor: UpdateReplacePolicyProcessor):
        """Test that Fn::GetAtt raises InvalidTemplateException.

        Requirement 7.5: Raise exception for unsupported expressions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "UpdateReplacePolicy": {"Fn::GetAtt": ["SomeResource", "SomeAttribute"]},
                    }
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Unsupported expression for UpdateReplacePolicy" in str(exc_info.value)


class TestUpdateReplacePolicyProcessorEdgeCases:
    """Tests for UpdateReplacePolicyProcessor edge cases."""

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_empty_resources_section(self, processor: UpdateReplacePolicyProcessor):
        """Test processing template with empty Resources section."""
        context = TemplateProcessingContext(fragment={"Resources": {}})

        # Should not raise any exception
        processor.process_template(context)

        assert context.fragment["Resources"] == {}

    def test_missing_resources_section(self, processor: UpdateReplacePolicyProcessor):
        """Test processing template without Resources section."""
        context = TemplateProcessingContext(fragment={})

        # Should not raise any exception
        processor.process_template(context)

        assert "Resources" not in context.fragment

    def test_non_dict_resources_section(self, processor: UpdateReplacePolicyProcessor):
        """Test processing template with non-dict Resources section."""
        context = TemplateProcessingContext(fragment={"Resources": "not a dict"})

        # Should not raise any exception (handled gracefully)
        processor.process_template(context)

    def test_non_dict_resource_definition(self, processor: UpdateReplacePolicyProcessor):
        """Test processing template with non-dict resource definition."""
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": "not a dict"}})

        # Should not raise any exception (handled gracefully)
        processor.process_template(context)

    def test_null_update_replace_policy(self, processor: UpdateReplacePolicyProcessor):
        """Test processing resource with null UpdateReplacePolicy."""
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": None}}}
        )

        # Should not raise any exception (None is skipped)
        processor.process_template(context)

        # UpdateReplacePolicy should remain None
        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] is None

    def test_policy_name_attribute(self, processor: UpdateReplacePolicyProcessor):
        """Test that POLICY_NAME attribute is correct."""
        assert processor.POLICY_NAME == "UpdateReplacePolicy"

    def test_unsupported_pseudo_params_attribute(self, processor: UpdateReplacePolicyProcessor):
        """Test that UNSUPPORTED_PSEUDO_PARAMS contains AWS::NoValue."""
        assert "AWS::NoValue" in processor.UNSUPPORTED_PSEUDO_PARAMS


class TestUpdateReplacePolicyProcessorErrorMessages:
    """Tests for UpdateReplacePolicyProcessor error message formatting."""

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_error_message_includes_resource_logical_id(self, processor: UpdateReplacePolicyProcessor):
        """Test that error message includes the resource logical ID."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MySpecialBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "NonExistent"}}
                }
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "MySpecialBucket" in str(exc_info.value)

    def test_error_message_includes_policy_name(self, processor: UpdateReplacePolicyProcessor):
        """Test that error message includes the policy name."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "NonExistent"}}}
            },
            parameter_values={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "UpdateReplacePolicy" in str(exc_info.value)


class TestUpdateReplacePolicyWithDeletionPolicy:
    """Tests for UpdateReplacePolicyProcessor when used alongside DeletionPolicy."""

    @pytest.fixture
    def processor(self) -> UpdateReplacePolicyProcessor:
        """Create an UpdateReplacePolicyProcessor for testing."""
        return UpdateReplacePolicyProcessor()

    def test_resource_with_both_policies(self, processor: UpdateReplacePolicyProcessor):
        """Test processing resource with both DeletionPolicy and UpdateReplacePolicy."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "DeletionPolicy": "Retain",
                        "UpdateReplacePolicy": {"Ref": "PolicyParam"},
                    }
                }
            },
            parameter_values={"PolicyParam": "Snapshot"},
        )

        processor.process_template(context)

        # UpdateReplacePolicy should be resolved
        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Snapshot"
        # DeletionPolicy should be unchanged (not processed by this processor)
        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == "Retain"

    def test_does_not_affect_deletion_policy(self, processor: UpdateReplacePolicyProcessor):
        """Test that UpdateReplacePolicyProcessor does not modify DeletionPolicy."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {
                        "Type": "AWS::S3::Bucket",
                        "DeletionPolicy": {"Ref": "SomeParam"},
                        "UpdateReplacePolicy": "Retain",
                    }
                }
            },
            parameter_values={"SomeParam": "Delete"},
        )

        processor.process_template(context)

        # DeletionPolicy should remain as Ref (not resolved by this processor)
        assert context.fragment["Resources"]["MyBucket"]["DeletionPolicy"] == {"Ref": "SomeParam"}
        # UpdateReplacePolicy should be unchanged (already a string)
        assert context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Retain"


# =============================================================================
# Parametrized Tests for UpdateReplacePolicy Parameter Resolution
# =============================================================================


class TestUpdateReplacePolicyParametrizedTests:
    """
    Parametrized tests for UpdateReplacePolicy parameter resolution.

    These tests validate that for any valid policy value (Delete, Retain, Snapshot)
    passed as a parameter, the UpdateReplacePolicyProcessor correctly resolves the Ref
    to that value.

    **Validates: Requirements 7.1, 7.2**
    """

    @pytest.mark.parametrize(
        "policy_value, param_name, resource_id",
        [
            ("Delete", "PolicyParam", "MyBucketResource"),
            ("Retain", "RetentionPolicy", "DataStore1"),
            ("Snapshot", "VolPolicy", "EbsVolume"),
        ],
    )
    def test_update_replace_policy_resolves_parameter_ref_to_value(
        self,
        policy_value: str,
        param_name: str,
        resource_id: str,
    ):
        """
        For any valid policy value (Delete, Retain, Snapshot) passed as a parameter,
        the UpdateReplacePolicyProcessor correctly resolves the Ref to that value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = UpdateReplacePolicyProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {resource_id: {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": param_name}}}
            },
            parameter_values={param_name: policy_value},
        )

        processor.process_template(context)

        assert context.fragment["Resources"][resource_id]["UpdateReplacePolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_value, param_name",
        [
            ("Delete", "DeletePolicyParam"),
            ("Retain", "RetainPolicyParam"),
            ("Snapshot", "SnapshotPolicyParam"),
        ],
    )
    def test_update_replace_policy_resolves_parameter_default_value(
        self,
        policy_value: str,
        param_name: str,
    ):
        """
        For any valid policy value set as a parameter default, the
        UpdateReplacePolicyProcessor correctly resolves the Ref to that value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = UpdateReplacePolicyProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"MyResource": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": param_name}}}
            },
            parameter_values={},
            parsed_template=ParsedTemplate(
                parameters={param_name: {"Type": "String", "Default": policy_value}}, resources={}
            ),
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyResource"]["UpdateReplacePolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_value, num_resources",
        [
            ("Delete", 1),
            ("Retain", 3),
            ("Snapshot", 5),
        ],
    )
    def test_update_replace_policy_resolves_same_parameter_across_multiple_resources(
        self,
        policy_value: str,
        num_resources: int,
    ):
        """
        For any valid policy value passed as a parameter, the UpdateReplacePolicyProcessor
        correctly resolves the Ref to that value across multiple resources.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = UpdateReplacePolicyProcessor()
        resources = {}
        for i in range(num_resources):
            resources[f"Resource{i}"] = {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "PolicyParam"}}

        context = TemplateProcessingContext(
            fragment={"Resources": resources}, parameter_values={"PolicyParam": policy_value}
        )

        processor.process_template(context)

        for i in range(num_resources):
            assert context.fragment["Resources"][f"Resource{i}"]["UpdateReplacePolicy"] == policy_value

    @pytest.mark.parametrize(
        "policy_values",
        [
            ["Delete"],
            ["Retain", "Snapshot"],
            ["Delete", "Retain", "Snapshot"],
        ],
    )
    def test_update_replace_policy_resolves_different_parameters_to_different_values(
        self,
        policy_values: List[str],
    ):
        """
        For any set of valid policy values passed as different parameters, the
        UpdateReplacePolicyProcessor correctly resolves each Ref to its respective value.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = UpdateReplacePolicyProcessor()
        resources = {}
        parameter_values = {}

        for i, policy_value in enumerate(policy_values):
            param_name = f"PolicyParam{i}"
            resources[f"Resource{i}"] = {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": param_name}}
            parameter_values[param_name] = policy_value

        context = TemplateProcessingContext(fragment={"Resources": resources}, parameter_values=parameter_values)

        processor.process_template(context)

        for i, policy_value in enumerate(policy_values):
            assert context.fragment["Resources"][f"Resource{i}"]["UpdateReplacePolicy"] == policy_value

    @pytest.mark.parametrize("policy_value", ["Delete", "Retain", "Snapshot"])
    def test_update_replace_policy_string_value_unchanged(
        self,
        policy_value: str,
    ):
        """
        For any valid policy value already set as a string, the UpdateReplacePolicyProcessor
        leaves it unchanged.

        **Validates: Requirements 7.1, 7.2**
        """
        processor = UpdateReplacePolicyProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"MyResource": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": policy_value}}}
        )

        processor.process_template(context)

        assert context.fragment["Resources"]["MyResource"]["UpdateReplacePolicy"] == policy_value
