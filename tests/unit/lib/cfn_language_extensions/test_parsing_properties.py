"""
Parametrized tests for the TemplateParsingProcessor.

These tests validate universal properties that should hold across representative inputs.

# Feature: cfn-language-extensions-python, Property 3: Template Parsing Round-Trip
"""

import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions import (
    TemplateParsingProcessor,
    TemplateProcessingContext,
    ParsedTemplate,
)


def parsed_template_to_dict(parsed: ParsedTemplate) -> Dict[str, Any]:
    """
    Convert a ParsedTemplate back to a dictionary representation.

    This function reconstructs the original template dictionary from
    the parsed template, preserving only non-empty/non-None sections.
    """
    result: Dict[str, Any] = {}

    if parsed.aws_template_format_version is not None:
        result["AWSTemplateFormatVersion"] = parsed.aws_template_format_version

    if parsed.description is not None:
        result["Description"] = parsed.description

    if parsed.parameters:
        result["Parameters"] = parsed.parameters

    if parsed.mappings:
        result["Mappings"] = parsed.mappings

    if parsed.conditions:
        result["Conditions"] = parsed.conditions

    if parsed.resources is not None:
        result["Resources"] = parsed.resources

    if parsed.outputs:
        result["Outputs"] = parsed.outputs

    if parsed.transform is not None:
        result["Transform"] = parsed.transform

    return result


# =============================================================================
# Concrete template examples for parametrized tests
# =============================================================================

MINIMAL_TEMPLATE = {
    "Resources": {
        "MyBucket": {
            "Type": "AWS::S3::Bucket",
            "Properties": {},
        }
    },
}

FULL_TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "A full test template",
    "Parameters": {
        "Env": {"Type": "String"},
    },
    "Mappings": {
        "RegionMap": {
            "useast1": {"AMI": "ami-12345"},
        },
    },
    "Conditions": {
        "IsProd": {"Fn::Equals": ["prod", "prod"]},
    },
    "Resources": {
        "Bucket": {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "my-bucket"},
        },
        "Topic": {
            "Type": "AWS::SNS::Topic",
            "Properties": {},
        },
    },
    "Outputs": {
        "BucketArn": {"Value": "arn:aws:s3:::my-bucket"},
    },
    "Transform": "AWS::Serverless-2016-10-31",
}

TEMPLATE_WITH_TRANSFORM_LIST = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Resources": {
        "Fn": {
            "Type": "AWS::Lambda::Function",
            "Properties": {"Runtime": "python3.12"},
        },
    },
    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
}


# =============================================================================
# Parametrized Tests
# =============================================================================


class TestTemplateParsingRoundTrip:
    """
    Property 3: Template Parsing Round-Trip

    For any valid CloudFormation template dictionary, parsing it into a
    ParsedTemplate and converting back to a dictionary SHALL produce an
    equivalent structure.

    **Validates: Requirements 2.1**
    """

    @pytest.mark.parametrize(
        "template",
        [MINIMAL_TEMPLATE, FULL_TEMPLATE, TEMPLATE_WITH_TRANSFORM_LIST],
        ids=["minimal", "full", "transform-list"],
    )
    def test_parsing_round_trip_preserves_structure(self, template: dict):
        """
        # Feature: cfn-language-extensions-python, Property 3: Template Parsing Round-Trip
        **Validates: Requirements 2.1**
        """
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context)

        assert context.parsed_template is not None
        reconstructed = parsed_template_to_dict(context.parsed_template)

        assert reconstructed.get("AWSTemplateFormatVersion") == template.get("AWSTemplateFormatVersion")
        assert reconstructed.get("Description") == template.get("Description")
        assert reconstructed.get("Parameters", {}) == template.get("Parameters", {})
        assert reconstructed.get("Mappings", {}) == template.get("Mappings", {})
        assert reconstructed.get("Conditions", {}) == template.get("Conditions", {})
        assert reconstructed.get("Resources") == template.get("Resources")
        assert reconstructed.get("Outputs", {}) == template.get("Outputs", {})
        assert reconstructed.get("Transform") == template.get("Transform")

    @pytest.mark.parametrize(
        "template",
        [MINIMAL_TEMPLATE, FULL_TEMPLATE, TEMPLATE_WITH_TRANSFORM_LIST],
        ids=["minimal", "full", "transform-list"],
    )
    def test_parsed_template_fields_match_input(self, template: dict):
        """
        Verify that each field in ParsedTemplate correctly captures the
        corresponding section from the input template.

        **Validates: Requirements 2.1**
        """
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context)
        parsed = context.parsed_template
        assert parsed is not None

        assert parsed.aws_template_format_version == template.get("AWSTemplateFormatVersion")
        assert parsed.description == template.get("Description")
        assert parsed.resources == template.get("Resources")
        assert parsed.transform == template.get("Transform")
        assert parsed.parameters == template.get("Parameters", {})
        assert parsed.mappings == template.get("Mappings", {})
        assert parsed.conditions == template.get("Conditions", {})
        assert parsed.outputs == template.get("Outputs", {})

    @pytest.mark.parametrize(
        "template",
        [MINIMAL_TEMPLATE, FULL_TEMPLATE, TEMPLATE_WITH_TRANSFORM_LIST],
        ids=["minimal", "full", "transform-list"],
    )
    def test_parsing_is_idempotent(self, template: dict):
        """
        Parsing a template twice should produce the same ParsedTemplate.

        **Validates: Requirements 2.1**
        """
        processor = TemplateParsingProcessor()
        context1 = TemplateProcessingContext(fragment=template.copy())
        context2 = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context1)
        processor.process_template(context2)

        parsed1 = context1.parsed_template
        parsed2 = context2.parsed_template
        assert parsed1 is not None
        assert parsed2 is not None

        assert parsed1.aws_template_format_version == parsed2.aws_template_format_version
        assert parsed1.description == parsed2.description
        assert parsed1.parameters == parsed2.parameters
        assert parsed1.mappings == parsed2.mappings
        assert parsed1.conditions == parsed2.conditions
        assert parsed1.resources == parsed2.resources
        assert parsed1.outputs == parsed2.outputs
        assert parsed1.transform == parsed2.transform


