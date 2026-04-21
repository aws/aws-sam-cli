"""
Tests for SAM CLI integration.

This module contains unit tests for the SAM integration components:
- process_template_for_sam_cli
- expand_language_extensions (including template-level caching)

Requirements tested:
    - 15.1-15.5: SAM CLI integration
"""

from typing import Any, Dict, List

import pytest

from samcli.lib.cfn_language_extensions import (
    process_template_for_sam_cli,
    AWS_LANGUAGE_EXTENSIONS_TRANSFORM,
    PseudoParameterValues,
)

# =============================================================================
# Tests for SAM Integration
# =============================================================================


class TestProcessTemplateForSAMCLIProperties:
    """Tests for process_template_for_sam_cli."""

    @pytest.mark.parametrize(
        "param_name,param_value,resource_id",
        [
            ("Environment", "prod", "MyTopic"),
            ("AppName", "myapp", "AppResource"),
            ("Stage", "dev", "StageRes"),
        ],
    )
    def test_parameter_resolution_in_sam_cli(
        self,
        param_name: str,
        param_value: str,
        resource_id: str,
    ):
        """
        Property: Parameter values are resolved in SAM CLI processing.

        For any template with Ref to parameters, the parameter values
        SHALL be substituted when provided.

        **Validates: Requirements 15.1, 15.2, 15.3**
        """
        template = {
            "Parameters": {
                param_name: {
                    "Type": "String",
                    "Default": "default-value",
                }
            },
            "Resources": {resource_id: {"Type": "AWS::SNS::Topic", "Properties": {"TopicName": {"Ref": param_name}}}},
        }

        result = process_template_for_sam_cli(template, parameter_values={param_name: param_value})

        # Parameter should be resolved
        assert result["Resources"][resource_id]["Properties"]["TopicName"] == param_value

    @pytest.mark.parametrize(
        "region,resource_id",
        [
            ("us-east-1", "MyTopic"),
            ("eu-west-1", "EuTopic"),
            ("ap-southeast-1", "ApTopic"),
        ],
    )
    def test_pseudo_parameter_resolution_in_sam_cli(
        self,
        region: str,
        resource_id: str,
    ):
        """
        Property: Pseudo-parameters are resolved in SAM CLI processing.

        For any template with Ref to pseudo-parameters, the values
        SHALL be substituted when provided.

        **Validates: Requirements 15.1, 15.4**
        """
        template = {
            "Resources": {
                resource_id: {"Type": "AWS::SNS::Topic", "Properties": {"DisplayName": {"Ref": "AWS::Region"}}}
            }
        }

        pseudo = PseudoParameterValues(region=region, account_id="123456789012")

        result = process_template_for_sam_cli(template, pseudo_parameters=pseudo)

        # Pseudo-parameter should be resolved
        assert result["Resources"][resource_id]["Properties"]["DisplayName"] == region


# =============================================================================
# Unit Tests for SAM Integration
# =============================================================================


