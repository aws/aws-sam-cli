"""
Unit tests for the CloudFormation Language Extensions public API.

This module tests the main process_template function and related API
components.

Requirements tested:
    - 12.1: process_template accepts a template dictionary and processing options
    - 12.4: Support both JSON and YAML template input formats
    - 12.5: Return the processed template as a Python dictionary
"""

import pytest
from typing import Any, Dict

from samcli.lib.cfn_language_extensions import (
    process_template,
    create_default_pipeline,
    create_default_intrinsic_resolver,
    InvalidTemplateException,
    ResolutionMode,
    PseudoParameterValues,
    TemplateProcessingContext,
)


class TestProcessTemplate:
    """Tests for the process_template function."""

    def test_process_template_returns_dict(self):
        """
        Requirement 12.5: process_template SHALL return the processed template
        as a Python dictionary.
        """
        template = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}

        result = process_template(template)

        assert isinstance(result, dict)
        assert "Resources" in result
        assert "MyBucket" in result["Resources"]

    def test_process_template_accepts_template_dict(self):
        """
        Requirement 12.1: process_template SHALL accept a template dictionary.
        """
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Test template",
            "Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}},
        }

        result = process_template(template)

        assert result["AWSTemplateFormatVersion"] == "2010-09-09"
        assert result["Description"] == "Test template"
        assert "MyQueue" in result["Resources"]

    def test_process_template_accepts_parameter_values(self):
        """
        Requirement 12.1: process_template SHALL accept processing options
        including parameter values.
        """
        template = {
            "Parameters": {"Environment": {"Type": "String", "Default": "dev"}},
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": "Environment"}}}
            },
        }

        result = process_template(template, parameter_values={"Environment": "prod"})

        # The Ref should be resolved to the parameter value
        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "prod"

    def test_process_template_accepts_pseudo_parameters(self):
        """
        Requirement 12.1: process_template SHALL accept processing options
        including pseudo-parameter values.
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::Sub": "bucket-${AWS::Region}"}},
                }
            }
        }

        pseudo_params = PseudoParameterValues(region="us-west-2", account_id="123456789012")

        result = process_template(template, pseudo_parameters=pseudo_params)

        # The pseudo-parameter should be resolved
        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "bucket-us-west-2"

    def test_process_template_accepts_resolution_mode(self):
        """
        Requirement 12.1: process_template SHALL accept processing options
        including resolution mode.
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::GetAtt": ["OtherResource", "Arn"]}},
                }
            }
        }

        # In PARTIAL mode, Fn::GetAtt should be preserved
        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        # Fn::GetAtt should be preserved in partial mode
        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == {"Fn::GetAtt": ["OtherResource", "Arn"]}

    def test_process_template_does_not_modify_input(self):
        """
        process_template SHALL NOT modify the input template dictionary.
        """
        template = {
            "Resources": {
                "Fn::ForEach::Topics": ["TopicName", ["A", "B"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
            }
        }

        # Make a copy to compare later
        original_template = {
            "Resources": {
                "Fn::ForEach::Topics": ["TopicName", ["A", "B"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
            }
        }

        process_template(template)

        # Original template should be unchanged
        assert template == original_template

    def test_process_template_expands_foreach(self):
        """
        process_template SHALL expand Fn::ForEach loops.
        """
        template = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Alerts", "Notifications"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        result = process_template(template)

        # ForEach should be expanded
        assert "TopicAlerts" in result["Resources"]
        assert "TopicNotifications" in result["Resources"]
        assert "Fn::ForEach::Topics" not in result["Resources"]

    def test_process_template_resolves_fn_length(self):
        """
        process_template SHALL resolve Fn::Length intrinsic function.
        """
        template = {
            "Resources": {
                "MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"DelaySeconds": {"Fn::Length": [1, 2, 3, 4, 5]}}}
            }
        }

        result = process_template(template)

        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == 5

    def test_process_template_resolves_fn_to_json_string(self):
        """
        process_template SHALL resolve Fn::ToJsonString intrinsic function.
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Environment": {"Fn::ToJsonString": {"key": "value"}}},
                }
            }
        }

        result = process_template(template)

        assert result["Resources"]["MyFunction"]["Properties"]["Environment"] == '{"key":"value"}'

    def test_process_template_resolves_fn_find_in_map(self):
        """
        process_template SHALL resolve Fn::FindInMap intrinsic function.
        """
        template = {
            "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-12345"}, "us-west-2": {"AMI": "ami-67890"}}},
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {"ImageId": {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]}},
                }
            },
        }

        result = process_template(template)

        assert result["Resources"]["MyInstance"]["Properties"]["ImageId"] == "ami-12345"

    def test_process_template_resolves_fn_find_in_map_with_default(self):
        """
        process_template SHALL resolve Fn::FindInMap with DefaultValue.
        """
        template = {
            "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-12345"}}},
            "Resources": {
                "MyInstance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        "ImageId": {
                            "Fn::FindInMap": [
                                "RegionMap",
                                "eu-west-1",  # Not in map
                                "AMI",
                                {"DefaultValue": "ami-default"},
                            ]
                        }
                    },
                }
            },
        }

        result = process_template(template)

        assert result["Resources"]["MyInstance"]["Properties"]["ImageId"] == "ami-default"

    def test_process_template_validates_deletion_policy(self):
        """
        process_template SHALL validate and resolve DeletionPolicy.
        """
        template = {
            "Parameters": {"Policy": {"Type": "String", "Default": "Retain"}},
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "DeletionPolicy": {"Ref": "Policy"}}},
        }

        result = process_template(template)

        assert result["Resources"]["MyBucket"]["DeletionPolicy"] == "Retain"

    def test_process_template_validates_update_replace_policy(self):
        """
        process_template SHALL validate and resolve UpdateReplacePolicy.
        """
        template = {
            "Parameters": {"Policy": {"Type": "String", "Default": "Delete"}},
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "UpdateReplacePolicy": {"Ref": "Policy"}}},
        }

        result = process_template(template)

        assert result["Resources"]["MyBucket"]["UpdateReplacePolicy"] == "Delete"

    def test_process_template_raises_for_null_resources(self):
        """
        process_template SHALL raise InvalidTemplateException for null Resources.
        """
        template = {"Resources": None}

        with pytest.raises(InvalidTemplateException) as exc_info:
            process_template(template)

        assert "The Resources section must not be null" in str(exc_info.value)

    def test_process_template_raises_for_invalid_foreach(self):
        """
        process_template SHALL raise InvalidTemplateException for invalid ForEach.
        """
        template = {"Resources": {"Fn::ForEach::Invalid": []}}  # Empty list is invalid ForEach layout

        with pytest.raises(InvalidTemplateException) as exc_info:
            process_template(template)

        assert "layout is incorrect" in str(exc_info.value)

    def test_process_template_with_nested_intrinsics(self):
        """
        process_template SHALL resolve nested intrinsic functions.
        """
        template = {
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {"DelaySeconds": {"Fn::Length": {"Fn::Split": [",", "a,b,c"]}}},
                }
            }
        }

        result = process_template(template)

        # Fn::Split produces ["a", "b", "c"], Fn::Length returns 3
        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == 3

    def test_process_template_with_fn_join(self):
        """
        process_template SHALL resolve Fn::Join intrinsic function.
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::Join": ["-", ["my", "bucket", "name"]]}},
                }
            }
        }

        result = process_template(template)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket-name"

    def test_process_template_with_fn_select(self):
        """
        process_template SHALL resolve Fn::Select intrinsic function.
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::Select": [1, ["first", "second", "third"]]}},
                }
            }
        }

        result = process_template(template)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "second"

    def test_process_template_with_fn_base64(self):
        """
        process_template SHALL resolve Fn::Base64 intrinsic function.
        """
        template = {
            "Resources": {
                "MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"UserData": {"Fn::Base64": "Hello World"}}}
            }
        }

        result = process_template(template)

        import base64

        expected = base64.b64encode(b"Hello World").decode("utf-8")
        assert result["Resources"]["MyInstance"]["Properties"]["UserData"] == expected


class TestCreateDefaultPipeline:
    """Tests for the create_default_pipeline function."""

    def test_create_default_pipeline_returns_pipeline(self):
        """
        create_default_pipeline SHALL return a ProcessingPipeline instance.
        """
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}})

        pipeline = create_default_pipeline(context)

        from samcli.lib.cfn_language_extensions.pipeline import ProcessingPipeline

        assert isinstance(pipeline, ProcessingPipeline)

    def test_create_default_pipeline_has_processors(self):
        """
        create_default_pipeline SHALL include all standard processors.
        """
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}})

        pipeline = create_default_pipeline(context)

        # Should have at least 5 processors
        assert len(pipeline.processors) >= 5


class TestCreateDefaultIntrinsicResolver:
    """Tests for the create_default_intrinsic_resolver function."""

    def test_create_default_intrinsic_resolver_returns_resolver(self):
        """
        create_default_intrinsic_resolver SHALL return an IntrinsicResolver.
        """
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}})

        resolver = create_default_intrinsic_resolver(context)

        from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicResolver

        assert isinstance(resolver, IntrinsicResolver)

    def test_create_default_intrinsic_resolver_has_resolvers(self):
        """
        create_default_intrinsic_resolver SHALL register all standard resolvers.
        """
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}})

        resolver = create_default_intrinsic_resolver(context)

        # Should have multiple resolvers registered
        assert len(resolver.resolvers) >= 10


class TestProcessTemplateIntegration:
    """Integration tests for process_template with complex templates."""

    def test_complex_template_with_multiple_features(self):
        """
        process_template SHALL handle templates with multiple language extensions.
        """
        template = {
            "Parameters": {"Environment": {"Type": "String", "Default": "dev"}},
            "Mappings": {"EnvConfig": {"dev": {"Retention": "7"}, "prod": {"Retention": "30"}}},
            "Resources": {
                "Fn::ForEach::Queues": [
                    "QueueName",
                    ["Orders", "Payments"],
                    {
                        "Queue${QueueName}": {
                            "Type": "AWS::SQS::Queue",
                            "Properties": {
                                "QueueName": {"Fn::Sub": "${QueueName}-${Environment}"},
                                "MessageRetentionPeriod": {
                                    "Fn::FindInMap": ["EnvConfig", {"Ref": "Environment"}, "Retention"]
                                },
                            },
                        }
                    },
                ]
            },
        }

        result = process_template(template)

        # ForEach should be expanded
        assert "QueueOrders" in result["Resources"]
        assert "QueuePayments" in result["Resources"]

        # Fn::Sub should be resolved
        assert result["Resources"]["QueueOrders"]["Properties"]["QueueName"] == "Orders-dev"
        assert result["Resources"]["QueuePayments"]["Properties"]["QueueName"] == "Payments-dev"

        # Fn::FindInMap should be resolved
        assert result["Resources"]["QueueOrders"]["Properties"]["MessageRetentionPeriod"] == "7"

    def test_template_with_conditions(self):
        """
        process_template SHALL handle templates with conditions.
        """
        template = {
            "Parameters": {"CreateBucket": {"Type": "String", "Default": "true"}},
            "Conditions": {"ShouldCreateBucket": {"Fn::Equals": [{"Ref": "CreateBucket"}, "true"]}},
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::If": ["ShouldCreateBucket", "my-bucket", "other-bucket"]}},
                }
            },
        }

        result = process_template(template)

        # Fn::If should be resolved based on condition
        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket"


class TestLoadTemplateFromJson:
    """Tests for the load_template_from_json function."""

    def test_load_template_from_json_returns_dict(self, tmp_path):
        """
        Requirement 12.4: load_template_from_json SHALL load a template from
        a JSON file and return it as a dictionary.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_json

        # Create a test JSON file
        template_content = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}},
        }
        json_file = tmp_path / "template.json"
        import json

        json_file.write_text(json.dumps(template_content))

        result = load_template_from_json(str(json_file))

        assert isinstance(result, dict)
        assert result["AWSTemplateFormatVersion"] == "2010-09-09"
        assert "MyBucket" in result["Resources"]

    def test_load_template_from_json_raises_for_missing_file(self, tmp_path):
        """
        load_template_from_json SHALL raise FileNotFoundError for missing files.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_json

        with pytest.raises(FileNotFoundError):
            load_template_from_json(str(tmp_path / "nonexistent.json"))

    def test_load_template_from_json_raises_for_invalid_json(self, tmp_path):
        """
        load_template_from_json SHALL raise JSONDecodeError for invalid JSON.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_json
        import json

        # Create an invalid JSON file
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_template_from_json(str(json_file))

    def test_load_template_from_json_handles_complex_template(self, tmp_path):
        """
        load_template_from_json SHALL handle complex templates with nested structures.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_json
        import json

        template_content = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Parameters": {"Environment": {"Type": "String", "Default": "dev"}},
            "Mappings": {"RegionMap": {"us-east-1": {"AMI": "ami-12345"}}},
            "Resources": {
                "MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"QueueName": {"Fn::Sub": "queue-${Environment}"}}}
            },
        }
        json_file = tmp_path / "complex.json"
        json_file.write_text(json.dumps(template_content))

        result = load_template_from_json(str(json_file))

        assert result["Parameters"]["Environment"]["Default"] == "dev"
        assert result["Mappings"]["RegionMap"]["us-east-1"]["AMI"] == "ami-12345"
        assert result["Resources"]["MyQueue"]["Properties"]["QueueName"] == {"Fn::Sub": "queue-${Environment}"}


class TestLoadTemplateFromYaml:
    """Tests for the load_template_from_yaml function."""

    def test_load_template_from_yaml_returns_dict(self, tmp_path):
        """
        Requirement 12.4: load_template_from_yaml SHALL load a template from
        a YAML file and return it as a dictionary.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_yaml

        # Create a test YAML file
        yaml_content = """
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
"""
        yaml_file = tmp_path / "template.yaml"
        yaml_file.write_text(yaml_content)

        result = load_template_from_yaml(str(yaml_file))

        assert isinstance(result, dict)
        assert result["AWSTemplateFormatVersion"] == "2010-09-09"
        assert "MyBucket" in result["Resources"]

    def test_load_template_from_yaml_raises_for_missing_file(self, tmp_path):
        """
        load_template_from_yaml SHALL raise FileNotFoundError for missing files.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_yaml

        with pytest.raises(FileNotFoundError):
            load_template_from_yaml(str(tmp_path / "nonexistent.yaml"))

    def test_load_template_from_yaml_raises_for_invalid_yaml(self, tmp_path):
        """
        load_template_from_yaml SHALL raise YAMLError for invalid YAML.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_yaml
        import yaml

        # Create an invalid YAML file
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("key: [invalid: yaml")

        with pytest.raises(yaml.YAMLError):
            load_template_from_yaml(str(yaml_file))

    def test_load_template_from_yaml_handles_complex_template(self, tmp_path):
        """
        load_template_from_yaml SHALL handle complex templates with nested structures.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_yaml

        yaml_content = """
