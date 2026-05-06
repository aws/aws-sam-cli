"""
Unit tests for the models module.

Tests for ResolutionMode enum, PseudoParameterValues, ParsedTemplate,
and TemplateProcessingContext dataclasses.
"""

import pytest
from dataclasses import fields

from samcli.lib.cfn_language_extensions import (
    ResolutionMode,
    PseudoParameterValues,
    ParsedTemplate,
    TemplateProcessingContext,
)


class TestResolutionMode:
    """Tests for ResolutionMode enum."""

    def test_full_mode_value(self):
        """ResolutionMode.FULL should have value 'full'."""
        assert ResolutionMode.FULL.value == "full"

    def test_partial_mode_value(self):
        """ResolutionMode.PARTIAL should have value 'partial'."""
        assert ResolutionMode.PARTIAL.value == "partial"

    def test_enum_members(self):
        """ResolutionMode should have exactly FULL and PARTIAL members."""
        members = list(ResolutionMode)
        assert len(members) == 2
        assert ResolutionMode.FULL in members
        assert ResolutionMode.PARTIAL in members


class TestPseudoParameterValues:
    """Tests for PseudoParameterValues dataclass."""

    def test_required_fields(self):
        """PseudoParameterValues requires region and account_id."""
        pseudo = PseudoParameterValues(region="us-east-1", account_id="123456789012")
        assert pseudo.region == "us-east-1"
        assert pseudo.account_id == "123456789012"

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        pseudo = PseudoParameterValues(region="us-west-2", account_id="123456789012")
        assert pseudo.stack_id is None
        assert pseudo.stack_name is None
        assert pseudo.notification_arns is None
        assert pseudo.partition is None
        assert pseudo.url_suffix is None

    def test_all_fields_can_be_set(self):
        """All fields can be explicitly set."""
        pseudo = PseudoParameterValues(
            region="eu-west-1",
            account_id="987654321098",
            stack_id="arn:aws:cloudformation:eu-west-1:987654321098:stack/my-stack/guid",
            stack_name="my-stack",
            notification_arns=["arn:aws:sns:eu-west-1:987654321098:my-topic"],
            partition="aws",
            url_suffix="amazonaws.com",
        )
        assert pseudo.region == "eu-west-1"
        assert pseudo.account_id == "987654321098"
        assert pseudo.stack_id == "arn:aws:cloudformation:eu-west-1:987654321098:stack/my-stack/guid"
        assert pseudo.stack_name == "my-stack"
        assert pseudo.notification_arns == ["arn:aws:sns:eu-west-1:987654321098:my-topic"]
        assert pseudo.partition == "aws"
        assert pseudo.url_suffix == "amazonaws.com"

    def test_notification_arns_can_be_empty_list(self):
        """notification_arns can be an empty list."""
        pseudo = PseudoParameterValues(region="us-east-1", account_id="123456789012", notification_arns=[])
        assert pseudo.notification_arns == []

    def test_supports_aws_region_requirement(self):
        """Validates requirement 9.1: accepts AWS::Region value."""
        pseudo = PseudoParameterValues(region="ap-southeast-1", account_id="123456789012")
        assert pseudo.region == "ap-southeast-1"

    def test_supports_aws_account_id_requirement(self):
        """Validates requirement 9.1: accepts AWS::AccountId value."""
        pseudo = PseudoParameterValues(region="us-east-1", account_id="111122223333")
        assert pseudo.account_id == "111122223333"

    def test_supports_aws_stack_name_requirement(self):
        """Validates requirement 9.1: accepts AWS::StackName value."""
        pseudo = PseudoParameterValues(region="us-east-1", account_id="123456789012", stack_name="production-stack")
        assert pseudo.stack_name == "production-stack"

    def test_supports_aws_stack_id_requirement(self):
        """Validates requirement 9.1: accepts AWS::StackId value."""
        pseudo = PseudoParameterValues(
            region="us-east-1",
            account_id="123456789012",
            stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/test/guid",
        )
        assert pseudo.stack_id == "arn:aws:cloudformation:us-east-1:123456789012:stack/test/guid"

    def test_supports_aws_notification_arns_requirement(self):
        """Validates requirement 9.1: accepts AWS::NotificationARNs value."""
        arns = ["arn:aws:sns:us-east-1:123456789012:topic1", "arn:aws:sns:us-east-1:123456789012:topic2"]
        pseudo = PseudoParameterValues(region="us-east-1", account_id="123456789012", notification_arns=arns)
        assert pseudo.notification_arns == arns