class TestProcessTemplateForSAMCLI:
    """Unit tests for process_template_for_sam_cli."""

    def test_sam_cli_processes_foreach(self):
        """
        Requirement 15.1: SAM CLI processes Fn::ForEach.
        """
        template = {
            "Resources": {
                "Fn::ForEach::Queues": [
                    "QueueName",
                    ["Orders", "Notifications"],
                    {"Queue${QueueName}": {"Type": "AWS::SQS::Queue"}},
                ]
            }
        }

        result = process_template_for_sam_cli(template)

        assert "QueueOrders" in result["Resources"]
        assert "QueueNotifications" in result["Resources"]
        assert "Fn::ForEach::Queues" not in result["Resources"]

    def test_sam_cli_preserves_transform(self):
        """
        Requirement 15.5: SAM CLI preserves Transform field.
        """
        template = {"Transform": "AWS::LanguageExtensions", "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic"}}}

        result = process_template_for_sam_cli(template)

        # Transform should be preserved (unlike plugin)
        assert result.get("Transform") == "AWS::LanguageExtensions"

    def test_sam_cli_with_pseudo_parameters(self):
        """
        Requirement 15.1: SAM CLI uses pseudo-parameters.
        """
        template = {
            "Resources": {
                "MyTopic": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {"DisplayName": {"Fn::Sub": "Topic in ${AWS::Region}"}},
                }
            }
        }

        pseudo = PseudoParameterValues(region="us-west-2", account_id="123456789012")

        result = process_template_for_sam_cli(template, pseudo_parameters=pseudo)

        assert result["Resources"]["MyTopic"]["Properties"]["DisplayName"] == "Topic in us-west-2"

    def test_sam_cli_partial_resolution(self):
        """
        Requirement 15.2, 15.4: SAM CLI uses partial resolution mode.
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"FunctionName": {"Fn::GetAtt": ["MyTable", "Arn"]}},
                },
                "MyTable": {"Type": "AWS::DynamoDB::Table"},
            }
        }

        result = process_template_for_sam_cli(template)

        # Fn::GetAtt should be preserved
        assert result["Resources"]["MyFunction"]["Properties"]["FunctionName"] == {"Fn::GetAtt": ["MyTable", "Arn"]}


# =============================================================================
# Coverage Tests for sam_integration.py
# =============================================================================

from unittest.mock import patch

from samcli.lib.cfn_language_extensions.sam_integration import (
    LanguageExtensionResult,
    _build_pseudo_parameters,
    check_using_language_extension,
    contains_loop_variable,
    detect_dynamic_artifact_properties,
    detect_foreach_dynamic_properties,
    expand_language_extensions,
    resolve_collection,
    resolve_parameter_collection,
)


class TestBuildPseudoParameters:
    """Tests for _build_pseudo_parameters."""

    def test_returns_none_for_none_input(self):
        assert _build_pseudo_parameters(None) is None

    def test_returns_none_for_empty_dict(self):
        assert _build_pseudo_parameters({}) is None

    def test_returns_none_for_no_pseudo_params(self):
        assert _build_pseudo_parameters({"MyParam": "value"}) is None

    def test_extracts_region(self):
        result = _build_pseudo_parameters({"AWS::Region": "us-east-1"})
        assert result is not None
        assert result.region == "us-east-1"

    def test_extracts_account_id(self):
        result = _build_pseudo_parameters({"AWS::AccountId": "123456789012"})
        assert result is not None
        assert result.account_id == "123456789012"

    def test_extracts_stack_name(self):
        result = _build_pseudo_parameters({"AWS::StackName": "my-stack"})
        assert result is not None
        assert result.stack_name == "my-stack"

    def test_extracts_stack_id(self):
        result = _build_pseudo_parameters({"AWS::StackId": "arn:aws:cloudformation:us-east-1:123:stack/my-stack/guid"})
        assert result is not None
        assert result.stack_id == "arn:aws:cloudformation:us-east-1:123:stack/my-stack/guid"

    def test_extracts_partition(self):
        result = _build_pseudo_parameters({"AWS::Partition": "aws"})
        assert result is not None
        assert result.partition == "aws"

    def test_extracts_url_suffix(self):
        result = _build_pseudo_parameters({"AWS::URLSuffix": "amazonaws.com"})
        assert result is not None
        assert result.url_suffix == "amazonaws.com"

    def test_extracts_all_pseudo_params(self):
        result = _build_pseudo_parameters(
            {
                "AWS::Region": "us-west-2",
                "AWS::AccountId": "111222333444",
                "AWS::StackName": "test-stack",
                "AWS::StackId": "arn:stack-id",
                "AWS::Partition": "aws-cn",
                "AWS::URLSuffix": "amazonaws.com.cn",
            }
        )
        assert result is not None
        assert result.region == "us-west-2"
        assert result.account_id == "111222333444"
        assert result.stack_name == "test-stack"
        assert result.stack_id == "arn:stack-id"
        assert result.partition == "aws-cn"
        assert result.url_suffix == "amazonaws.com.cn"

    def test_missing_pseudo_params_default_to_empty_string_or_none(self):
        result = _build_pseudo_parameters({"AWS::Region": "us-east-1"})
        assert result is not None
        assert result.region == "us-east-1"
        assert result.account_id == ""
        assert result.stack_name is None
        assert result.stack_id is None
        assert result.partition is None
        assert result.url_suffix is None


class TestContainsLoopVariable:
    """Tests for contains_loop_variable."""

    def test_string_with_variable(self):
        assert contains_loop_variable("./src/${Name}", "Name") is True

    def test_string_without_variable(self):
        assert contains_loop_variable("./src/static", "Name") is False

    def test_ref_dict_matching(self):
        assert contains_loop_variable({"Ref": "Name"}, "Name") is True

    def test_ref_dict_not_matching(self):
        assert contains_loop_variable({"Ref": "Other"}, "Name") is False

    def test_fn_sub_string(self):
        assert contains_loop_variable({"Fn::Sub": "./src/${Name}"}, "Name") is True

    def test_fn_sub_string_no_match(self):
        assert contains_loop_variable({"Fn::Sub": "./src/static"}, "Name") is False

    def test_fn_sub_list_form(self):
        assert contains_loop_variable({"Fn::Sub": ["./src/${Name}", {}]}, "Name") is True

    def test_fn_sub_list_form_no_match(self):
        assert contains_loop_variable({"Fn::Sub": ["./src/static", {}]}, "Name") is False

    def test_nested_dict(self):
        assert contains_loop_variable({"Nested": {"Deep": "./src/${Name}"}}, "Name") is True

    def test_list_with_variable(self):
        assert contains_loop_variable(["./src/${Name}", "other"], "Name") is True

    def test_list_without_variable(self):
        assert contains_loop_variable(["static", "other"], "Name") is False

    def test_non_string_non_dict_non_list(self):
        assert contains_loop_variable(42, "Name") is False
        assert contains_loop_variable(None, "Name") is False
        assert contains_loop_variable(True, "Name") is False

    def test_fn_sub_empty_list(self):
        assert contains_loop_variable({"Fn::Sub": []}, "Name") is False


class TestResolveCollection:
    """Tests for resolve_collection and resolve_parameter_collection."""

    def test_static_list(self):
        result = resolve_collection(["Alpha", "Beta"], {})
        assert result == ["Alpha", "Beta"]

    def test_static_list_with_none_values(self):
        result = resolve_collection(["Alpha", None, "Beta"], {})
        assert result == ["Alpha", "Beta"]

    def test_static_list_with_integers(self):
        result = resolve_collection([1, 2, 3], {})
        assert result == ["1", "2", "3"]

    def test_ref_to_parameter_with_override(self):
        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList"}}}
        result = resolve_collection({"Ref": "Names"}, template, {"Names": "Alpha,Beta"})
        assert result == ["Alpha", "Beta"]

    def test_ref_to_parameter_with_list_override(self):
        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList"}}}
        result = resolve_collection({"Ref": "Names"}, template, {"Names": ["Alpha", "Beta"]})
        assert result == ["Alpha", "Beta"]

    def test_ref_to_parameter_with_default(self):
        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "X,Y"}}}
        result = resolve_collection({"Ref": "Names"}, template)
        assert result == ["X", "Y"]

    def test_ref_to_parameter_with_list_default(self):
        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": ["X", "Y"]}}}
        result = resolve_collection({"Ref": "Names"}, template)
        assert result == ["X", "Y"]

    def test_ref_to_nonexistent_parameter(self):
        result = resolve_collection({"Ref": "Missing"}, {"Parameters": {}})
        assert result == []

    def test_unsupported_collection_type(self):
        result = resolve_collection("not-a-list-or-dict", {})
        assert result == []

    def test_non_ref_dict(self):
        result = resolve_collection({"Fn::GetAtt": ["Resource", "Attr"]}, {})
        assert result == []

    def test_ref_to_param_no_parameters_section(self):
        result = resolve_collection({"Ref": "Names"}, {})
        assert result == []

    def test_ref_to_param_non_dict_param_def(self):
        template = {"Parameters": {"Names": "not-a-dict"}}
        result = resolve_collection({"Ref": "Names"}, template)
        assert result == []


class TestResolveParameterCollection:
    """Direct tests for resolve_parameter_collection."""

    def test_override_string_value(self):
        result = resolve_parameter_collection("P", {}, {"P": "a, b, c"})
        assert result == ["a", "b", "c"]

    def test_override_list_value(self):
        result = resolve_parameter_collection("P", {}, {"P": ["a", "b"]})
        assert result == ["a", "b"]

    def test_default_string_value(self):
        result = resolve_parameter_collection("P", {"Parameters": {"P": {"Default": "x,y"}}})
        assert result == ["x", "y"]

    def test_default_list_value(self):
        result = resolve_parameter_collection("P", {"Parameters": {"P": {"Default": ["x", "y"]}}})
        assert result == ["x", "y"]

    def test_no_default_no_override(self):
        result = resolve_parameter_collection("P", {"Parameters": {"P": {"Type": "String"}}})
        assert result == []

    def test_no_parameters_section(self):
        result = resolve_parameter_collection("P", {})
        assert result == []


class TestDetectForeachDynamicProperties:
    """Tests for detect_foreach_dynamic_properties."""

    def test_detects_dynamic_codeuri(self):
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Function": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src/${Name}",
                        "Handler": "index.handler",
                    },
                }
            },
        ]
        template = {"Resources": {}}
        result = detect_foreach_dynamic_properties("Fn::ForEach::Services", foreach_value, template)
        assert len(result) == 1
        assert result[0].loop_name == "Services"
        assert result[0].loop_variable == "Name"
        assert result[0].property_name == "CodeUri"
        assert result[0].collection == ["Alpha", "Beta"]

    def test_static_codeuri_not_detected(self):
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Function": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Handler": "${Name}.handler",
                    },
                }
            },
        ]
        template = {"Resources": {}}
        result = detect_foreach_dynamic_properties("Fn::ForEach::Services", foreach_value, template)
        assert len(result) == 0

    def test_invalid_foreach_value_not_list(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", "not-a-list", {})
        assert result == []

    def test_invalid_foreach_value_wrong_length(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"]], {})
        assert result == []

    def test_non_string_loop_variable(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", [123, ["A"], {}], {})
        assert result == []

    def test_non_dict_output_template(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"], "not-dict"], {})
        assert result == []

    def test_non_dict_resource_def_skipped(self):
        foreach_value = ["Name", ["A"], {"Res": "not-a-dict"}]
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", foreach_value, {})
        assert result == []

    def test_non_string_resource_type_skipped(self):
        foreach_value = ["Name", ["A"], {"Res": {"Type": 123, "Properties": {}}}]
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", foreach_value, {})
        assert result == []

    def test_non_packageable_resource_type_skipped(self):
        foreach_value = [
            "Name",
            ["A"],
            {"Res": {"Type": "AWS::DynamoDB::Table", "Properties": {"TableName": "${Name}"}}},
        ]
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", foreach_value, {})
        assert result == []

    def test_non_dict_properties_skipped(self):
        foreach_value = [
            "Name",
            ["A"],
            {"Res": {"Type": "AWS::Serverless::Function", "Properties": "not-dict"}},
        ]
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", foreach_value, {})
        assert result == []

    def test_empty_collection_returns_empty(self):
        foreach_value = [
            "Name",
            {"Ref": "Missing"},
            {"Res": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "${Name}"}}},
        ]
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", foreach_value, {})
        assert result == []

    def test_parameter_ref_collection_detected(self):
        foreach_value = [
            "Name",
            {"Ref": "ServiceNames"},
            {
                "${Name}Function": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src/${Name}"},
                }
            },
        ]
        template = {"Parameters": {"ServiceNames": {"Type": "CommaDelimitedList", "Default": "A,B"}}}
        result = detect_foreach_dynamic_properties("Fn::ForEach::Svc", foreach_value, template)
        assert len(result) == 1
        assert result[0].collection_is_parameter_ref is True
        assert result[0].collection_parameter_name == "ServiceNames"

    def test_lambda_function_dynamic_code(self):
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Function": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": "./src/${Name}",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                }
            },
        ]
        result = detect_foreach_dynamic_properties("Fn::ForEach::Funcs", foreach_value, {})
        assert len(result) == 1
        assert result[0].property_name == "Code"

    def test_layer_dynamic_contenturi(self):
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Layer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": "./layers/${Name}"},
                }
            },
        ]
        result = detect_foreach_dynamic_properties("Fn::ForEach::Layers", foreach_value, {})
        assert len(result) == 1
        assert result[0].property_name == "ContentUri"


class TestDetectDynamicArtifactProperties:
    """Tests for detect_dynamic_artifact_properties."""

    def test_detects_properties_in_resources(self):
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./src/${Name}"},
                        }
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        assert len(result) == 1

    def test_no_foreach_returns_empty(self):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src"},
                }
            }
        }
        result = detect_dynamic_artifact_properties(template)
        assert result == []

    def test_non_dict_resources_returns_empty(self):
        result = detect_dynamic_artifact_properties({"Resources": "not-a-dict"})
        assert result == []

    def test_no_resources_returns_empty(self):
        result = detect_dynamic_artifact_properties({"AWSTemplateFormatVersion": "2010-09-09"})
        assert result == []

    def test_multiple_foreach_blocks(self):
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["A", "B"],
                    {
                        "${Name}Func": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./src/${Name}"},
                        }
                    },
                ],
                "Fn::ForEach::Layers": [
                    "Name",
                    ["X", "Y"],
                    {
                        "${Name}Layer": {
                            "Type": "AWS::Serverless::LayerVersion",
                            "Properties": {"ContentUri": "./layers/${Name}"},
                        }
                    },
                ],
            }
        }
        result = detect_dynamic_artifact_properties(template)
        assert len(result) == 2


class TestExpandLanguageExtensionsEdgeCases:
    """Tests for expand_language_extensions edge cases."""

    def test_nonexistent_template_path_does_not_error(self):
        template = {"Transform": "AWS::Serverless-2016-10-31", "Resources": {}}
        result = expand_language_extensions(template, template_path="/nonexistent/path/template.yaml")
        assert result.had_language_extensions is False

    def test_non_language_extension_template_returns_frozen_result(self):
        template = {"Resources": {}}
        result = expand_language_extensions(template)
        assert result.had_language_extensions is False
        # Both fields point to the same frozen object (no-LE path optimization)
        assert result.expanded_template is result.original_template
        assert dict(result.expanded_template) == template
        # Frozen — mutation raises TypeError
        with pytest.raises(TypeError):
            result.expanded_template["Resources"] = {}

    def test_mutation_does_not_affect_subsequent_calls(self):
        """Frozen results prevent mutation; callers must deep_thaw first."""
        from samcli.lib.cfn_language_extensions.utils import deep_thaw

        template = {
            "Resources": {
                "MyStack": {
                    "Type": "AWS::Serverless::Application",
                    "Properties": {"Location": "./child.yaml"},
                }
            }
        }
        result1 = expand_language_extensions(template)
        # Must deep_thaw before mutating (matches the documented contract)
        mutable = deep_thaw(result1.expanded_template)
        mutable["Resources"]["MyStack"]["Properties"]["Location"] = "SomeOther/template.yaml"

        # A fresh call should not be affected
        template2 = {
            "Resources": {
                "MyStack": {
                    "Type": "AWS::Serverless::Application",
                    "Properties": {"Location": "./child.yaml"},
                }
            }
        }
        result2 = expand_language_extensions(template2)
        assert result2.expanded_template["Resources"]["MyStack"]["Properties"]["Location"] == "./child.yaml"

    def test_non_invalid_template_exception_reraised(self):
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Test": [
                    "Name",
                    ["A"],
                    {
                        "${Name}Res": {
                            "Type": "AWS::CloudFormation::WaitConditionHandle",
                        }
                    },
                ]
            },
        }
        with patch(
            "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
            side_effect=RuntimeError("unexpected error"),
        ):
            with pytest.raises(RuntimeError, match="unexpected error"):
                expand_language_extensions(template)

    def test_invalid_template_exception_converted(self):
        from samcli.lib.cfn_language_extensions.exceptions import (
            InvalidTemplateException as LangExtInvalidTemplateException,
        )

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {},
        }
        with patch(
            "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
            side_effect=LangExtInvalidTemplateException("bad template"),
        ):
            from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

            with pytest.raises(InvalidSamDocumentException):
                expand_language_extensions(template)

    def test_telemetry_tracked_when_language_extensions_used(self):
        """Verify UsedFeature telemetry event is emitted when language extensions are expanded."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Test": [
                    "Name",
                    ["A"],
                    {
                        "${Name}Res": {
                            "Type": "AWS::CloudFormation::WaitConditionHandle",
                        }
                    },
                ]
            },
        }
        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as mock_track:
            result = expand_language_extensions(template)
            assert result.had_language_extensions is True
            mock_track.assert_called_with("UsedFeature", "CFNLanguageExtensions")

    def test_telemetry_not_tracked_when_no_language_extensions(self):
        """Verify no telemetry event when template has no language extensions."""
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"Fn": {"Type": "AWS::Lambda::Function", "Properties": {}}},
        }
        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as mock_track:
            result = expand_language_extensions(template)
            assert result.had_language_extensions is False
            mock_track.assert_not_called()