AWSTemplateFormatVersion: "2010-09-09"
Parameters:
  Environment:
    Type: String
    Default: dev
Mappings:
  RegionMap:
    us-east-1:
      AMI: ami-12345
Resources:
  MyQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName:
        Fn::Sub: "queue-${Environment}"
"""
        yaml_file = tmp_path / "complex.yaml"
        yaml_file.write_text(yaml_content)

        result = load_template_from_yaml(str(yaml_file))

        assert result["Parameters"]["Environment"]["Default"] == "dev"
        assert result["Mappings"]["RegionMap"]["us-east-1"]["AMI"] == "ami-12345"
        assert "MyQueue" in result["Resources"]
        assert result["Resources"]["MyQueue"]["Properties"]["QueueName"] == {"Fn::Sub": "queue-${Environment}"}

    def test_load_template_from_yaml_handles_multiline_strings(self, tmp_path):
        """
        load_template_from_yaml SHALL handle multi-line strings correctly.
        """
        from samcli.lib.cfn_language_extensions import load_template_from_yaml

        yaml_content = """
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      Code:
        ZipFile: |
          def handler(event, context):
              return "Hello World"
"""
        yaml_file = tmp_path / "multiline.yaml"
        yaml_file.write_text(yaml_content)

        result = load_template_from_yaml(str(yaml_file))

        code = result["Resources"]["MyFunction"]["Properties"]["Code"]["ZipFile"]
        assert "def handler" in code
        assert "Hello World" in code


class TestLoadTemplate:
    """Tests for the load_template function with auto-detection."""

    def test_load_template_detects_json_extension(self, tmp_path):
        """
        load_template SHALL auto-detect JSON format from .json extension.
        """
        from samcli.lib.cfn_language_extensions import load_template
        import json

        template_content = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}
        json_file = tmp_path / "template.json"
        json_file.write_text(json.dumps(template_content))

        result = load_template(str(json_file))

        assert "MyBucket" in result["Resources"]

    def test_load_template_detects_yaml_extension(self, tmp_path):
        """
        load_template SHALL auto-detect YAML format from .yaml extension.
        """
        from samcli.lib.cfn_language_extensions import load_template

        yaml_content = """
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
"""
        yaml_file = tmp_path / "template.yaml"
        yaml_file.write_text(yaml_content)

        result = load_template(str(yaml_file))

        assert "MyBucket" in result["Resources"]

    def test_load_template_detects_yml_extension(self, tmp_path):
        """
        load_template SHALL auto-detect YAML format from .yml extension.
        """
        from samcli.lib.cfn_language_extensions import load_template

        yaml_content = """
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
"""
        yml_file = tmp_path / "template.yml"
        yml_file.write_text(yaml_content)

        result = load_template(str(yml_file))

        assert "MyBucket" in result["Resources"]

    def test_load_template_detects_template_extension(self, tmp_path):
        """
        load_template SHALL auto-detect YAML format from .template extension.
        """
        from samcli.lib.cfn_language_extensions import load_template

        yaml_content = """
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
"""
        template_file = tmp_path / "stack.template"
        template_file.write_text(yaml_content)

        result = load_template(str(template_file))

        assert "MyBucket" in result["Resources"]

    def test_load_template_raises_for_unknown_extension(self, tmp_path):
        """
        load_template SHALL raise ValueError for unrecognized file extensions.
        """
        from samcli.lib.cfn_language_extensions import load_template

        unknown_file = tmp_path / "template.txt"
        unknown_file.write_text("some content")

        with pytest.raises(ValueError) as exc_info:
            load_template(str(unknown_file))

        assert "Unrecognized file extension" in str(exc_info.value)
        assert ".txt" in str(exc_info.value)

    def test_load_template_case_insensitive_extension(self, tmp_path):
        """
        load_template SHALL handle file extensions case-insensitively.
        """
        from samcli.lib.cfn_language_extensions import load_template
        import json

        template_content = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}
        json_file = tmp_path / "template.JSON"
        json_file.write_text(json.dumps(template_content))

        result = load_template(str(json_file))

        assert "MyBucket" in result["Resources"]

    def test_load_template_raises_for_missing_file(self, tmp_path):
        """
        load_template SHALL raise FileNotFoundError for missing files.
        """
        from samcli.lib.cfn_language_extensions import load_template

        with pytest.raises(FileNotFoundError):
            load_template(str(tmp_path / "nonexistent.json"))


# =============================================================================
# Parametrized Tests for Partial Resolution Mode
# =============================================================================


class TestPartialResolutionModeProperties:
    """
    Parametrized tests for partial resolution mode.

    **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

    Property 17: Partial Resolution Preserves Unresolvable References

    For any template processed in partial resolution mode:
    - Fn::GetAtt SHALL be preserved (16.1)
    - Fn::ImportValue SHALL be preserved (16.2)
    - Ref to resources SHALL be preserved (16.3)
    - Resolvable intrinsics (Fn::Length, Fn::Join, etc.) SHALL still be resolved (16.4)
    - Fn::GetAZs SHALL be preserved (16.5)
    """

    @pytest.mark.parametrize(
        "resource_name, attribute_name",
        [
            ("MyResource", "Arn"),
            ("BucketA1", "DomainName"),
            ("Queue123", "QueueUrl"),
        ],
    )
    def test_fn_get_att_preserved_in_partial_mode(self, resource_name: str, attribute_name: str):
        """
        Property 17: Fn::GetAtt SHALL be preserved in partial resolution mode.

        **Validates: Requirements 16.1**
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Fn::GetAtt": [resource_name, attribute_name]}},
                }
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == {
            "Fn::GetAtt": [resource_name, attribute_name]
        }

    @pytest.mark.parametrize(
        "export_name",
        [
            "SharedVpcId",
            "cross-stack-output-123",
            "DB_Endpoint",
        ],
    )
    def test_fn_import_value_preserved_in_partial_mode(self, export_name: str):
        """
        Property 17: Fn::ImportValue SHALL be preserved in partial resolution mode.

        **Validates: Requirements 16.2**
        """
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Fn::ImportValue": export_name}}}
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == {"Fn::ImportValue": export_name}

    @pytest.mark.parametrize(
        "resource_name",
        [
            "MyBucketResource",
            "Queue1",
            "LambdaFunction",
        ],
    )
    def test_ref_to_resource_preserved_in_partial_mode(self, resource_name: str):
        """
        Property 17: Ref to resources SHALL be preserved in partial resolution mode.

        **Validates: Requirements 16.3**
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Ref": resource_name}},
                }
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == {"Ref": resource_name}

    @pytest.mark.parametrize(
        "region",
        [
            "",
            "us-east-1",
            "eu-west-1",
        ],
    )
    def test_fn_get_azs_preserved_in_partial_mode(self, region: str):
        """
        Property 17: Fn::GetAZs SHALL be preserved in partial resolution mode.

        **Validates: Requirements 16.5**
        """
        template = {
            "Resources": {
                "MySubnet": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {"AvailabilityZones": {"Fn::GetAZs": region}},
                }
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        az_value = result["Resources"]["MySubnet"]["Properties"]["AvailabilityZones"]
        assert az_value == {"Fn::GetAZs": region}

    @pytest.mark.parametrize(
        "items",
        [
            [],
            ["a", "b", "c"],
            ["item1", "item2", "item3", "item4", "item5"],
        ],
    )
    def test_fn_length_resolved_in_partial_mode(self, items: list):
        """
        Property 17: Fn::Length SHALL be resolved in partial resolution mode.

        **Validates: Requirements 16.4**
        """
        template = {
            "Resources": {"MyQueue": {"Type": "AWS::SQS::Queue", "Properties": {"DelaySeconds": {"Fn::Length": items}}}}
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == len(items)

    @pytest.mark.parametrize(
        "delimiter, items",
        [
            ("-", ["my", "bucket", "name"]),
            (",", ["a", "b", "c"]),
            ("", ["x", "y"]),
        ],
    )
    def test_fn_join_resolved_in_partial_mode(self, delimiter: str, items: list):
        """
        Property 17: Fn::Join SHALL be resolved in partial resolution mode.

        **Validates: Requirements 16.4**
        """
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Fn::Join": [delimiter, items]}}}
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        expected = delimiter.join(items)
        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == expected

    @pytest.mark.parametrize(
        "data",
        [
            {"key1": "value1"},
            {"name": "test", "count": "3"},
            {},
        ],
    )
    def test_fn_to_json_string_resolved_in_partial_mode(self, data: dict):
        """
        Property 17: Fn::ToJsonString SHALL be resolved in partial resolution mode.

        **Validates: Requirements 16.4**
        """
        import json

        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Environment": {"Fn::ToJsonString": data}},
                }
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        json_str = result["Resources"]["MyFunction"]["Properties"]["Environment"]
        assert json.loads(json_str) == data

    @pytest.mark.parametrize(
        "param_name, param_value",
        [
            ("Environment", "production"),
            ("BucketPrefix", "my-app"),
            ("Region1", "us-west-2"),
        ],
    )
    def test_ref_to_parameter_resolved_in_partial_mode(self, param_name: str, param_value: str):
        """
        Property 17: Ref to parameters SHALL be resolved in partial resolution mode.

        **Validates: Requirements 16.4**
        """
        template = {
            "Parameters": {param_name: {"Type": "String", "Default": "default-value"}},
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": param_name}}}},
        }

        result = process_template(
            template, parameter_values={param_name: param_value}, resolution_mode=ResolutionMode.PARTIAL
        )

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == param_value

    @pytest.mark.parametrize(
        "resource_name, attribute_name, items",
        [
            ("MyResource", "Arn", ["a", "b", "c"]),
            ("Queue1", "Id", ["item1"]),
            ("Func", "Name", ["x", "y", "z", "w"]),
        ],
    )
    def test_mixed_resolvable_and_unresolvable_intrinsics(self, resource_name: str, attribute_name: str, items: list):
        """
        Property 17: Mixed templates with both resolvable and unresolvable intrinsics
        SHALL have resolvable ones resolved and unresolvable ones preserved.

        **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**
        """
        template = {
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "DelaySeconds": {"Fn::Length": items},
                        "QueueName": {"Fn::GetAtt": [resource_name, attribute_name]},
                        "Tags": [{"Key": "Items", "Value": {"Fn::Join": [",", items]}}],
                    },
                },
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Ref": resource_name}},
                },
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        assert result["Resources"]["MyQueue"]["Properties"]["DelaySeconds"] == len(items)

        assert result["Resources"]["MyQueue"]["Properties"]["QueueName"] == {
            "Fn::GetAtt": [resource_name, attribute_name]
        }

        assert result["Resources"]["MyQueue"]["Properties"]["Tags"][0]["Value"] == ",".join(items)

        assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == {"Ref": resource_name}

    @pytest.mark.parametrize(
        "resource_name, attribute_name, export_name",
        [
            ("MyResource", "Arn", "SharedOutput"),
            ("BucketRes", "Id", "cross-stack-val"),
            ("Queue1", "Name", "DB_Endpoint"),
        ],
    )
    def test_nested_unresolvable_intrinsics_preserved(self, resource_name: str, attribute_name: str, export_name: str):
        """
        Property 17: Nested unresolvable intrinsics SHALL be preserved.

        **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**
        """
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": {
                            "Fn::Join": ["-", ["prefix", {"Fn::GetAtt": [resource_name, attribute_name]}, "suffix"]]
                        }
                    },
                }
            }
        }

        result = process_template(template, resolution_mode=ResolutionMode.PARTIAL)

        bucket_name = result["Resources"]["MyBucket"]["Properties"]["BucketName"]

        assert "Fn::GetAtt" in str(bucket_name) or isinstance(bucket_name, dict)


class TestLoadTemplateIntegration:
    """Integration tests for loading and processing templates."""

    def test_load_and_process_json_template(self, tmp_path):
        """
        Templates loaded from JSON files SHALL be processable.
        """
        from samcli.lib.cfn_language_extensions import load_template, process_template
        import json

        template_content = {
            "Resources": {"Fn::ForEach::Topics": ["Name", ["A", "B"], {"Topic${Name}": {"Type": "AWS::SNS::Topic"}}]}
        }
        json_file = tmp_path / "template.json"
        json_file.write_text(json.dumps(template_content))

        template = load_template(str(json_file))
        result = process_template(template)

        assert "TopicA" in result["Resources"]
        assert "TopicB" in result["Resources"]

    def test_load_and_process_yaml_template(self, tmp_path):
        """
        Templates loaded from YAML files SHALL be processable.
        """
        from samcli.lib.cfn_language_extensions import load_template, process_template

        yaml_content = """
