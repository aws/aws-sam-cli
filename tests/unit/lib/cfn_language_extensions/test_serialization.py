"""
Unit tests for the serialization module.

Tests cover:
- JSON serialization functionality
- YAML serialization functionality
- Round-trip serialization (serialize then parse back)
- CloudFormation-specific YAML features (multi-line strings)
- Error handling for invalid inputs

Requirements:
    - 13.1: THE Package SHALL provide a function to serialize processed templates to JSON format
    - 13.2: THE Package SHALL provide a function to serialize processed templates to YAML format
    - 13.3: JSON serialization SHALL produce valid JSON that can be parsed back
    - 13.4: YAML serialization SHALL produce valid YAML that can be parsed back
"""

import json
import pytest
from typing import Any, Dict

import yaml

from samcli.lib.cfn_language_extensions.serialization import (
    serialize_to_json,
    serialize_to_yaml,
)


# =============================================================================
# Unit Tests for serialize_to_json
# =============================================================================


class TestSerializeToJsonBasicFunctionality:
    """Tests for basic JSON serialization functionality.

    Requirement 13.1: THE Package SHALL provide a function to serialize
    processed templates to JSON format
    """

    def test_serialize_empty_template(self):
        """Test serializing an empty template."""
        template: Dict[str, Any] = {}
        result = serialize_to_json(template)
        assert result == "{}"

    def test_serialize_minimal_template(self):
        """Test serializing a minimal CloudFormation template."""
        template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}
        result = serialize_to_json(template)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == template

    def test_serialize_full_template(self):
        """Test serializing a full CloudFormation template with all sections."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Test template",
            "Parameters": {"Environment": {"Type": "String", "Default": "dev"}},
            "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}},
            "Conditions": {"IsProd": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]}},
            "Resources": {"MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": {"Ref": "Environment"}}}},
            "Outputs": {"QueueUrl": {"Value": {"Fn::GetAtt": ["MyQueue", "QueueUrl"]}}},
        }
        result = serialize_to_json(template)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == template

    def test_serialize_with_intrinsic_functions(self):
        """Test serializing template with CloudFormation intrinsic functions."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": {"Fn::Sub": "${AWS::StackName}-function"},
                        "Environment": {
                            "Variables": {
                                "TABLE_NAME": {"Ref": "MyTable"},
                                "BUCKET_ARN": {"Fn::GetAtt": ["MyBucket", "Arn"]},
                            }
                        },
                    },
                }
            }
        }
        result = serialize_to_json(template)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == template

    def test_serialize_with_nested_structures(self):
        """Test serializing template with deeply nested structures."""
        template = {
            "Resources": {
                "MyResource": {
                    "Type": "AWS::CloudFormation::CustomResource",
                    "Properties": {"Level1": {"Level2": {"Level3": {"Level4": {"Value": "deep"}}}}},
                }
            }
        }
        result = serialize_to_json(template)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == template


class TestSerializeToJsonOptions:
    """Tests for JSON serialization options."""

    def test_serialize_with_indent(self):
        """Test serializing with custom indentation."""
        template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}

        # Default indent (2)
        result_default = serialize_to_json(template)
        assert "  " in result_default  # 2-space indent

        # Custom indent (4)
        result_4 = serialize_to_json(template, indent=4)
        assert "    " in result_4  # 4-space indent

        # No indent (compact)
        result_compact = serialize_to_json(template, indent=None)
        assert "\n" not in result_compact  # No newlines in compact mode

    def test_serialize_with_sort_keys(self):
        """Test serializing with sorted keys."""
        template = {"z_key": 1, "a_key": 2, "m_key": 3}

        # Without sorting
        result_unsorted = serialize_to_json(template, sort_keys=False)

        # With sorting
        result_sorted = serialize_to_json(template, sort_keys=True)

        # Both should be valid JSON
        assert json.loads(result_unsorted) == template
        assert json.loads(result_sorted) == template

        # Sorted version should have keys in alphabetical order
        assert result_sorted.index("a_key") < result_sorted.index("m_key")
        assert result_sorted.index("m_key") < result_sorted.index("z_key")

    def test_serialize_with_unicode(self):
        """Test serializing template with Unicode characters."""
        template = {
            "Resources": {
                "MyResource": {
                    "Type": "AWS::CloudFormation::CustomResource",
                    "Properties": {"Message": "Hello, 世界! 🌍"},
                }
            }
        }
        result = serialize_to_json(template)

        # Should preserve Unicode characters
        assert "世界" in result
        assert "🌍" in result

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == template


