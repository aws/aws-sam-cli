"""
Unit tests for the TemplateParsingProcessor.

Tests for template parsing and validation.
Validates requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6.
"""

import pytest

from samcli.lib.cfn_language_extensions import (
    TemplateParsingProcessor,
    TemplateProcessingContext,
    InvalidTemplateException,
    ParsedTemplate,
)


class TestTemplateParsingProcessor:
    """Tests for TemplateParsingProcessor class."""

    def test_parses_valid_template(self):
        """Requirement 2.1: Parse valid template into structured Template object."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={
                "AWSTemplateFormatVersion": "2010-09-09",
                "Description": "Test template",
                "Parameters": {"Env": {"Type": "String"}},
                "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-123"}}},
                "Conditions": {"IsProd": {"Fn::Equals": [{"Ref": "Env"}, "prod"]}},
                "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}},
                "Outputs": {"BucketName": {"Value": {"Ref": "Bucket"}}},
                "Transform": "AWS::Serverless-2016-10-31",
            }
        )

        processor.process_template(context)

        assert context.parsed_template is not None
        assert context.parsed_template.aws_template_format_version == "2010-09-09"
        assert context.parsed_template.description == "Test template"
        assert context.parsed_template.parameters == {"Env": {"Type": "String"}}
        assert context.parsed_template.mappings == {"RegionMap": {"us-east-1": {"AMI": "ami-123"}}}
        assert context.parsed_template.conditions == {"IsProd": {"Fn::Equals": [{"Ref": "Env"}, "prod"]}}
        assert context.parsed_template.resources == {"Bucket": {"Type": "AWS::S3::Bucket"}}
        assert context.parsed_template.outputs == {"BucketName": {"Value": {"Ref": "Bucket"}}}
        assert context.parsed_template.transform == "AWS::Serverless-2016-10-31"

    def test_parses_minimal_template(self):
        """Parse minimal template with only Resources section."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}})

        processor.process_template(context)

        assert context.parsed_template is not None
        assert context.parsed_template.resources == {"MyQueue": {"Type": "AWS::SQS::Queue"}}

    def test_null_resources_raises_exception(self):
        """Requirement 2.2: Null Resources section raises InvalidTemplateException."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": None})

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "The Resources section must not be null" in str(exc_info.value)

    def test_missing_resources_raises_exception(self):
        """Requirement 2.2: Missing Resources section raises InvalidTemplateException."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Parameters": {"Env": {"Type": "String"}}})

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "The Resources section must not be null" in str(exc_info.value)

    def test_null_output_raises_exception(self):
        """Requirement 2.3: Null Output raises InvalidTemplateException."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}, "Outputs": {"NullOutput": None}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "[/Outputs/NullOutput] 'null' values are not allowed" in str(exc_info.value)

    def test_null_resource_raises_exception(self):
        """Requirement 2.4: Null Resource raises InvalidTemplateException."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"ValidBucket": {"Type": "AWS::S3::Bucket"}, "NullResource": None}}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "[/Resources/NullResource] resource definition is malformed" in str(exc_info.value)

    def test_initializes_missing_parameters_as_empty_dict(self):
        """Requirement 2.6: Missing Parameters initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        processor.process_template(context)

        assert context.parsed_template.parameters == {}

    def test_initializes_missing_conditions_as_empty_dict(self):
        """Requirement 2.6: Missing Conditions initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        processor.process_template(context)

        assert context.parsed_template.conditions == {}

    def test_initializes_missing_outputs_as_empty_dict(self):
        """Requirement 2.6: Missing Outputs initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        processor.process_template(context)

        assert context.parsed_template.outputs == {}

    def test_initializes_missing_mappings_as_empty_dict(self):
        """Requirement 2.6: Missing Mappings initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        processor.process_template(context)

        assert context.parsed_template.mappings == {}

    def test_initializes_null_parameters_as_empty_dict(self):
        """Requirement 2.6: Null Parameters initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Parameters": None, "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}
        )

        processor.process_template(context)

        assert context.parsed_template.parameters == {}

    def test_initializes_null_conditions_as_empty_dict(self):
        """Requirement 2.6: Null Conditions initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Conditions": None, "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}
        )

        processor.process_template(context)

        assert context.parsed_template.conditions == {}

    def test_initializes_null_outputs_as_empty_dict(self):
        """Requirement 2.6: Null Outputs initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Outputs": None, "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}
        )

        processor.process_template(context)

        assert context.parsed_template.outputs == {}

    def test_initializes_null_mappings_as_empty_dict(self):
        """Requirement 2.6: Null Mappings initialized as empty dict."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Mappings": None, "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}
        )

        processor.process_template(context)

        assert context.parsed_template.mappings == {}

    def test_preserves_transform_as_string(self):
        """Transform can be a single string."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Transform": "AWS::Serverless-2016-10-31", "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}
        )

        processor.process_template(context)

        assert context.parsed_template.transform == "AWS::Serverless-2016-10-31"

    def test_preserves_transform_as_list(self):
        """Transform can be a list of transforms."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}},
            }
        )

        processor.process_template(context)

        assert context.parsed_template.transform == ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]

    def test_multiple_null_resources_reports_first(self):
        """When multiple resources are null, report the first one found."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "NullResource1": None,
                    "ValidResource": {"Type": "AWS::S3::Bucket"},
                    "NullResource2": None,
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        # Should raise for one of the null resources
        assert "resource definition is malformed" in str(exc_info.value)

    def test_multiple_null_outputs_reports_first(self):
        """When multiple outputs are null, report the first one found."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}},
                "Outputs": {"NullOutput1": None, "ValidOutput": {"Value": "test"}, "NullOutput2": None},
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        # Should raise for one of the null outputs
        assert "'null' values are not allowed" in str(exc_info.value)

    def test_empty_resources_is_valid(self):
        """Empty Resources dict is valid (no resources defined)."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment={"Resources": {}})

        processor.process_template(context)

        assert context.parsed_template.resources == {}

    def test_empty_outputs_is_valid(self):
        """Empty Outputs dict is valid."""
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(
            fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}, "Outputs": {}}
        )

        processor.process_template(context)

        assert context.parsed_template.outputs == {}

    def test_implements_template_processor_protocol(self):
        """TemplateParsingProcessor should implement TemplateProcessor protocol."""
        from samcli.lib.cfn_language_extensions import TemplateProcessor

        processor = TemplateParsingProcessor()
        assert isinstance(processor, TemplateProcessor)


class TestTemplateParsingProcessorIntegration:
    """Integration tests for TemplateParsingProcessor with pipeline."""

    def test_works_in_pipeline(self):
        """TemplateParsingProcessor should work in a ProcessingPipeline."""
        from samcli.lib.cfn_language_extensions import ProcessingPipeline

        processor = TemplateParsingProcessor()
        pipeline = ProcessingPipeline([processor])
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        result = pipeline.process_template(context)

        assert context.parsed_template is not None
        assert context.parsed_template.resources == {"Bucket": {"Type": "AWS::S3::Bucket"}}
        assert result == {"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}}

    def test_exception_propagates_through_pipeline(self):
        """InvalidTemplateException should propagate through pipeline."""
        from samcli.lib.cfn_language_extensions import ProcessingPipeline

        processor = TemplateParsingProcessor()
        pipeline = ProcessingPipeline([processor])
        context = TemplateProcessingContext(fragment={"Resources": None})

        with pytest.raises(InvalidTemplateException) as exc_info:
            pipeline.process_template(context)

        assert "The Resources section must not be null" in str(exc_info.value)


class TestModuleExports:
    """Tests for module exports."""

    def test_template_parsing_processor_exported_from_package(self):
        """TemplateParsingProcessor should be exported from main package."""
        from samcli.lib.cfn_language_extensions import TemplateParsingProcessor

        assert TemplateParsingProcessor is not None

    def test_template_parsing_processor_exported_from_processors(self):
        """TemplateParsingProcessor should be exported from processors module."""
        from samcli.lib.cfn_language_extensions.processors import TemplateParsingProcessor

        assert TemplateParsingProcessor is not None