class TestParsedTemplate:
    """Tests for ParsedTemplate dataclass."""

    def test_default_values(self):
        """All fields should have sensible defaults."""
        parsed = ParsedTemplate()
        assert parsed.aws_template_format_version is None
        assert parsed.description is None
        assert parsed.parameters == {}
        assert parsed.mappings == {}
        assert parsed.conditions == {}
        assert parsed.resources is None  # Resources can be None for validation
        assert parsed.outputs == {}
        assert parsed.transform is None

    def test_all_fields_can_be_set(self):
        """All fields can be explicitly set."""
        parsed = ParsedTemplate(
            aws_template_format_version="2010-09-09",
            description="Test template",
            parameters={"Env": {"Type": "String"}},
            mappings={"RegionMap": {"us-east-1": {"AMI": "ami-123"}}},
            conditions={"IsProd": {"Fn::Equals": [{"Ref": "Env"}, "prod"]}},
            resources={"Bucket": {"Type": "AWS::S3::Bucket"}},
            outputs={"BucketName": {"Value": {"Ref": "Bucket"}}},
            transform="AWS::Serverless-2016-10-31",
        )
        assert parsed.aws_template_format_version == "2010-09-09"
        assert parsed.description == "Test template"
        assert parsed.parameters == {"Env": {"Type": "String"}}
        assert parsed.mappings == {"RegionMap": {"us-east-1": {"AMI": "ami-123"}}}
        assert parsed.conditions == {"IsProd": {"Fn::Equals": [{"Ref": "Env"}, "prod"]}}
        assert parsed.resources == {"Bucket": {"Type": "AWS::S3::Bucket"}}
        assert parsed.outputs == {"BucketName": {"Value": {"Ref": "Bucket"}}}
        assert parsed.transform == "AWS::Serverless-2016-10-31"

    def test_transform_can_be_list(self):
        """Transform can be a list of transforms."""
        parsed = ParsedTemplate(transform=["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"])
        assert parsed.transform == ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]

    def test_dict_fields_are_independent(self):
        """Each instance should have independent dict fields."""
        parsed1 = ParsedTemplate()
        parsed2 = ParsedTemplate()

        parsed1.parameters["Key"] = "Value"

        assert "Key" not in parsed2.parameters