class TestSerializeToJsonRoundTrip:
    """Tests for JSON serialization round-trip.

    Requirement 13.3: JSON serialization SHALL produce valid JSON that can be parsed back
    """

    def test_round_trip_empty_template(self):
        """Test round-trip for empty template."""
        template: Dict[str, Any] = {}
        result = serialize_to_json(template)
        parsed = json.loads(result)
        assert parsed == template

    def test_round_trip_with_all_json_types(self):
        """Test round-trip with all JSON data types."""
        template = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
        result = serialize_to_json(template)
        parsed = json.loads(result)
        assert parsed == template

    def test_round_trip_complex_template(self):
        """Test round-trip for a complex CloudFormation template."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Description": "Complex test template",
            "Parameters": {
                "Environment": {"Type": "String", "Default": "dev"},
                "InstanceCount": {"Type": "Number", "Default": 1},
            },
            "Conditions": {"IsProd": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]}},
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": {"Fn::Sub": "${AWS::StackName}-queue"},
                        "Tags": [{"Key": "Environment", "Value": {"Ref": "Environment"}}],
                    },
                }
            },
            "Outputs": {
                "QueueUrl": {
                    "Value": {"Fn::GetAtt": ["MyQueue", "QueueUrl"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-queue-url"}},
                }
            },
        }
        result = serialize_to_json(template)
        parsed = json.loads(result)
        assert parsed == template


# =============================================================================
# Unit Tests for serialize_to_yaml
# =============================================================================


class TestSerializeToYamlBasicFunctionality:
    """Tests for basic YAML serialization functionality.

    Requirement 13.2: THE Package SHALL provide a function to serialize
    processed templates to YAML format
    """

    def test_serialize_empty_template(self):
        """Test serializing an empty template."""
        template: Dict[str, Any] = {}
        result = serialize_to_yaml(template)
        assert result.strip() == "{}"

    def test_serialize_minimal_template(self):
        """Test serializing a minimal CloudFormation template."""
        template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}
        result = serialize_to_yaml(template)

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_serialize_full_template(self):
        """Test serializing a full CloudFormation template with all sections."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Test template",
            "Parameters": {"Environment": {"Type": "String", "Default": "dev"}},
            "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-12345678"}}},
            "Conditions": {"IsProd": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]}},
            "Resources": {"MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": {"Ref": "Environment"}}}},
            "Outputs": {"QueueUrl": {"Value": {"Fn::GetAtt": ["MyQueue", "QueueUrl"]}}},
        }
        result = serialize_to_yaml(template)

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_serialize_with_intrinsic_functions(self):
        """Test serializing template with CloudFormation intrinsic functions."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": {"Fn::Sub": "${AWS::StackName}-function"},
                        "Environment": {
                            "Variables": {
                                "TABLE_NAME": {"Ref": "MyTable"},
                                "BUCKET_ARN": {"Fn::GetAtt": ["MyBucket", "Arn"]},
                            }
                        },
                    },
                }
            }
        }
        result = serialize_to_yaml(template)

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template


class TestSerializeToYamlMultiLineStrings:
    """Tests for YAML serialization of multi-line strings.

    CloudFormation templates often contain multi-line strings for inline code,
    policies, etc. These should be formatted using literal block scalar style.
    """

    def test_serialize_multiline_string(self):
        """Test that multi-line strings use literal block style."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "ZipFile": "import json\n\ndef handler(event, context):\n    return {'statusCode': 200}"
                        }
                    },
                }
            }
        }
        result = serialize_to_yaml(template)

        # Should use literal block style (|) for multi-line strings
        assert "|" in result

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_serialize_policy_document(self):
        """Test serializing a template with an IAM policy document."""
        template = {
            "Resources": {
                "MyRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"Service": "lambda.amazonaws.com"},
                                    "Action": "sts:AssumeRole",
                                }
                            ],
                        }
                    },
                }
            }
        }
        result = serialize_to_yaml(template)

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template