Resources:
  Fn::ForEach::Topics:
    - Name
    - [A, B]
    - Topic${Name}:
        Type: AWS::SNS::Topic
"""
        yaml_file = tmp_path / "template.yaml"
        yaml_file.write_text(yaml_content)

        template = load_template(str(yaml_file))
        result = process_template(template)

        assert "TopicA" in result["Resources"]
        assert "TopicB" in result["Resources"]


class TestProcessTemplateAdditionalEdgeCases:
    """Tests for process_template function additional edge cases."""

    def test_process_template_with_empty_resources(self):
        """Test processing template with empty Resources section."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Empty template",
            "Resources": {},
        }
        result = process_template(template)
        assert "Description" in result
        assert result["Resources"] == {}

    def test_process_template_preserves_unknown_sections(self):
        """Test that unknown template sections are preserved."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Metadata": {"CustomKey": "CustomValue"},
            "Resources": {},
        }
        result = process_template(template)
        assert result["Metadata"]["CustomKey"] == "CustomValue"

    def test_process_template_with_condition_and_parameter(self):
        """Test processing template with conditions referencing parameters."""
        template = {
            "Parameters": {"Env": {"Type": "String", "Default": "prod"}},
            "Conditions": {"IsProduction": {"Fn::Equals": [{"Ref": "Env"}, "prod"]}},
            "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic", "Condition": "IsProduction"}},
        }
        result = process_template(template, parameter_values={"Env": "prod"})
        assert "IsProduction" in result.get("Conditions", {})