class TestTemplateProcessingContext:
    """Tests for TemplateProcessingContext dataclass."""

    def test_required_fragment_field(self):
        """TemplateProcessingContext requires fragment."""
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})
        assert context.fragment == {"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}

    def test_default_values(self):
        """Optional fields should have sensible defaults."""
        context = TemplateProcessingContext(fragment={})
        assert context.parameter_values == {}
        assert context.pseudo_parameters is None
        assert context.resolution_mode == ResolutionMode.PARTIAL
        assert context.parsed_template is None
        assert context.resolved_conditions == {}
        assert context.request_id == ""

    def test_all_fields_can_be_set(self):
        """All fields can be explicitly set."""
        pseudo = PseudoParameterValues(region="us-east-1", account_id="123456789012")
        parsed = ParsedTemplate(resources={"Bucket": {"Type": "AWS::S3::Bucket"}})

        context = TemplateProcessingContext(
            fragment={"Resources": {}},
            parameter_values={"Env": "prod"},
            pseudo_parameters=pseudo,
            resolution_mode=ResolutionMode.FULL,
            parsed_template=parsed,
            resolved_conditions={"IsProd": True},
            request_id="req-123",
        )

        assert context.fragment == {"Resources": {}}
        assert context.parameter_values == {"Env": "prod"}
        assert context.pseudo_parameters is pseudo
        assert context.resolution_mode == ResolutionMode.FULL
        assert context.parsed_template is parsed
        assert context.resolved_conditions == {"IsProd": True}
        assert context.request_id == "req-123"

    def test_default_resolution_mode_is_partial(self):
        """Default resolution mode should be PARTIAL for SAM integration."""
        context = TemplateProcessingContext(fragment={})
        assert context.resolution_mode == ResolutionMode.PARTIAL

    def test_provides_template_processing_context_class(self):
        """Validates requirement 12.2: provides TemplateProcessingContext class."""
        # The class exists and can be instantiated
        context = TemplateProcessingContext(fragment={"Resources": {}}, parameter_values={"Key": "Value"})
        assert isinstance(context, TemplateProcessingContext)

    def test_context_accepts_pseudo_parameters(self):
        """Validates requirement 9.1: context accepts pseudo-parameter values."""
        pseudo = PseudoParameterValues(
            region="us-west-2",
            account_id="123456789012",
            stack_name="my-stack",
            stack_id="arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid",
            notification_arns=["arn:aws:sns:us-west-2:123456789012:topic"],
        )
        context = TemplateProcessingContext(fragment={}, pseudo_parameters=pseudo)
        assert context.pseudo_parameters.region == "us-west-2"
        assert context.pseudo_parameters.account_id == "123456789012"
        assert context.pseudo_parameters.stack_name == "my-stack"
        assert context.pseudo_parameters.stack_id == "arn:aws:cloudformation:us-west-2:123456789012:stack/my-stack/guid"
        assert context.pseudo_parameters.notification_arns == ["arn:aws:sns:us-west-2:123456789012:topic"]

    def test_dict_fields_are_independent(self):
        """Each instance should have independent dict fields."""
        context1 = TemplateProcessingContext(fragment={})
        context2 = TemplateProcessingContext(fragment={})

        context1.parameter_values["Key"] = "Value"
        context1.resolved_conditions["Cond"] = True

        assert "Key" not in context2.parameter_values
        assert "Cond" not in context2.resolved_conditions

    def test_fragment_is_mutable(self):
        """Fragment should be mutable during processing."""
        context = TemplateProcessingContext(fragment={"Resources": {}})
        context.fragment["Resources"]["NewResource"] = {"Type": "AWS::S3::Bucket"}
        assert "NewResource" in context.fragment["Resources"]

    def test_parsed_template_can_be_set_during_processing(self):
        """parsed_template can be set during processing."""
        context = TemplateProcessingContext(fragment={})
        assert context.parsed_template is None

        context.parsed_template = ParsedTemplate(resources={"Bucket": {"Type": "AWS::S3::Bucket"}})
        assert context.parsed_template is not None
        assert "Bucket" in context.parsed_template.resources


class TestModuleExports:
    """Tests for module exports from __init__.py."""

    def test_resolution_mode_exported(self):
        """ResolutionMode should be exported from package."""
        from samcli.lib.cfn_language_extensions import ResolutionMode

        assert ResolutionMode.FULL.value == "full"

    def test_pseudo_parameter_values_exported(self):
        """PseudoParameterValues should be exported from package."""
        from samcli.lib.cfn_language_extensions import PseudoParameterValues

        pseudo = PseudoParameterValues(region="us-east-1", account_id="123")
        assert pseudo.region == "us-east-1"

    def test_parsed_template_exported(self):
        """ParsedTemplate should be exported from package."""
        from samcli.lib.cfn_language_extensions import ParsedTemplate

        parsed = ParsedTemplate()
        assert parsed.resources is None  # Resources can be None for validation

    def test_template_processing_context_exported(self):
        """TemplateProcessingContext should be exported from package."""
        from samcli.lib.cfn_language_extensions import TemplateProcessingContext

        context = TemplateProcessingContext(fragment={})
        assert context.fragment == {}