class TestSerializeToYamlOptions:
    """Tests for YAML serialization options."""

    def test_serialize_with_flow_style(self):
        """Test serializing with flow style (inline collections)."""
        template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}

        # Block style (default)
        result_block = serialize_to_yaml(template, default_flow_style=False)

        # Flow style
        result_flow = serialize_to_yaml(template, default_flow_style=True)

        # Both should be valid YAML
        assert yaml.safe_load(result_block) == template
        assert yaml.safe_load(result_flow) == template

        # Flow style should use inline format (curly braces)
        assert "{" in result_flow
        # Block style should use indentation (no curly braces for dicts)
        assert "Resources:" in result_block

    def test_serialize_with_sort_keys(self):
        """Test serializing with sorted keys."""
        template = {"z_key": 1, "a_key": 2, "m_key": 3}

        # Without sorting
        result_unsorted = serialize_to_yaml(template, sort_keys=False)

        # With sorting
        result_sorted = serialize_to_yaml(template, sort_keys=True)

        # Both should be valid YAML
        assert yaml.safe_load(result_unsorted) == template
        assert yaml.safe_load(result_sorted) == template

        # Sorted version should have keys in alphabetical order
        assert result_sorted.index("a_key") < result_sorted.index("m_key")
        assert result_sorted.index("m_key") < result_sorted.index("z_key")

    def test_serialize_with_unicode(self):
        """Test serializing template with Unicode characters."""
        template = {
            "Resources": {
                "MyResource": {
                    "Type": "AWS::CloudFormation::CustomResource",
                    "Properties": {"Message": "Hello, 世界! 🌍"},
                }
            }
        }
        result = serialize_to_yaml(template)

        # Should preserve Unicode characters
        assert "世界" in result
        assert "🌍" in result

        # Should be valid YAML
        parsed = yaml.safe_load(result)
        assert parsed == template


class TestSerializeToYamlRoundTrip:
    """Tests for YAML serialization round-trip.

    Requirement 13.4: YAML serialization SHALL produce valid YAML that can be parsed back
    """

    def test_round_trip_empty_template(self):
        """Test round-trip for empty template."""
        template: Dict[str, Any] = {}
        result = serialize_to_yaml(template)
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_round_trip_with_all_yaml_types(self):
        """Test round-trip with all YAML data types."""
        template = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
        result = serialize_to_yaml(template)
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_round_trip_complex_template(self):
        """Test round-trip for a complex CloudFormation template."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Description": "Complex test template",
            "Parameters": {
                "Environment": {"Type": "String", "Default": "dev"},
                "InstanceCount": {"Type": "Number", "Default": 1},
            },
            "Conditions": {"IsProd": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]}},
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": {"Fn::Sub": "${AWS::StackName}-queue"},
                        "Tags": [{"Key": "Environment", "Value": {"Ref": "Environment"}}],
                    },
                }
            },
            "Outputs": {
                "QueueUrl": {
                    "Value": {"Fn::GetAtt": ["MyQueue", "QueueUrl"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-queue-url"}},
                }
            },
        }
        result = serialize_to_yaml(template)
        parsed = yaml.safe_load(result)
        assert parsed == template

    def test_round_trip_with_multiline_strings(self):
        """Test round-trip for template with multi-line strings."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "ZipFile": "import json\n\ndef handler(event, context):\n    print('Hello')\n    return {'statusCode': 200}"
                        }
                    },
                }
            }
        }
        result = serialize_to_yaml(template)
        parsed = yaml.safe_load(result)
        assert parsed == template


# =============================================================================
# Integration Tests
# =============================================================================