class TestCheckUsingLanguageExtensionEdgeCases:
    """Tests for check_using_language_extension edge cases."""

    def test_none_template(self):
        assert check_using_language_extension(None) is False

    def test_no_transform_key(self):
        assert check_using_language_extension({"Resources": {}}) is False

    def test_empty_transform(self):
        assert check_using_language_extension({"Transform": ""}) is False

    def test_non_string_in_transform_list(self):
        assert check_using_language_extension({"Transform": [123, "AWS::LanguageExtensions"]}) is True

    def test_non_string_only_in_transform_list(self):
        assert check_using_language_extension({"Transform": [123, 456]}) is False

    def test_transform_list_without_language_extensions(self):
        assert check_using_language_extension({"Transform": ["AWS::Serverless-2016-10-31"]}) is False

    def test_transform_none_value(self):
        assert check_using_language_extension({"Transform": None}) is False


class TestLanguageExtensionResultDataclass:
    """Tests for LanguageExtensionResult frozen dataclass."""

    def test_default_values(self):
        result = LanguageExtensionResult(
            expanded_template={},
            original_template={},
        )
        assert result.dynamic_artifact_properties == []
        assert result.had_language_extensions is False

    def test_frozen(self):
        result = LanguageExtensionResult(
            expanded_template={},
            original_template={},
        )
        with pytest.raises(AttributeError):
            result.had_language_extensions = True