class TestMissingSectionsInitialization:
    """
    Property 4: Missing Sections Initialization

    For any template missing optional sections (Parameters, Conditions, Outputs,
    Mappings), the parser SHALL initialize them as empty dictionaries.

    **Validates: Requirements 2.6**
    """

    @pytest.mark.parametrize(
        "template,missing_sections",
        [
            (
                {"Resources": {"B": {"Type": "AWS::S3::Bucket", "Properties": {}}}},
                ["Parameters", "Mappings", "Conditions", "Outputs"],
            ),
            (
                {
                    "Resources": {"B": {"Type": "AWS::S3::Bucket", "Properties": {}}},
                    "Parameters": {"P": {"Type": "String"}},
                },
                ["Mappings", "Conditions", "Outputs"],
            ),
            (
                {
                    "AWSTemplateFormatVersion": "2010-09-09",
                    "Resources": {"B": {"Type": "AWS::S3::Bucket", "Properties": {}}},
                    "Outputs": {"O": {"Value": "val"}},
                },
                ["Parameters", "Mappings", "Conditions"],
            ),
        ],
        ids=["all-missing", "only-params-present", "only-outputs-present"],
    )
    def test_missing_sections_initialized_as_empty_dicts(self, template: dict, missing_sections: list):
        """
        # Feature: cfn-language-extensions-python, Property 4: Missing Sections Initialization
        **Validates: Requirements 2.6**
        """
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context)
        parsed = context.parsed_template
        assert parsed is not None

        assert isinstance(parsed.parameters, dict)
        assert isinstance(parsed.mappings, dict)
        assert isinstance(parsed.conditions, dict)
        assert isinstance(parsed.outputs, dict)

        if "Parameters" in missing_sections:
            assert parsed.parameters == {}
        if "Mappings" in missing_sections:
            assert parsed.mappings == {}
        if "Conditions" in missing_sections:
            assert parsed.conditions == {}
        if "Outputs" in missing_sections:
            assert parsed.outputs == {}

    @pytest.mark.parametrize(
        "resources",
        [
            {"Bucket": {"Type": "AWS::S3::Bucket", "Properties": {}}},
            {"Queue": {"Type": "AWS::SQS::Queue", "Properties": {"DelaySeconds": 5}}},
            {
                "Topic": {"Type": "AWS::SNS::Topic", "Properties": {}},
                "Sub": {"Type": "AWS::SNS::Subscription", "Properties": {}},
            },
        ],
        ids=["single-bucket", "queue-with-props", "two-resources"],
    )
    def test_minimal_template_initializes_all_optional_sections(self, resources: dict):
        """
        # Feature: cfn-language-extensions-python, Property 4: Missing Sections Initialization
        **Validates: Requirements 2.6**
        """
        template = {"Resources": resources}
        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context)
        parsed = context.parsed_template
        assert parsed is not None

        assert parsed.parameters == {}
        assert parsed.mappings == {}
        assert parsed.conditions == {}
        assert parsed.outputs == {}
        assert parsed.resources == resources

    @pytest.mark.parametrize(
        "include_params,include_mappings,include_conditions,include_outputs",
        [
            (False, False, False, False),
            (True, False, True, False),
            (True, True, True, True),
        ],
        ids=["none-present", "params-and-conditions", "all-present"],
    )
    def test_any_combination_of_missing_sections(
        self,
        include_params: bool,
        include_mappings: bool,
        include_conditions: bool,
        include_outputs: bool,
    ):
        """
        # Feature: cfn-language-extensions-python, Property 4: Missing Sections Initialization
        **Validates: Requirements 2.6**
        """
        resources = {"Res": {"Type": "AWS::S3::Bucket", "Properties": {}}}
        template: Dict[str, Any] = {"Resources": resources}

        expected_params: Dict[str, Any] = {}
        expected_mappings: Dict[str, Any] = {}
        expected_conditions: Dict[str, Any] = {}
        expected_outputs: Dict[str, Any] = {}

        if include_params:
            expected_params = {"TestParam": {"Type": "String"}}
            template["Parameters"] = expected_params

        if include_mappings:
            expected_mappings = {"TestMap": {"key1": {"subkey": "value"}}}
            template["Mappings"] = expected_mappings

        if include_conditions:
            expected_conditions = {"TestCondition": {"Fn::Equals": ["a", "b"]}}
            template["Conditions"] = expected_conditions

        if include_outputs:
            expected_outputs = {"TestOutput": {"Value": "test-value"}}
            template["Outputs"] = expected_outputs

        processor = TemplateParsingProcessor()
        context = TemplateProcessingContext(fragment=template.copy())

        processor.process_template(context)
        parsed = context.parsed_template
        assert parsed is not None

        assert parsed.parameters == expected_params
        assert parsed.mappings == expected_mappings
        assert parsed.conditions == expected_conditions
        assert parsed.outputs == expected_outputs