class TestSerializationIntegration:
    """Integration tests for serialization functions."""

    def test_json_and_yaml_produce_equivalent_data(self):
        """Test that JSON and YAML serialization produce equivalent data when parsed."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": "test-queue",
                        "DelaySeconds": 5,
                        "Tags": [{"Key": "Environment", "Value": "test"}],
                    },
                }
            },
        }

        json_result = serialize_to_json(template)
        yaml_result = serialize_to_yaml(template)

        json_parsed = json.loads(json_result)
        yaml_parsed = yaml.safe_load(yaml_result)

        assert json_parsed == yaml_parsed == template

    def test_serialize_processed_template_with_expanded_foreach(self):
        """Test serializing a template that has been processed (ForEach expanded)."""
        # This represents a template after Fn::ForEach has been expanded
        template = {
            "Resources": {
                "QueueA": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": "queue-a"}},
                "QueueB": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": "queue-b"}},
                "QueueC": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": "queue-c"}},
            }
        }

        # Both formats should work
        json_result = serialize_to_json(template)
        yaml_result = serialize_to_yaml(template)

        assert json.loads(json_result) == template
        assert yaml.safe_load(yaml_result) == template

    def test_serialize_template_with_preserved_intrinsics(self):
        """Test serializing a template with preserved intrinsic functions."""
        # This represents a template processed in partial mode
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "my-function",
                        "Role": {"Fn::GetAtt": ["MyRole", "Arn"]},
                        "Environment": {"Variables": {"BUCKET_NAME": {"Ref": "MyBucket"}}},
                    },
                }
            }
        }

        # Both formats should preserve the intrinsic functions
        json_result = serialize_to_json(template)
        yaml_result = serialize_to_yaml(template)

        json_parsed = json.loads(json_result)
        yaml_parsed = yaml.safe_load(yaml_result)

        # Intrinsic functions should be preserved
        assert json_parsed["Resources"]["MyFunction"]["Properties"]["Role"] == {"Fn::GetAtt": ["MyRole", "Arn"]}
        assert yaml_parsed["Resources"]["MyFunction"]["Properties"]["Role"] == {"Fn::GetAtt": ["MyRole", "Arn"]}


# =============================================================================
# Parametrized Tests for Serialization Round-Trip
# =============================================================================


# Concrete template examples for parametrized tests
_SIMPLE_TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Resources": {
        "MyQueue": {
            "Type": "AWS::SQS::Queue",
            "Properties": {"QueueName": "test-queue", "DelaySeconds": 5},
        }
    },
}

_TEMPLATE_WITH_PARAMS = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "Template with parameters",
    "Parameters": {
        "Environment": {"Type": "String", "Default": "dev"},
        "InstanceCount": {"Type": "Number", "Default": 1},
    },
    "Resources": {
        "MyTopic": {"Type": "AWS::SNS::Topic", "Properties": {"DisplayName": "test-topic"}},
    },
    "Outputs": {
        "TopicArn": {"Value": "arn:aws:sns:us-east-1:123456789012:test-topic", "Description": "Topic ARN"},
    },
}

_TEMPLATE_WITH_INTRINSICS = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
    "Resources": {
        "MyFunction": {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionName": {"Fn::Sub": "${AWS::StackName}-function"},
                "Role": {"Fn::GetAtt": ["MyRole", "Arn"]},
                "Environment": {
                    "Variables": {
                        "TABLE_NAME": {"Ref": "MyTable"},
                        "REGION": {"Fn::Join": ["-", ["us", "east", "1"]]},
                    }
                },
            },
        }
    },
    "Outputs": {
        "FunctionArn": {"Value": {"Fn::GetAtt": ["MyFunction", "Arn"]}},
    },
}


class TestSerializationRoundTripParametrized:
    """
    Parametrized tests for Serialization Round-Trip.

    For any processed template dictionary, serializing to JSON and parsing back
    SHALL produce an equivalent dictionary; similarly for YAML serialization.

    **Validates: Requirements 13.3, 13.4**
    """

    @pytest.mark.parametrize(
        "template",
        [_SIMPLE_TEMPLATE, _TEMPLATE_WITH_PARAMS, _TEMPLATE_WITH_INTRINSICS],
        ids=["simple", "with_params", "with_intrinsics"],
    )
    def test_json_serialization_round_trip(self, template: Dict[str, Any]):
        """
        For any valid CloudFormation template structure, serializing to JSON
        and parsing back produces the original template.

        **Validates: Requirements 13.3, 13.4**
        """
        json_str = serialize_to_json(template)
        parsed = json.loads(json_str)
        assert parsed == template

    @pytest.mark.parametrize(
        "template",
        [_SIMPLE_TEMPLATE, _TEMPLATE_WITH_PARAMS, _TEMPLATE_WITH_INTRINSICS],
        ids=["simple", "with_params", "with_intrinsics"],
    )
    def test_yaml_serialization_round_trip(self, template: Dict[str, Any]):
        """
        For any valid CloudFormation template structure, serializing to YAML
        and parsing back produces the original template.

        **Validates: Requirements 13.3, 13.4**
        """
        yaml_str = serialize_to_yaml(template)
        parsed = yaml.safe_load(yaml_str)
        assert parsed == template

    @pytest.mark.parametrize(
        "template",
        [_SIMPLE_TEMPLATE, _TEMPLATE_WITH_PARAMS, _TEMPLATE_WITH_INTRINSICS],
        ids=["simple", "with_params", "with_intrinsics"],
    )
    def test_json_and_yaml_produce_equivalent_data(self, template: Dict[str, Any]):
        """
        JSON and YAML serialization of the same template produce equivalent
        data when parsed.

        **Validates: Requirements 13.3, 13.4**
        """
        json_str = serialize_to_json(template)
        yaml_str = serialize_to_yaml(template)

        json_parsed = json.loads(json_str)
        yaml_parsed = yaml.safe_load(yaml_str)

        assert json_parsed == yaml_parsed

    @pytest.mark.parametrize(
        "template",
        [_TEMPLATE_WITH_INTRINSICS],
        ids=["with_intrinsics"],
    )
    def test_json_round_trip_preserves_intrinsic_functions(self, template: Dict[str, Any]):
        """
        For any CloudFormation template with intrinsic functions, serializing
        to JSON and parsing back preserves the intrinsic function structure.

        **Validates: Requirements 13.3, 13.4**
        """
        json_str = serialize_to_json(template)
        parsed = json.loads(json_str)
        assert parsed == template

    @pytest.mark.parametrize(
        "template",
        [_TEMPLATE_WITH_INTRINSICS],
        ids=["with_intrinsics"],
    )
    def test_yaml_round_trip_preserves_intrinsic_functions(self, template: Dict[str, Any]):
        """
        For any CloudFormation template with intrinsic functions, serializing
        to YAML and parsing back preserves the intrinsic function structure.

        **Validates: Requirements 13.3, 13.4**
        """
        yaml_str = serialize_to_yaml(template)
        parsed = yaml.safe_load(yaml_str)
        assert parsed == template

    @pytest.mark.parametrize(
        "template, indent, sort_keys",
        [
            (_SIMPLE_TEMPLATE, None, False),
            (_SIMPLE_TEMPLATE, 4, True),
            (_TEMPLATE_WITH_PARAMS, 2, False),
        ],
        ids=["compact_unsorted", "indent4_sorted", "indent2_unsorted"],
    )
    def test_json_round_trip_with_options(self, template: Dict[str, Any], indent: int, sort_keys: bool):
        """
        For any valid CloudFormation template and any serialization options,
        serializing to JSON and parsing back produces the original template.

        **Validates: Requirements 13.3, 13.4**
        """
        json_str = serialize_to_json(template, indent=indent, sort_keys=sort_keys)
        parsed = json.loads(json_str)
        assert parsed == template

    @pytest.mark.parametrize(
        "template, default_flow_style, sort_keys",
        [
            (_SIMPLE_TEMPLATE, False, False),
            (_SIMPLE_TEMPLATE, True, True),
            (_TEMPLATE_WITH_PARAMS, False, True),
        ],
        ids=["block_unsorted", "flow_sorted", "block_sorted"],
    )
    def test_yaml_round_trip_with_options(self, template: Dict[str, Any], default_flow_style: bool, sort_keys: bool):
        """
        For any valid CloudFormation template and any serialization options,
        serializing to YAML and parsing back produces the original template.

        **Validates: Requirements 13.3, 13.4**
        """
        yaml_str = serialize_to_yaml(
            template,
            default_flow_style=default_flow_style,
            sort_keys=sort_keys,
        )
        parsed = yaml.safe_load(yaml_str)
        assert parsed == template