# =============================================================================
# Tests for template-level expansion cache
# =============================================================================

import os
import tempfile

from samcli.lib.cfn_language_extensions.sam_integration import (
    _expansion_cache,
    _MAX_CACHE_SIZE,
    clear_expansion_cache,
)


class TestExpansionCache:
    """Tests for template-level caching in expand_language_extensions."""

    def setup_method(self):
        """Clear cache before each test to avoid cross-test pollution."""
        clear_expansion_cache()

    def teardown_method(self):
        clear_expansion_cache()

    def _make_template_file(self, tmp_path, content="Transform: AWS::LanguageExtensions\nResources: {}"):
        """Write a dummy file so os.path.isfile / getmtime work."""
        path = os.path.join(tmp_path, "template.yaml")
        with open(path, "w") as f:
            f.write(content)
        return path

    def _lang_ext_template(self):
        return {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Items": [
                    "Name",
                    ["A", "B"],
                    {"Topic${Name}": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }

    def test_cache_hit_avoids_reprocessing(self):
        """Second call with same path/mtime/params should be a cache hit."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = self._lang_ext_template()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value={
                    "Resources": {"TopicA": {"Type": "AWS::SNS::Topic"}, "TopicB": {"Type": "AWS::SNS::Topic"}}
                },
            ) as mock_process:
                expand_language_extensions(template, template_path=path)
                expand_language_extensions(template, template_path=path)

                assert mock_process.call_count == 1

    def test_cache_miss_on_different_path(self):
        """Different template_path should miss the cache."""
        with tempfile.TemporaryDirectory() as tmp:
            path1 = os.path.join(tmp, "t1.yaml")
            path2 = os.path.join(tmp, "t2.yaml")
            for p in (path1, path2):
                with open(p, "w") as f:
                    f.write("x")
            template = self._lang_ext_template()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value={"Resources": {}},
            ) as mock_process:
                expand_language_extensions(template, template_path=path1)
                expand_language_extensions(template, template_path=path2)

                assert mock_process.call_count == 2

    def test_cache_miss_on_different_mtime(self):
        """Changed file mtime should miss the cache."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = self._lang_ext_template()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value={"Resources": {}},
            ) as mock_process:
                expand_language_extensions(template, template_path=path)

                # Touch the file to change its mtime
                import time

                time.sleep(0.05)
                os.utime(path, None)

                expand_language_extensions(template, template_path=path)

                assert mock_process.call_count == 2

    def test_cache_miss_on_different_params(self):
        """Different parameter_values should miss the cache."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = self._lang_ext_template()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value={"Resources": {}},
            ) as mock_process:
                expand_language_extensions(template, parameter_values={"Env": "dev"}, template_path=path)
                expand_language_extensions(template, parameter_values={"Env": "prod"}, template_path=path)

                assert mock_process.call_count == 2

    def test_clear_expansion_cache(self):
        """clear_expansion_cache() should force re-expansion."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = self._lang_ext_template()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value={"Resources": {}},
            ) as mock_process:
                expand_language_extensions(template, template_path=path)
                clear_expansion_cache()
                expand_language_extensions(template, template_path=path)

                assert mock_process.call_count == 2

    def test_no_template_path_skips_cache(self):
        """Without template_path, every call should process."""
        template = self._lang_ext_template()

        with patch(
            "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
            return_value={"Resources": {}},
        ) as mock_process:
            expand_language_extensions(template)
            expand_language_extensions(template)

            assert mock_process.call_count == 2

    def test_cache_returns_independent_copies(self):
        """Cached results are frozen — mutation raises TypeError."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = self._lang_ext_template()

            expanded = {
                "Resources": {
                    "TopicA": {"Type": "AWS::SNS::Topic", "Properties": {"DisplayName": "original"}},
                    "TopicB": {"Type": "AWS::SNS::Topic"},
                }
            }

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
                return_value=expanded,
            ):
                result1 = expand_language_extensions(template, template_path=path)
                # Frozen — mutation raises TypeError
                with pytest.raises(TypeError):
                    result1.expanded_template["Resources"]["TopicA"]["Properties"]["DisplayName"] = "mutated"

                # Cache hit returns the same frozen object
                result2 = expand_language_extensions(template, template_path=path)
                assert result2 is result1
                assert result2.expanded_template["Resources"]["TopicA"]["Properties"]["DisplayName"] == "original"

    def test_nonexistent_template_path_skips_cache(self):
        """A template_path that doesn't exist should skip caching."""
        template = self._lang_ext_template()

        with patch(
            "samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli",
            return_value={"Resources": {}},
        ) as mock_process:
            expand_language_extensions(template, template_path="/no/such/file.yaml")
            expand_language_extensions(template, template_path="/no/such/file.yaml")

            assert mock_process.call_count == 2
            assert len(_expansion_cache) == 0

    def test_non_language_ext_template_cached(self):
        """Templates without language extensions should also be cached when path is given."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = {"Resources": {"MyTopic": {"Type": "AWS::SNS::Topic"}}}

            result1 = expand_language_extensions(template, template_path=path)
            result2 = expand_language_extensions(template, template_path=path)

            assert result1.had_language_extensions is False
            assert result2.had_language_extensions is False
            assert len(_expansion_cache) == 1
            # Cache returns the same frozen object
            assert result1 is result2

    def test_cache_evicts_oldest_when_full(self):
        """Cache should evict the oldest entry when _MAX_CACHE_SIZE is reached."""
        clear_expansion_cache()
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Item",
                    ["A"],
                    {"Res${Item}": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i in range(_MAX_CACHE_SIZE + 1):
                path = os.path.join(tmp, f"template_{i}.yaml")
                with open(path, "w") as f:
                    f.write("AWSTemplateFormatVersion: '2010-09-09'\n")
                paths.append(path)

            # Fill the cache to capacity
            for i in range(_MAX_CACHE_SIZE):
                expand_language_extensions(template, template_path=paths[i])

            assert len(_expansion_cache) == _MAX_CACHE_SIZE
            first_key = next(iter(_expansion_cache))

            # One more should evict the oldest
            expand_language_extensions(template, template_path=paths[_MAX_CACHE_SIZE])

            assert len(_expansion_cache) == _MAX_CACHE_SIZE
            assert first_key not in _expansion_cache

    def test_original_template_is_independent_copy(self):
        """Mutating the input template after the call should not affect original_template."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = {
                "Transform": "AWS::LanguageExtensions",
                "Resources": {
                    "Fn::ForEach::Loop": [
                        "Item",
                        ["A"],
                        {"Res${Item}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }

            result = expand_language_extensions(template, template_path=path)

            # Mutate the caller's template
            template["Resources"]["NewResource"] = {"Type": "AWS::SQS::Queue"}

            # original_template should not be affected
            assert "NewResource" not in result.original_template.get("Resources", {})

    def test_original_template_is_independent_copy_no_extensions(self):
        """Same independence guarantee when template has no language extensions."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_template_file(tmp)
            template = {"Resources": {"MyTopic": {"Type": "AWS::SNS::Topic"}}}

            result = expand_language_extensions(template, template_path=path)

            # Mutate the caller's template
            template["Resources"]["Injected"] = {"Type": "AWS::SQS::Queue"}

            # original_template should not be affected
            assert "Injected" not in result.original_template.get("Resources", {})
