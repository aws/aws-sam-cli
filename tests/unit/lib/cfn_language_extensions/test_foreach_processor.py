"""
Unit tests for the ForEachProcessor class.

Tests cover:
- Detection of Fn::ForEach:: prefixed keys
- Validation of ForEach structure (identifier, collection, body)
- Resolution of collections containing intrinsic functions
- Error handling for invalid ForEach constructs

Requirements:
    - 6.7: WHEN Fn::ForEach has invalid layout (wrong number of arguments,
           invalid types), THEN THE Resolver SHALL raise an Invalid_Template_Exception
    - 6.8: WHEN Fn::ForEach collection contains a Ref to a parameter,
           THEN THE Resolver SHALL resolve the parameter value before iteration
"""

import pytest
from typing import Any, Dict, List

from samcli.lib.cfn_language_extensions.models import (
    TemplateProcessingContext,
    ResolutionMode,
    ParsedTemplate,
)
from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestForEachProcessorDetection:
    """Tests for ForEachProcessor Fn::ForEach:: key detection."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_detects_foreach_key(self, processor: ForEachProcessor):
        """Test that is_foreach_key returns True for valid ForEach keys."""
        from samcli.lib.cfn_language_extensions.utils import is_foreach_key

        assert is_foreach_key("Fn::ForEach::Topics") is True
        assert is_foreach_key("Fn::ForEach::MyLoop") is True
        assert is_foreach_key("Fn::ForEach::A") is True

    def test_does_not_detect_non_foreach_keys(self, processor: ForEachProcessor):
        """Test that is_foreach_key returns False for non-ForEach keys."""
        from samcli.lib.cfn_language_extensions.utils import is_foreach_key

        assert is_foreach_key("Fn::Sub") is False
        assert is_foreach_key("Fn::Length") is False
        assert is_foreach_key("Ref") is False
        assert is_foreach_key("MyResource") is False
        assert is_foreach_key("Fn::ForEach") is False  # Missing ::

    def test_does_not_detect_non_string_keys(self, processor: ForEachProcessor):
        """Test that is_foreach_key returns False for non-string values."""
        from samcli.lib.cfn_language_extensions.utils import is_foreach_key

        assert is_foreach_key(123) is False  # type: ignore[arg-type]
        assert is_foreach_key(None) is False  # type: ignore[arg-type]
        assert is_foreach_key(["Fn::ForEach::Test"]) is False  # type: ignore[arg-type]

    def test_get_foreach_loop_name(self, processor: ForEachProcessor):
        """Test extracting loop name from ForEach key."""
        assert processor.get_foreach_loop_name("Fn::ForEach::Topics") == "Topics"
        assert processor.get_foreach_loop_name("Fn::ForEach::MyLoop") == "MyLoop"
        assert processor.get_foreach_loop_name("Fn::ForEach::A") == "A"

    def test_get_foreach_loop_name_invalid_key_raises(self, processor: ForEachProcessor):
        """Test that get_foreach_loop_name raises for invalid keys."""
        with pytest.raises(ValueError):
            processor.get_foreach_loop_name("Fn::Sub")


class TestForEachProcessorValidation:
    """Tests for ForEachProcessor validation of ForEach structure.

    Requirement 6.7: WHEN Fn::ForEach has invalid layout (wrong number of arguments,
    invalid types), THEN THE Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    def test_valid_foreach_structure(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that valid ForEach structure passes validation."""
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Alerts", "Notifications"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }
        # Should not raise
        processor.process_template(context)

    def test_valid_foreach_with_empty_collection(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach with empty collection passes validation."""
        context.fragment = {
            "Resources": {"Fn::ForEach::Topics": ["TopicName", [], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]}
        }
        # Should not raise
        processor.process_template(context)

    def test_invalid_foreach_not_a_list(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach value must be a list.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid layout
        """
        context.fragment = {"Resources": {"Fn::ForEach::Topics": "not-a-list"}}

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_wrong_number_of_elements_too_few(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that ForEach must have exactly 3 elements.

        Requirement 6.7: Raise Invalid_Template_Exception for wrong number of arguments
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Alerts"],
                    # Missing template body
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_wrong_number_of_elements_too_many(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that ForEach must have exactly 3 elements.

        Requirement 6.7: Raise Invalid_Template_Exception for wrong number of arguments
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Alerts"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    "extra-element",
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_identifier_not_string(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that ForEach identifier must be a string.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    123,  # Not a string
                    ["Alerts"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_identifier_empty_string(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that ForEach identifier must be non-empty.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "",  # Empty string
                    ["Alerts"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_identifier_none(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach identifier cannot be None.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [None, ["Alerts"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]  # None
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_collection_not_list(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach collection must be a list.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    "not-a-list",  # String instead of list
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_collection_integer(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach collection cannot be an integer.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    42,  # Integer instead of list
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_body_not_dict(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach template body must be a dictionary.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {"Fn::ForEach::Topics": ["TopicName", ["Alerts"], "not-a-dict"]}  # String instead of dict
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_body_list(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach template body cannot be a list.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": ["TopicName", ["Alerts"], ["not", "a", "dict"]]  # List instead of dict
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)

    def test_invalid_foreach_body_none(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach template body cannot be None.

        Requirement 6.7: Raise Invalid_Template_Exception for invalid types
        """
        context.fragment = {
            "Resources": {"Fn::ForEach::Topics": ["TopicName", ["Alerts"], None]}  # None instead of dict
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "Fn::ForEach::Topics layout is incorrect" in str(exc_info.value)


class TestForEachProcessorSections:
    """Tests for ForEachProcessor processing different template sections."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    def test_processes_resources_section(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach in Resources section is expanded.

        Requirements:
            - 6.1: Fn::ForEach in Resources SHALL expand to multiple resources
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Alerts", "Notifications"],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ],
                "ExistingResource": {"Type": "AWS::S3::Bucket"},
            }
        }

        processor.process_template(context)

        # ForEach should be expanded into multiple resources
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        # ForEach key should be removed after expansion
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]
        # Existing resources should be preserved
        assert "ExistingResource" in context.fragment["Resources"]

    def test_processes_outputs_section(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach in Outputs section is expanded.

        Requirements:
            - 6.2: Fn::ForEach in Outputs SHALL expand to multiple outputs
        """
        context.fragment = {
            "Resources": {},
            "Outputs": {
                "Fn::ForEach::TopicOutputs": [
                    "TopicName",
                    ["Alerts", "Notifications"],
                    {"${TopicName}Arn": {"Value": {"Ref": "Topic${TopicName}"}}},
                ],
                "ExistingOutput": {"Value": "test"},
            },
        }

        processor.process_template(context)

        # ForEach should be expanded into multiple outputs
        assert "AlertsArn" in context.fragment["Outputs"]
        assert "NotificationsArn" in context.fragment["Outputs"]
        # ForEach key should be removed after expansion
        assert "Fn::ForEach::TopicOutputs" not in context.fragment["Outputs"]
        # Existing outputs should be preserved
        assert "ExistingOutput" in context.fragment["Outputs"]
        # Verify identifier substitution in values
        assert context.fragment["Outputs"]["AlertsArn"]["Value"] == {"Ref": "TopicAlerts"}
        assert context.fragment["Outputs"]["NotificationsArn"]["Value"] == {"Ref": "TopicNotifications"}

    def test_processes_conditions_section(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach in Conditions section is expanded.

        Requirements:
            - 6.3: Fn::ForEach in Conditions SHALL expand to multiple conditions
        """
        context.fragment = {
            "Resources": {},
            "Conditions": {
                "Fn::ForEach::EnvConditions": [
                    "Env",
                    ["Dev", "Prod"],
                    {"Is${Env}": {"Fn::Equals": [{"Ref": "Environment"}, "${Env}"]}},
                ],
                "ExistingCondition": {"Fn::Equals": ["a", "b"]},
            },
        }

        processor.process_template(context)

        # ForEach should be expanded into multiple conditions
        assert "IsDev" in context.fragment["Conditions"]
        assert "IsProd" in context.fragment["Conditions"]
        # ForEach key should be removed after expansion
        assert "Fn::ForEach::EnvConditions" not in context.fragment["Conditions"]
        # Existing conditions should be preserved
        assert "ExistingCondition" in context.fragment["Conditions"]
        # Verify identifier substitution in values
        assert context.fragment["Conditions"]["IsDev"]["Fn::Equals"][1] == "Dev"
        assert context.fragment["Conditions"]["IsProd"]["Fn::Equals"][1] == "Prod"

    def test_processes_multiple_sections(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that ForEach in multiple sections is expanded."""
        context.fragment = {
            "Conditions": {
                "Fn::ForEach::EnvConditions": [
                    "Env",
                    ["Dev", "Prod"],
                    {"Is${Env}": {"Fn::Equals": [{"Ref": "Environment"}, "${Env}"]}},
                ]
            },
            "Resources": {
                "Fn::ForEach::Topics": ["TopicName", ["Alerts"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
            },
            "Outputs": {
                "Fn::ForEach::TopicOutputs": [
                    "TopicName",
                    ["Alerts"],
                    {"${TopicName}Arn": {"Value": {"Ref": "Topic${TopicName}"}}},
                ]
            },
        }

        processor.process_template(context)

        # All ForEach constructs should be expanded
        assert "IsDev" in context.fragment["Conditions"]
        assert "IsProd" in context.fragment["Conditions"]
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "AlertsArn" in context.fragment["Outputs"]
        # ForEach keys should be removed
        assert "Fn::ForEach::EnvConditions" not in context.fragment["Conditions"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]
        assert "Fn::ForEach::TopicOutputs" not in context.fragment["Outputs"]

    def test_handles_missing_sections(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that processor handles templates with missing optional sections."""
        context.fragment = {
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}
            # No Conditions or Outputs sections
        }

        # Should not raise
        processor.process_template(context)

        assert "MyBucket" in context.fragment["Resources"]

    def test_handles_empty_sections(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that processor handles empty sections."""
        context.fragment = {"Conditions": {}, "Resources": {}, "Outputs": {}}

        # Should not raise
        processor.process_template(context)


class TestForEachProcessorCollectionResolution:
    """Tests for ForEachProcessor collection resolution."""

    def _create_processor_with_resolver(self, context):
        """Create a ForEachProcessor with an intrinsic resolver."""
        from samcli.lib.cfn_language_extensions.api import create_default_intrinsic_resolver

        resolver = create_default_intrinsic_resolver(context)
        return ForEachProcessor(intrinsic_resolver=resolver)

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing (no resolver - for literal list tests)."""
        return ForEachProcessor()

    def test_resolves_ref_to_parameter_value(self):
        """Test that Ref to parameter in collection is resolved and expanded."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        {"Ref": "TopicNames"},
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            },
            parameter_values={"TopicNames": ["Alerts", "Notifications", "Errors"]},
        )
        processor = self._create_processor_with_resolver(context)

        processor.process_template(context)

        # The ForEach should be expanded using the resolved parameter value
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "TopicErrors" in context.fragment["Resources"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]

    def test_resolves_ref_to_empty_list_parameter(self):
        """Test that Ref to parameter with empty list produces no outputs."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        {"Ref": "TopicNames"},
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            },
            parameter_values={"TopicNames": []},
        )
        processor = self._create_processor_with_resolver(context)

        processor.process_template(context)

        # Empty collection should produce no outputs
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]
        # No expanded resources should exist
        assert len(context.fragment["Resources"]) == 0

    def test_ref_to_nonexistent_parameter_raises(self):
        """Test that Ref to non-existent parameter raises exception.

        When a Ref cannot be resolved and doesn't result in a list,
        validation should fail.
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        {"Ref": "NonExistentParam"},
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            },
            parameter_values={},
        )
        processor = self._create_processor_with_resolver(context)

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "layout is incorrect" in str(exc_info.value)

    def test_literal_list_collection_expanded(self, processor: ForEachProcessor):
        """Test that literal list collections are expanded correctly."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            },
            parameter_values={},
        )

        processor.process_template(context)

        # The ForEach should be expanded
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]

    def test_resolves_parameter_default_value(self):
        """Test that parameter default values are used and expanded."""
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"TopicNames": {"Type": "CommaDelimitedList", "Default": "Alerts,Notifications,Errors"}},
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        {"Ref": "TopicNames"},
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            },
            parameter_values={},
        )

        # Set up parsed template with parameters
        context.parsed_template = ParsedTemplate(
            parameters={"TopicNames": {"Type": "CommaDelimitedList", "Default": "Alerts,Notifications,Errors"}},
            resources={},
        )
        processor = self._create_processor_with_resolver(context)

        processor.process_template(context)

        # The ForEach should be expanded using the default value
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "TopicErrors" in context.fragment["Resources"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]


class TestForEachProcessorWithIntrinsicResolver:
    """Tests for ForEachProcessor with IntrinsicResolver integration."""

    def test_uses_intrinsic_resolver_for_collection(self):
        """Test that intrinsic resolver is used to resolve and expand collections."""
        from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicResolver
        from samcli.lib.cfn_language_extensions.resolvers.fn_ref import FnRefResolver

        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        {"Ref": "TopicNames"},
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            },
            parameter_values={"TopicNames": ["Alerts", "Notifications"]},
        )

        # Create intrinsic resolver with FnRefResolver
        intrinsic_resolver = IntrinsicResolver(context)
        intrinsic_resolver.register_resolver(FnRefResolver)

        processor = ForEachProcessor(intrinsic_resolver=intrinsic_resolver)
        processor.process_template(context)

        # The ForEach should be expanded via the intrinsic resolver
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]


class TestForEachProcessorMultipleForEach:
    """Tests for ForEachProcessor with multiple ForEach constructs."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_multiple_foreach_in_same_section(self, processor: ForEachProcessor):
        """Test that multiple ForEach constructs in same section are expanded."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ],
                    "Fn::ForEach::Queues": [
                        "QueueName",
                        ["Orders", "Events"],
                        {"Queue${QueueName}": {"Type": "AWS::SQS::Queue"}},
                    ],
                    "StaticResource": {"Type": "AWS::S3::Bucket"},
                }
            }
        )

        processor.process_template(context)

        # Both ForEach constructs should be expanded
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "QueueOrders" in context.fragment["Resources"]
        assert "QueueEvents" in context.fragment["Resources"]
        # ForEach keys should be removed
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]
        assert "Fn::ForEach::Queues" not in context.fragment["Resources"]
        # Static resource should be preserved
        assert "StaticResource" in context.fragment["Resources"]

    def test_foreach_with_different_identifiers(self, processor: ForEachProcessor):
        """Test ForEach constructs with different identifiers are expanded correctly."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Loop1": ["Item", ["A", "B"], {"Resource${Item}": {"Type": "AWS::SNS::Topic"}}],
                    "Fn::ForEach::Loop2": ["Name", ["X", "Y"], {"Other${Name}": {"Type": "AWS::SQS::Queue"}}],
                }
            }
        )

        processor.process_template(context)

        # Both should be expanded with correct identifiers
        assert "ResourceA" in context.fragment["Resources"]
        assert "ResourceB" in context.fragment["Resources"]
        assert "OtherX" in context.fragment["Resources"]
        assert "OtherY" in context.fragment["Resources"]
        # ForEach keys should be removed
        assert "Fn::ForEach::Loop1" not in context.fragment["Resources"]
        assert "Fn::ForEach::Loop2" not in context.fragment["Resources"]


class TestForEachProcessorEdgeCases:
    """Tests for ForEachProcessor edge cases."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_foreach_with_single_item_collection(self, processor: ForEachProcessor):
        """Test ForEach with single item in collection expands to one output."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["OnlyOne"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand to exactly one resource
        assert "TopicOnlyOne" in context.fragment["Resources"]
        assert len(context.fragment["Resources"]) == 1
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]

    def test_foreach_with_numeric_collection_items(self, processor: ForEachProcessor):
        """Test ForEach with numeric items in collection converts to strings."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Instances": ["Index", [1, 2, 3], {"Instance${Index}": {"Type": "AWS::EC2::Instance"}}]
                }
            }
        )

        processor.process_template(context)

        # Numeric items should be converted to strings for substitution
        assert "Instance1" in context.fragment["Resources"]
        assert "Instance2" in context.fragment["Resources"]
        assert "Instance3" in context.fragment["Resources"]
        assert "Fn::ForEach::Instances" not in context.fragment["Resources"]

    def test_foreach_with_complex_body(self, processor: ForEachProcessor):
        """Test ForEach with complex template body expands correctly."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts"],
                        {
                            "Topic${TopicName}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "TopicName": "${TopicName}Topic",
                                    "Tags": [{"Key": "Name", "Value": "${TopicName}"}],
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand with all substitutions
        assert "TopicAlerts" in context.fragment["Resources"]
        resource = context.fragment["Resources"]["TopicAlerts"]
        assert resource["Properties"]["TopicName"] == "AlertsTopic"
        assert resource["Properties"]["Tags"][0]["Value"] == "Alerts"

    def test_foreach_with_special_characters_in_loop_name(self, processor: ForEachProcessor):
        """Test ForEach with special characters in loop name expands correctly."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::MyLoop123": ["Item", ["A"], {"Resource${Item}": {"Type": "AWS::SNS::Topic"}}]
                }
            }
        )

        processor.process_template(context)

        assert "ResourceA" in context.fragment["Resources"]
        assert "Fn::ForEach::MyLoop123" not in context.fragment["Resources"]

    def test_foreach_preserves_non_foreach_keys(self, processor: ForEachProcessor):
        """Test that non-ForEach keys are preserved unchanged."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ],
                    "MyQueue": {"Type": "AWS::SQS::Queue"},
                }
            }
        )

        processor.process_template(context)

        # Non-ForEach resources should be preserved exactly
        assert context.fragment["Resources"]["MyBucket"] == {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "my-bucket"},
        }
        assert context.fragment["Resources"]["MyQueue"] == {"Type": "AWS::SQS::Queue"}


class TestForEachProcessorProtocol:
    """Tests for ForEachProcessor implementing TemplateProcessor protocol."""

    def test_implements_process_template_method(self):
        """Test that ForEachProcessor has process_template method."""
        processor = ForEachProcessor()
        assert hasattr(processor, "process_template")
        assert callable(processor.process_template)

    def test_can_be_used_in_pipeline(self):
        """Test that ForEachProcessor can be used in ProcessingPipeline."""
        from samcli.lib.cfn_language_extensions.pipeline import ProcessingPipeline

        processor = ForEachProcessor()
        pipeline = ProcessingPipeline([processor])

        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": ["TopicName", ["Alerts"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
                }
            }
        )

        result = pipeline.process_template(context)

        # ForEach should be expanded
        assert "TopicAlerts" in result["Resources"]
        assert "Fn::ForEach::Topics" not in result["Resources"]

    def test_works_with_parsing_processor(self):
        """Test that ForEachProcessor works after TemplateParsingProcessor."""
        from samcli.lib.cfn_language_extensions.pipeline import ProcessingPipeline
        from samcli.lib.cfn_language_extensions.processors.parsing import TemplateParsingProcessor

        parsing_processor = TemplateParsingProcessor()
        foreach_processor = ForEachProcessor()
        pipeline = ProcessingPipeline([parsing_processor, foreach_processor])

        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            }
        )

        result = pipeline.process_template(context)

        # Parsing should have set parsed_template
        assert context.parsed_template is not None
        # ForEach should be expanded
        assert "TopicAlerts" in result["Resources"]
        assert "TopicNotifications" in result["Resources"]
        assert "Fn::ForEach::Topics" not in result["Resources"]


class TestForEachExpansionLogic:
    """Tests for ForEach loop expansion logic (Task 12.2).

    Requirements:
        - 6.1: Fn::ForEach in Resources SHALL expand to multiple resources
        - 6.2: Fn::ForEach in Outputs SHALL expand to multiple outputs
        - 6.3: Fn::ForEach in Conditions SHALL expand to multiple conditions
        - 6.4: Nested Fn::ForEach SHALL expand recursively
        - 6.5: Collection items SHALL be iterated in order
        - 6.9: Identifier SHALL be substituted in both keys and values
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_single_foreach_expansion(self, processor: ForEachProcessor):
        """Test that a single ForEach expands correctly.

        Requirement 6.1: Fn::ForEach in Resources SHALL expand to multiple resources
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications", "Errors"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand to 3 resources
        assert len(context.fragment["Resources"]) == 3
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert "TopicErrors" in context.fragment["Resources"]
        # Original ForEach key should be removed
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]

    def test_multiple_items_in_collection(self, processor: ForEachProcessor):
        """Test ForEach with multiple items produces correct number of outputs.

        Requirement 6.5: Collection items SHALL be iterated in order
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Buckets": [
                        "BucketName",
                        ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
                        {"Bucket${BucketName}": {"Type": "AWS::S3::Bucket"}},
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand to 5 resources
        assert len(context.fragment["Resources"]) == 5
        assert "BucketAlpha" in context.fragment["Resources"]
        assert "BucketBeta" in context.fragment["Resources"]
        assert "BucketGamma" in context.fragment["Resources"]
        assert "BucketDelta" in context.fragment["Resources"]
        assert "BucketEpsilon" in context.fragment["Resources"]

    def test_nested_foreach_expansion(self, processor: ForEachProcessor):
        """Test that nested ForEach constructs expand recursively.

        Requirement 6.4: Nested Fn::ForEach SHALL expand recursively
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Environments": [
                        "Env",
                        ["Dev", "Prod"],
                        {
                            "Fn::ForEach::Services": [
                                "Service",
                                ["Api", "Web"],
                                {
                                    "${Env}${Service}Bucket": {
                                        "Type": "AWS::S3::Bucket",
                                        "Properties": {"BucketName": "${Env}-${Service}-bucket"},
                                    }
                                },
                            ]
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand to 2 * 2 = 4 resources
        assert len(context.fragment["Resources"]) == 4
        assert "DevApiBucket" in context.fragment["Resources"]
        assert "DevWebBucket" in context.fragment["Resources"]
        assert "ProdApiBucket" in context.fragment["Resources"]
        assert "ProdWebBucket" in context.fragment["Resources"]

        # Verify nested substitution in properties
        assert context.fragment["Resources"]["DevApiBucket"]["Properties"]["BucketName"] == "Dev-Api-bucket"
        assert context.fragment["Resources"]["ProdWebBucket"]["Properties"]["BucketName"] == "Prod-Web-bucket"

    def test_identifier_substitution_in_keys(self, processor: ForEachProcessor):
        """Test that identifier is substituted in dictionary keys.

        Requirement 6.9: Identifier SHALL be substituted in both keys and values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "Name",
                        ["Alerts"],
                        {"Topic${Name}": {"Type": "AWS::SNS::Topic", "Properties": {"${Name}Property": "value"}}},
                    ]
                }
            }
        )

        processor.process_template(context)

        # Key should be substituted
        assert "TopicAlerts" in context.fragment["Resources"]
        # Property key should also be substituted
        assert "AlertsProperty" in context.fragment["Resources"]["TopicAlerts"]["Properties"]

    def test_identifier_substitution_in_values(self, processor: ForEachProcessor):
        """Test that identifier is substituted in values.

        Requirement 6.9: Identifier SHALL be substituted in both keys and values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts"],
                        {
                            "Topic${TopicName}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "DisplayName": "${TopicName} Topic",
                                    "TopicName": "my-${TopicName}-topic",
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        resource = context.fragment["Resources"]["TopicAlerts"]
        assert resource["Properties"]["DisplayName"] == "Alerts Topic"
        assert resource["Properties"]["TopicName"] == "my-Alerts-topic"

    def test_identifier_substitution_in_nested_structures(self, processor: ForEachProcessor):
        """Test that identifier is substituted in deeply nested structures.

        Requirement 6.9: Identifier SHALL be substituted in both keys and values
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "Name",
                        ["Alerts"],
                        {
                            "Topic${Name}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "Tags": [
                                        {"Key": "Name", "Value": "${Name}"},
                                        {"Key": "Environment", "Value": "${Name}-env"},
                                    ],
                                    "Subscription": [{"Endpoint": "https://example.com/${Name}", "Protocol": "https"}],
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        resource = context.fragment["Resources"]["TopicAlerts"]
        assert resource["Properties"]["Tags"][0]["Value"] == "Alerts"
        assert resource["Properties"]["Tags"][1]["Value"] == "Alerts-env"
        assert resource["Properties"]["Subscription"][0]["Endpoint"] == "https://example.com/Alerts"

    def test_empty_collection_produces_no_outputs(self, processor: ForEachProcessor):
        """Test that empty collection produces no outputs.

        Requirement 6.5: Empty collection produces no outputs
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        [],  # Empty collection
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ],
                    "StaticResource": {"Type": "AWS::S3::Bucket"},
                }
            }
        )

        processor.process_template(context)

        # Only the static resource should remain
        assert len(context.fragment["Resources"]) == 1
        assert "StaticResource" in context.fragment["Resources"]
        assert "Fn::ForEach::Topics" not in context.fragment["Resources"]

    def test_collection_items_iterated_in_order(self, processor: ForEachProcessor):
        """Test that collection items are iterated in order.

        Requirement 6.5: Collection items SHALL be iterated in order
        """
        context = TemplateProcessingContext(
            fragment={
                "Outputs": {
                    "Fn::ForEach::Values": [
                        "Item",
                        ["First", "Second", "Third"],
                        {"Output${Item}": {"Value": "${Item}"}},
                    ]
                }
            }
        )

        processor.process_template(context)

        # Verify all outputs exist with correct values
        assert context.fragment["Outputs"]["OutputFirst"]["Value"] == "First"
        assert context.fragment["Outputs"]["OutputSecond"]["Value"] == "Second"
        assert context.fragment["Outputs"]["OutputThird"]["Value"] == "Third"

    def test_deeply_nested_foreach(self, processor: ForEachProcessor):
        """Test three levels of nested ForEach."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Regions": [
                        "Region",
                        ["East", "West"],
                        {
                            "Fn::ForEach::Environments": [
                                "Env",
                                ["Dev", "Prod"],
                                {
                                    "Fn::ForEach::Services": [
                                        "Svc",
                                        ["Api"],
                                        {
                                            "${Region}${Env}${Svc}": {
                                                "Type": "AWS::Lambda::Function",
                                                "Properties": {"FunctionName": "${Region}-${Env}-${Svc}"},
                                            }
                                        },
                                    ]
                                },
                            ]
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        # Should expand to 2 * 2 * 1 = 4 resources
        assert len(context.fragment["Resources"]) == 4
        assert "EastDevApi" in context.fragment["Resources"]
        assert "EastProdApi" in context.fragment["Resources"]
        assert "WestDevApi" in context.fragment["Resources"]
        assert "WestProdApi" in context.fragment["Resources"]

        # Verify property substitution
        assert context.fragment["Resources"]["EastDevApi"]["Properties"]["FunctionName"] == "East-Dev-Api"
        assert context.fragment["Resources"]["WestProdApi"]["Properties"]["FunctionName"] == "West-Prod-Api"

    def test_foreach_preserves_non_string_values(self, processor: ForEachProcessor):
        """Test that non-string values (int, bool, etc.) are preserved."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Queues": [
                        "Name",
                        ["Orders"],
                        {
                            "Queue${Name}": {
                                "Type": "AWS::SQS::Queue",
                                "Properties": {
                                    "DelaySeconds": 30,
                                    "FifoQueue": True,
                                    "MaximumMessageSize": 262144,
                                    "QueueName": "${Name}Queue",
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        resource = context.fragment["Resources"]["QueueOrders"]
        assert resource["Properties"]["DelaySeconds"] == 30
        assert resource["Properties"]["FifoQueue"] is True
        assert resource["Properties"]["MaximumMessageSize"] == 262144
        assert resource["Properties"]["QueueName"] == "OrdersQueue"

    def test_foreach_with_intrinsic_functions_in_body(self, processor: ForEachProcessor):
        """Test that intrinsic functions in body are preserved during expansion."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "Name",
                        ["Alerts"],
                        {
                            "Topic${Name}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "TopicName": {"Fn::Sub": "${Name}-topic"},
                                    "KmsMasterKeyId": {"Ref": "KmsKey"},
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        resource = context.fragment["Resources"]["TopicAlerts"]
        # Fn::Sub should be preserved but with identifier substituted
        assert resource["Properties"]["TopicName"] == {"Fn::Sub": "Alerts-topic"}
        # Ref should be preserved unchanged
        assert resource["Properties"]["KmsMasterKeyId"] == {"Ref": "KmsKey"}

    def test_foreach_expansion_in_outputs_with_refs(self, processor: ForEachProcessor):
        """Test ForEach expansion in Outputs section with Ref intrinsics.

        Requirement 6.2: Fn::ForEach in Outputs SHALL expand to multiple outputs
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Outputs": {
                    "Fn::ForEach::TopicArns": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {
                            "${TopicName}TopicArn": {
                                "Description": "ARN of ${TopicName} topic",
                                "Value": {"Ref": "Topic${TopicName}"},
                                "Export": {"Name": "${TopicName}-topic-arn"},
                            }
                        },
                    ]
                },
            }
        )

        processor.process_template(context)

        # Should expand to 2 outputs
        assert len(context.fragment["Outputs"]) == 2

        alerts_output = context.fragment["Outputs"]["AlertsTopicArn"]
        assert alerts_output["Description"] == "ARN of Alerts topic"
        assert alerts_output["Value"] == {"Ref": "TopicAlerts"}
        assert alerts_output["Export"]["Name"] == "Alerts-topic-arn"

        notifications_output = context.fragment["Outputs"]["NotificationsTopicArn"]
        assert notifications_output["Description"] == "ARN of Notifications topic"
        assert notifications_output["Value"] == {"Ref": "TopicNotifications"}
        assert notifications_output["Export"]["Name"] == "Notifications-topic-arn"

    def test_foreach_expansion_in_conditions(self, processor: ForEachProcessor):
        """Test ForEach expansion in Conditions section.

        Requirement 6.3: Fn::ForEach in Conditions SHALL expand to multiple conditions
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Conditions": {
                    "Fn::ForEach::EnvConditions": [
                        "Env",
                        ["Development", "Staging", "Production"],
                        {"Is${Env}": {"Fn::Equals": [{"Ref": "Environment"}, "${Env}"]}},
                    ]
                },
            }
        )

        processor.process_template(context)

        # Should expand to 3 conditions
        assert len(context.fragment["Conditions"]) == 3

        assert "IsDevelopment" in context.fragment["Conditions"]
        assert "IsStaging" in context.fragment["Conditions"]
        assert "IsProduction" in context.fragment["Conditions"]

        # Verify condition structure
        dev_condition = context.fragment["Conditions"]["IsDevelopment"]
        assert dev_condition["Fn::Equals"][1] == "Development"

        prod_condition = context.fragment["Conditions"]["IsProduction"]
        assert prod_condition["Fn::Equals"][1] == "Production"


class TestForEachIdentifierConflictDetection:
    """Tests for ForEach identifier conflict detection.

    Requirement 6.6: WHEN Fn::ForEach identifier conflicts with an existing parameter name
    or another loop identifier, THEN THE Resolver SHALL raise an Invalid_Template_Exception
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_identifier_conflicts_with_parameter_name(self, processor: ForEachProcessor):
        """Test that identifier conflicting with parameter name raises exception.

        Requirement 6.6: Raise Invalid_Template_Exception for identifier conflicts
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"TopicName": {"Type": "String", "Default": "MyTopic"}},
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",  # Conflicts with parameter name
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'TopicName' conflicts with parameter name" in str(exc_info.value)

    def test_identifier_conflicts_with_parameter_name_from_parsed_template(self, processor: ForEachProcessor):
        """Test that identifier conflicting with parameter from parsed_template raises exception.

        Requirement 6.6: Raise Invalid_Template_Exception for identifier conflicts
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "Environment",  # Conflicts with parameter name
                        ["Dev", "Prod"],
                        {"${Environment}Bucket": {"Type": "AWS::S3::Bucket"}},
                    ]
                }
            }
        )

        # Set up parsed template with parameters
        context.parsed_template = ParsedTemplate(
            parameters={"Environment": {"Type": "String", "Default": "Dev"}}, resources={}
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'Environment' conflicts with parameter name" in str(exc_info.value)

    def test_identifier_conflicts_with_nested_loop_identifier(self, processor: ForEachProcessor):
        """Test that identifier conflicting with nested loop identifier raises exception.

        Requirement 6.6: Raise Invalid_Template_Exception for identifier conflicts
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Outer": [
                        "Name",
                        ["A", "B"],
                        {
                            "Fn::ForEach::Inner": [
                                "Name",  # Conflicts with outer loop identifier
                                ["X", "Y"],
                                {"${Name}Resource": {"Type": "AWS::SNS::Topic"}},
                            ]
                        },
                    ]
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'Name' conflicts with another loop identifier" in str(exc_info.value)

    def test_identifier_conflicts_with_deeply_nested_loop_identifier(self, processor: ForEachProcessor):
        """Test that identifier conflicting with deeply nested loop identifier raises exception.

        Requirement 6.6: Raise Invalid_Template_Exception for identifier conflicts
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Level1": [
                        "Env",
                        ["Dev", "Prod"],
                        {
                            "Fn::ForEach::Level2": [
                                "Region",
                                ["East", "West"],
                                {
                                    "Fn::ForEach::Level3": [
                                        "Env",  # Conflicts with Level1 identifier
                                        ["Api", "Web"],
                                        {"${Env}${Region}Resource": {"Type": "AWS::SNS::Topic"}},
                                    ]
                                },
                            ]
                        },
                    ]
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'Env' conflicts with another loop identifier" in str(exc_info.value)

    def test_valid_identifier_no_conflict_with_parameters(self, processor: ForEachProcessor):
        """Test that valid identifier without conflicts passes validation."""
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Environment": {"Type": "String", "Default": "Dev"}},
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",  # Does not conflict with "Environment"
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        # Should not raise
        processor.process_template(context)

        # Verify expansion worked
        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]

    def test_valid_nested_identifiers_no_conflict(self, processor: ForEachProcessor):
        """Test that valid nested identifiers without conflicts pass validation."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Outer": [
                        "Env",
                        ["Dev", "Prod"],
                        {
                            "Fn::ForEach::Inner": [
                                "Service",  # Different from "Env"
                                ["Api", "Web"],
                                {"${Env}${Service}Bucket": {"Type": "AWS::S3::Bucket"}},
                            ]
                        },
                    ]
                }
            }
        )

        # Should not raise
        processor.process_template(context)

        # Verify expansion worked
        assert "DevApiBucket" in context.fragment["Resources"]
        assert "DevWebBucket" in context.fragment["Resources"]
        assert "ProdApiBucket" in context.fragment["Resources"]
        assert "ProdWebBucket" in context.fragment["Resources"]

    def test_valid_three_level_nested_identifiers(self, processor: ForEachProcessor):
        """Test that valid three-level nested identifiers pass validation."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Level1": [
                        "Env",
                        ["Dev"],
                        {
                            "Fn::ForEach::Level2": [
                                "Region",
                                ["East"],
                                {
                                    "Fn::ForEach::Level3": [
                                        "Service",  # All different identifiers
                                        ["Api"],
                                        {"${Env}${Region}${Service}": {"Type": "AWS::SNS::Topic"}},
                                    ]
                                },
                            ]
                        },
                    ]
                }
            }
        )

        # Should not raise
        processor.process_template(context)

        # Verify expansion worked
        assert "DevEastApi" in context.fragment["Resources"]

    def test_identifier_conflict_with_multiple_parameters(self, processor: ForEachProcessor):
        """Test identifier conflict detection with multiple parameters."""
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {
                    "Environment": {"Type": "String"},
                    "Region": {"Type": "String"},
                    "ServiceName": {"Type": "String"},
                },
                "Resources": {
                    "Fn::ForEach::Services": [
                        "Region",  # Conflicts with parameter "Region"
                        ["East", "West"],
                        {"${Region}Service": {"Type": "AWS::Lambda::Function"}},
                    ]
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'Region' conflicts with parameter name" in str(exc_info.value)

    def test_no_conflict_with_empty_parameters(self, processor: ForEachProcessor):
        """Test that identifier validation works with empty parameters section."""
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {},
                "Resources": {
                    "Fn::ForEach::Topics": ["TopicName", ["Alerts"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
                },
            }
        )

        # Should not raise
        processor.process_template(context)

        assert "TopicAlerts" in context.fragment["Resources"]

    def test_no_conflict_without_parameters_section(self, processor: ForEachProcessor):
        """Test that identifier validation works without parameters section."""
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": ["TopicName", ["Alerts"], {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}]
                }
            }
        )

        # Should not raise
        processor.process_template(context)

        assert "TopicAlerts" in context.fragment["Resources"]

    def test_sibling_foreach_can_use_same_identifier(self, processor: ForEachProcessor):
        """Test that sibling ForEach constructs can use the same identifier.

        Sibling loops (not nested) should be allowed to use the same identifier
        since they don't have overlapping scopes.
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": ["Name", ["Alerts"], {"Topic${Name}": {"Type": "AWS::SNS::Topic"}}],
                    "Fn::ForEach::Queues": [
                        "Name",  # Same identifier as Topics, but sibling not nested
                        ["Orders"],
                        {"Queue${Name}": {"Type": "AWS::SQS::Queue"}},
                    ],
                }
            }
        )

        # Should not raise - sibling loops can use same identifier
        processor.process_template(context)

        assert "TopicAlerts" in context.fragment["Resources"]
        assert "QueueOrders" in context.fragment["Resources"]


# =============================================================================
# Property-Based Tests for ForEach Processor
# =============================================================================


# =============================================================================
# Parametrized Tests for ForEach Processor
# =============================================================================


class TestForEachExpansionCountProperty:
    """Parametrized tests for ForEach expansion count.

    Property 9: Fn::ForEach Expansion Count
    For any Fn::ForEach with a collection of N items, the expansion SHALL produce
    exactly N outputs.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
    """

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta", "Gamma"], "Topics"),
            ("Name", [], "Empty"),
            ("Svc", ["A"], "Single"),
        ],
    )
    def test_foreach_resources_expansion_count(self, identifier, collection_items, loop_name):
        """
        Property 9: A collection with N items produces exactly N expanded resources.

        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {f"Resource${{{identifier}}}": {"Type": "AWS::SNS::Topic"}},
                    ]
                }
            }
        )

        processor.process_template(context)

        assert len(context.fragment["Resources"]) == len(collection_items)
        for item in collection_items:
            assert f"Resource{item}" in context.fragment["Resources"]
        assert f"Fn::ForEach::{loop_name}" not in context.fragment["Resources"]

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["X", "Y", "Z"], "Outputs"),
            ("Name", [], "EmptyOutputs"),
            ("Svc", ["One", "Two"], "TwoOutputs"),
        ],
    )
    def test_foreach_outputs_expansion_count(self, identifier, collection_items, loop_name):
        """
        Property 9: A collection with N items in Outputs produces exactly N outputs.

        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Outputs": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {f"Output${{{identifier}}}": {"Value": f"${{{identifier}}}"}},
                    ]
                },
            }
        )

        processor.process_template(context)

        if len(collection_items) == 0:
            assert "Outputs" not in context.fragment or len(context.fragment.get("Outputs", {})) == 0
        else:
            assert len(context.fragment["Outputs"]) == len(collection_items)
            for item in collection_items:
                assert f"Output{item}" in context.fragment["Outputs"]

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Env", ["prod", "dev", "staging"], "Conditions"),
            ("Name", [], "EmptyConds"),
            ("Item", ["Alpha"], "SingleCond"),
        ],
    )
    def test_foreach_conditions_expansion_count(self, identifier, collection_items, loop_name):
        """
        Property 9: A collection with N items in Conditions produces exactly N conditions.

        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Conditions": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {f"Is${{{identifier}}}": {"Fn::Equals": [{"Ref": "Env"}, f"${{{identifier}}}"]}},
                    ]
                },
            }
        )

        processor.process_template(context)

        if len(collection_items) == 0:
            assert "Conditions" not in context.fragment or len(context.fragment.get("Conditions", {})) == 0
        else:
            assert len(context.fragment["Conditions"]) == len(collection_items)
            for item in collection_items:
                assert f"Is{item}" in context.fragment["Conditions"]

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta", "Gamma"], "OrderTest"),
            ("Svc", ["X", "Y"], "TwoItems"),
        ],
    )
    def test_foreach_expansion_preserves_iteration_order(self, identifier, collection_items, loop_name):
        """
        Property 9: Collection items are iterated in order and substituted values match.

        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Outputs": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {f"Output${{{identifier}}}": {"Value": f"${{{identifier}}}"}},
                    ]
                },
            }
        )

        processor.process_template(context)

        for item in collection_items:
            assert context.fragment["Outputs"][f"Output{item}"]["Value"] == item


class TestForEachNestedExpansionProperty:
    """Parametrized tests for nested ForEach expansion.

    Property 10: Fn::ForEach Nested Expansion
    For any nested Fn::ForEach with outer collection of M items and inner collection
    of N items, the expansion SHALL produce M × N outputs.

    **Validates: Requirements 6.4**
    """

    @pytest.mark.parametrize(
        "outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop",
        [
            ("Env", "Svc", ["prod", "dev"], ["Api", "Web"], "Envs", "Services"),
            ("Region", "Tier", ["us", "eu", "ap"], ["front", "back"], "Regions", "Tiers"),
        ],
    )
    def test_nested_foreach_produces_m_times_n_outputs(
        self, outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop
    ):
        """
        Property 10: Nested ForEach with M outer and N inner items produces M*N resources.

        **Validates: Requirements 6.4**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{outer_loop}": [
                        outer_id,
                        outer_items,
                        {
                            f"Fn::ForEach::{inner_loop}": [
                                inner_id,
                                inner_items,
                                {f"Resource${{{outer_id}}}${{{inner_id}}}": {"Type": "AWS::SNS::Topic"}},
                            ]
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        expected_count = len(outer_items) * len(inner_items)
        assert len(context.fragment["Resources"]) == expected_count

        for outer_item in outer_items:
            for inner_item in inner_items:
                assert f"Resource{outer_item}{inner_item}" in context.fragment["Resources"]

    @pytest.mark.parametrize(
        "outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop",
        [
            ("Env", "Svc", ["prod", "dev"], ["Api", "Web"], "Envs", "Services"),
            ("Region", "Tier", ["us", "eu"], ["front", "back", "data"], "Regions", "Tiers"),
        ],
    )
    def test_nested_foreach_correct_variable_substitution(
        self, outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop
    ):
        """
        Property 10: Nested ForEach correctly substitutes variables at each level.

        **Validates: Requirements 6.4**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{outer_loop}": [
                        outer_id,
                        outer_items,
                        {
                            f"Fn::ForEach::{inner_loop}": [
                                inner_id,
                                inner_items,
                                {
                                    f"Resource${{{outer_id}}}${{{inner_id}}}": {
                                        "Type": "AWS::SNS::Topic",
                                        "Properties": {
                                            "OuterValue": f"${{{outer_id}}}",
                                            "InnerValue": f"${{{inner_id}}}",
                                            "CombinedValue": f"${{{outer_id}}}-${{{inner_id}}}",
                                        },
                                    }
                                },
                            ]
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for outer_item in outer_items:
            for inner_item in inner_items:
                resource = context.fragment["Resources"][f"Resource{outer_item}{inner_item}"]
                assert resource["Properties"]["OuterValue"] == outer_item
                assert resource["Properties"]["InnerValue"] == inner_item
                assert resource["Properties"]["CombinedValue"] == f"{outer_item}-{inner_item}"

    @pytest.mark.parametrize(
        "outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop",
        [
            ("Env", "Svc", ["prod", "dev"], ["Api", "Web"], "Envs", "Services"),
        ],
    )
    def test_nested_foreach_in_outputs_section(
        self, outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop
    ):
        """
        Property 10: Nested ForEach in Outputs produces M*N outputs.

        **Validates: Requirements 6.4**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Outputs": {
                    f"Fn::ForEach::{outer_loop}": [
                        outer_id,
                        outer_items,
                        {
                            f"Fn::ForEach::{inner_loop}": [
                                inner_id,
                                inner_items,
                                {
                                    f"Output${{{outer_id}}}${{{inner_id}}}": {
                                        "Value": f"${{{outer_id}}}-${{{inner_id}}}"
                                    }
                                },
                            ]
                        },
                    ]
                },
            }
        )

        processor.process_template(context)

        expected_count = len(outer_items) * len(inner_items)
        assert len(context.fragment["Outputs"]) == expected_count

        for outer_item in outer_items:
            for inner_item in inner_items:
                output_key = f"Output{outer_item}{inner_item}"
                assert context.fragment["Outputs"][output_key]["Value"] == f"{outer_item}-{inner_item}"

    @pytest.mark.parametrize(
        "outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop",
        [
            ("Env", "Svc", ["prod", "dev"], ["Api", "Web"], "Envs", "Services"),
        ],
    )
    def test_nested_foreach_in_conditions_section(
        self, outer_id, inner_id, outer_items, inner_items, outer_loop, inner_loop
    ):
        """
        Property 10: Nested ForEach in Conditions produces M*N conditions.

        **Validates: Requirements 6.4**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {},
                "Conditions": {
                    f"Fn::ForEach::{outer_loop}": [
                        outer_id,
                        outer_items,
                        {
                            f"Fn::ForEach::{inner_loop}": [
                                inner_id,
                                inner_items,
                                {
                                    f"Is${{{outer_id}}}${{{inner_id}}}": {
                                        "Fn::Equals": [{"Ref": "Env"}, f"${{{outer_id}}}-${{{inner_id}}}"]
                                    }
                                },
                            ]
                        },
                    ]
                },
            }
        )

        processor.process_template(context)

        expected_count = len(outer_items) * len(inner_items)
        assert len(context.fragment["Conditions"]) == expected_count

        for outer_item in outer_items:
            for inner_item in inner_items:
                cond_key = f"Is{outer_item}{inner_item}"
                assert context.fragment["Conditions"][cond_key]["Fn::Equals"][1] == f"{outer_item}-{inner_item}"


class TestForEachIdentifierSubstitutionProperty:
    """Parametrized tests for ForEach identifier substitution.

    Property 11: Fn::ForEach Identifier Substitution
    For any Fn::ForEach expansion, the loop variable identifier SHALL be substituted
    in both logical IDs (keys) and all property values throughout the template body.

    **Validates: Requirements 6.9**
    """

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta"], "Topics"),
            ("Svc", ["Api", "Web", "Worker"], "Services"),
        ],
    )
    def test_identifier_substituted_in_dictionary_keys(self, identifier, collection_items, loop_name):
        """
        Property 11: ${identifier} in dictionary keys is replaced with the collection item value.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource${{{identifier}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {f"${{{identifier}}}Property": "value"},
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for item in collection_items:
            assert f"Resource{item}" in context.fragment["Resources"]
            resource = context.fragment["Resources"][f"Resource{item}"]
            assert f"{item}Property" in resource["Properties"]

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta"], "Topics"),
            ("Svc", ["Api", "Web", "Worker"], "Services"),
        ],
    )
    def test_identifier_substituted_in_string_values(self, identifier, collection_items, loop_name):
        """
        Property 11: ${identifier} in string values is replaced with the collection item value.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource${{{identifier}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "SingleSubstitution": f"${{{identifier}}}",
                                    "PrefixSubstitution": f"prefix-${{{identifier}}}",
                                    "SuffixSubstitution": f"${{{identifier}}}-suffix",
                                    "MultipleSubstitution": f"${{{identifier}}}-middle-${{{identifier}}}",
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for item in collection_items:
            props = context.fragment["Resources"][f"Resource{item}"]["Properties"]
            assert props["SingleSubstitution"] == item
            assert props["PrefixSubstitution"] == f"prefix-{item}"
            assert props["SuffixSubstitution"] == f"{item}-suffix"
            assert props["MultipleSubstitution"] == f"{item}-middle-{item}"

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta"], "Topics"),
            ("Svc", ["Api", "Web"], "Services"),
        ],
    )
    def test_identifier_substituted_in_nested_dictionary_keys_and_values(self, identifier, collection_items, loop_name):
        """
        Property 11: ${identifier} in nested dictionary keys and values is replaced.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource${{{identifier}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "Level1": {
                                        f"${{{identifier}}}Key": f"${{{identifier}}}Value",
                                        "Level2": {f"Nested${{{identifier}}}Key": f"Nested${{{identifier}}}Value"},
                                    }
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for item in collection_items:
            level1 = context.fragment["Resources"][f"Resource{item}"]["Properties"]["Level1"]
            assert f"{item}Key" in level1
            assert level1[f"{item}Key"] == f"{item}Value"
            level2 = level1["Level2"]
            assert f"Nested{item}Key" in level2
            assert level2[f"Nested{item}Key"] == f"Nested{item}Value"

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta"], "Topics"),
            ("Svc", ["Api", "Web", "Worker"], "Services"),
        ],
    )
    def test_identifier_substituted_in_list_items(self, identifier, collection_items, loop_name):
        """
        Property 11: ${identifier} in list items is replaced.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource${{{identifier}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "StringList": [
                                        f"${{{identifier}}}",
                                        f"prefix-${{{identifier}}}",
                                        f"${{{identifier}}}-suffix",
                                    ],
                                    "Tags": [
                                        {"Key": "Name", "Value": f"${{{identifier}}}"},
                                        {"Key": f"${{{identifier}}}Tag", "Value": "static"},
                                    ],
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for item in collection_items:
            props = context.fragment["Resources"][f"Resource{item}"]["Properties"]
            assert props["StringList"][0] == item
            assert props["StringList"][1] == f"prefix-{item}"
            assert props["StringList"][2] == f"{item}-suffix"
            assert props["Tags"][0]["Value"] == item
            assert props["Tags"][1]["Key"] == f"{item}Tag"

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name",
        [
            ("Item", ["Alpha", "Beta"], "Topics"),
            ("Svc", ["Api"], "SingleService"),
        ],
    )
    def test_all_occurrences_of_identifier_are_replaced(self, identifier, collection_items, loop_name):
        """
        Property 11: ALL occurrences of ${identifier} SHALL be replaced.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        placeholder = f"${{{identifier}}}"

        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource{placeholder}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    f"{placeholder}Prop": f"{placeholder}",
                                    "Nested": {f"Key{placeholder}": f"Value{placeholder}"},
                                    "List": [f"{placeholder}", {"Tag": f"{placeholder}"}],
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        def contains_placeholder(obj, ph):
            if isinstance(obj, str):
                return ph in obj
            elif isinstance(obj, dict):
                return any(contains_placeholder(k, ph) or contains_placeholder(v, ph) for k, v in obj.items())
            elif isinstance(obj, list):
                return any(contains_placeholder(i, ph) for i in obj)
            return False

        for resource_key, resource_value in context.fragment["Resources"].items():
            assert not contains_placeholder(resource_key, placeholder)
            assert not contains_placeholder(resource_value, placeholder)

    @pytest.mark.parametrize(
        "identifier, collection_items, loop_name, static_int, static_bool",
        [
            ("Item", ["Alpha", "Beta"], "Topics", 42, True),
            ("Svc", ["Api", "Web"], "Services", 0, False),
        ],
    )
    def test_non_string_values_preserved_during_substitution(
        self, identifier, collection_items, loop_name, static_int, static_bool
    ):
        """
        Property 11: Non-string values (integers, booleans, None) SHALL be preserved.

        **Validates: Requirements 6.9**
        """
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    f"Fn::ForEach::{loop_name}": [
                        identifier,
                        collection_items,
                        {
                            f"Resource${{{identifier}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "IntValue": static_int,
                                    "BoolValue": static_bool,
                                    "NullValue": None,
                                    "StringValue": f"${{{identifier}}}",
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        for item in collection_items:
            props = context.fragment["Resources"][f"Resource{item}"]["Properties"]
            assert props["IntValue"] == static_int
            assert isinstance(props["IntValue"], int)
            assert props["BoolValue"] == static_bool
            assert isinstance(props["BoolValue"], bool)
            assert props["NullValue"] is None
            assert props["StringValue"] == item


class TestForEachProcessorCloudDependentCollectionValidation:
    """Tests for ForEachProcessor validation of cloud-dependent collections."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def _create_processor_with_resolver(self, context):
        """Create a ForEachProcessor with an intrinsic resolver."""
        from samcli.lib.cfn_language_extensions.api import create_default_intrinsic_resolver

        resolver = create_default_intrinsic_resolver(context)
        return ForEachProcessor(intrinsic_resolver=resolver)

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    def test_fn_getatt_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that Fn::GetAtt in collection raises InvalidTemplateException.

        Requirement 5.1: Raise error for Fn::GetAtt in collection
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Fn::GetAtt": ["SomeResource", "OutputList"]},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        # Requirement 5.4: Error message explains collection cannot be resolved locally
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "Fn::GetAtt" in error_message
        # Requirement 5.5: Error message suggests parameter workaround
        assert "Workaround" in error_message
        assert "parameter" in error_message.lower()
        assert "--parameter-overrides" in error_message

    def test_fn_getatt_shorthand_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that !GetAtt shorthand in collection raises InvalidTemplateException.

        Requirement 5.1: Raise error for Fn::GetAtt in collection
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"!GetAtt": "SomeResource.OutputList"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message

    def test_fn_importvalue_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that Fn::ImportValue in collection raises InvalidTemplateException.

        Requirement 5.2: Raise error for Fn::ImportValue in collection
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Fn::ImportValue": "SharedFunctionNames"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        # Requirement 5.4: Error message explains collection cannot be resolved locally
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "Fn::ImportValue" in error_message
        # Requirement 5.5: Error message suggests parameter workaround
        assert "Workaround" in error_message
        assert "parameter" in error_message.lower()

    def test_fn_importvalue_shorthand_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that !ImportValue shorthand in collection raises InvalidTemplateException.

        Requirement 5.2: Raise error for Fn::ImportValue in collection
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"!ImportValue": "SharedFunctionNames"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message

    def test_ssm_dynamic_reference_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that SSM dynamic reference in collection raises InvalidTemplateException.

        Requirement 5.3: Raise error for SSM/Secrets Manager dynamic references
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    "{{resolve:ssm:/my/function/names}}",
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        # Requirement 5.4: Error message explains collection cannot be resolved locally
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "Systems Manager Parameter Store" in error_message
        # Requirement 5.5: Error message suggests parameter workaround
        assert "Workaround" in error_message
        assert "parameter" in error_message.lower()

    def test_ssm_secure_dynamic_reference_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that SSM SecureString dynamic reference in collection raises error.

        Requirement 5.3: Raise error for SSM/Secrets Manager dynamic references
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    "{{resolve:ssm-secure:/my/secure/names}}",
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "SecureString" in error_message

    def test_secretsmanager_dynamic_reference_in_collection_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that Secrets Manager dynamic reference in collection raises error.

        Requirement 5.3: Raise error for SSM/Secrets Manager dynamic references
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    "{{resolve:secretsmanager:my-secret:SecretString:names}}",
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "Secrets Manager" in error_message

    def test_static_list_collection_succeeds(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that static list collections work correctly.

        Requirement 5.6: Static list collections work correctly
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta", "Gamma"],
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        # Should not raise
        processor.process_template(context)

        # Verify expansion
        assert "AlphaFunction" in context.fragment["Resources"]
        assert "BetaFunction" in context.fragment["Resources"]
        assert "GammaFunction" in context.fragment["Resources"]

    def test_parameter_reference_collection_succeeds(self, context: TemplateProcessingContext):
        """Test that parameter reference collections work correctly."""
        context.fragment = {
            "Parameters": {"FunctionNames": {"Type": "CommaDelimitedList", "Default": "Alpha,Beta,Gamma"}},
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Ref": "FunctionNames"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            },
        }
        context.parameter_values = {"FunctionNames": ["Alpha", "Beta", "Gamma"]}
        processor = self._create_processor_with_resolver(context)

        # Should not raise
        processor.process_template(context)

        # Verify expansion
        assert "AlphaFunction" in context.fragment["Resources"]
        assert "BetaFunction" in context.fragment["Resources"]
        assert "GammaFunction" in context.fragment["Resources"]

    def test_parameter_reference_with_default_value_succeeds(self, context: TemplateProcessingContext):
        """Test that parameter reference with default value works correctly."""
        context.fragment = {
            "Parameters": {"FunctionNames": {"Type": "CommaDelimitedList", "Default": "Alpha,Beta"}},
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Ref": "FunctionNames"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            },
        }
        context.parsed_template = ParsedTemplate(
            parameters={"FunctionNames": {"Type": "CommaDelimitedList", "Default": "Alpha,Beta"}},
            resources={},
        )
        # No parameter_values provided, should use default
        processor = self._create_processor_with_resolver(context)

        # Should not raise
        processor.process_template(context)

        # Verify expansion using default value
        assert "AlphaFunction" in context.fragment["Resources"]
        assert "BetaFunction" in context.fragment["Resources"]

    def test_fn_getatt_in_collection_item_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that Fn::GetAtt in a collection item raises error.

        Requirement 5.1: Raise error for Fn::GetAtt in collection
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", {"Fn::GetAtt": ["SomeResource", "Name"]}, "Gamma"],
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message
        assert "Fn::GetAtt" in error_message

    def test_ssm_dynamic_reference_in_collection_item_raises_error(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that SSM dynamic reference in a collection item raises error.

        Requirement 5.3: Raise error for SSM/Secrets Manager dynamic references
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "{{resolve:ssm:/my/name}}", "Gamma"],
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Unable to resolve Fn::ForEach collection locally" in error_message

    def test_error_message_includes_target_info(self, processor: ForEachProcessor, context: TemplateProcessingContext):
        """Test that error message includes the target information.

        Requirement 5.4: Error message explains collection cannot be resolved locally
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Fn::GetAtt": ["MyDynamoDB", "StreamArn"]},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        # Should include target information
        assert "MyDynamoDB" in error_message or "StreamArn" in error_message

    def test_error_message_includes_workaround_example(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that error message includes a complete workaround example.

        Requirement 5.5: Error message suggests parameter workaround
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    {"Fn::ImportValue": "SharedNames"},
                    {"${Name}Function": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        # Should include workaround with parameter definition
        assert "Parameters:" in error_message
        assert "CommaDelimitedList" in error_message
        assert "!Ref" in error_message or "Ref" in error_message
        assert "--parameter-overrides" in error_message


class TestForEachProcessorAdditionalEdgeCases:
    """Additional edge case tests for ForEach processor."""

    def test_foreach_with_empty_collection(self):
        """Test ForEach with empty collection produces no resources."""
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    [],
                    {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }
        result = process_template(template)
        assert result.get("Resources", {}) == {}

    def test_foreach_with_boolean_values_in_collection(self):
        """Test ForEach with boolean values in collection."""
        from samcli.lib.cfn_language_extensions import process_template

        template = {
            "Resources": {
                "Fn::ForEach::Flags": [
                    "Flag",
                    [True, False],
                    {"Resource${Flag}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }
        result = process_template(template)
        assert "Resourcetrue" in result["Resources"]
        assert "Resourcefalse" in result["Resources"]


class TestForEachProcessorNonDictSections:
    """Tests for ForEach processor handling of non-dict sections."""

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        return ForEachProcessor()

    def test_non_dict_resources_section_returned_as_is(self, processor: ForEachProcessor):
        """Test that non-dict Resources section is returned unchanged."""
        context = TemplateProcessingContext(fragment={"Resources": "not-a-dict"})
        processor.process_template(context)
        assert context.fragment["Resources"] == "not-a-dict"

    def test_non_dict_outputs_section_returned_as_is(self, processor: ForEachProcessor):
        """Test that non-dict Outputs section is returned unchanged."""
        context = TemplateProcessingContext(fragment={"Resources": {}, "Outputs": "not-a-dict"})
        processor.process_template(context)
        assert context.fragment["Outputs"] == "not-a-dict"

    def test_non_dict_conditions_section_returned_as_is(self, processor: ForEachProcessor):
        """Test that non-dict Conditions section is returned unchanged."""
        context = TemplateProcessingContext(fragment={"Resources": {}, "Conditions": "not-a-dict"})
        processor.process_template(context)
        assert context.fragment["Conditions"] == "not-a-dict"


class TestForEachProcessorNestingDepthValidation:
    """Tests for ForEach processor nesting depth validation.

    CloudFormation enforces a maximum nesting depth of 5 for Fn::ForEach loops.
    These tests verify that SAM CLI validates this limit before processing.

    Requirements:
        - 18.1: Count nesting depth starting from 1 for outermost loop
        - 18.2: Accept templates with 5 or fewer levels of nesting
        - 18.3: Reject templates with more than 5 levels of nesting
        - 18.4: Error message indicates maximum nesting depth of 5
        - 18.5: Error message indicates actual nesting depth found
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    @pytest.fixture
    def context(self) -> TemplateProcessingContext:
        """Create a minimal template processing context."""
        return TemplateProcessingContext(fragment={"Resources": {}})

    def test_calculate_depth_single_foreach(self, processor: ForEachProcessor):
        """Test depth calculation for single Fn::ForEach at top level.

        Requirement 18.1: Count nesting depth starting from 1 for outermost loop
        """
        template = {
            "Fn::ForEach::Topics": [
                "TopicName",
                ["Alerts", "Notifications"],
                {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
            ]
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 1

    def test_calculate_depth_nested_foreach_depth_2(self, processor: ForEachProcessor):
        """Test depth calculation for two levels of nested Fn::ForEach."""
        template = {
            "Fn::ForEach::Outer": [
                "Env",
                ["dev", "prod"],
                {
                    "Fn::ForEach::Inner": [
                        "Service",
                        ["api", "worker"],
                        {"${Env}${Service}Function": {"Type": "AWS::Serverless::Function"}},
                    ]
                },
            ]
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 2

    def test_calculate_depth_nested_foreach_depth_5(self, processor: ForEachProcessor):
        """Test depth calculation for maximum valid nesting (5 levels).

        Requirement 18.2: Accept templates with 5 or fewer levels of nesting
        """
        template = {
            "Fn::ForEach::L1": [
                "V1",
                ["a"],
                {
                    "Fn::ForEach::L2": [
                        "V2",
                        ["b"],
                        {
                            "Fn::ForEach::L3": [
                                "V3",
                                ["c"],
                                {
                                    "Fn::ForEach::L4": [
                                        "V4",
                                        ["d"],
                                        {
                                            "Fn::ForEach::L5": [
                                                "V5",
                                                ["e"],
                                                {"${V1}${V2}${V3}${V4}${V5}Resource": {"Type": "AWS::SNS::Topic"}},
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ]
                },
            ]
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 5

    def test_calculate_depth_nested_foreach_depth_6(self, processor: ForEachProcessor):
        """Test depth calculation for nesting that exceeds limit (6 levels)."""
        template = {
            "Fn::ForEach::L1": [
                "V1",
                ["a"],
                {
                    "Fn::ForEach::L2": [
                        "V2",
                        ["b"],
                        {
                            "Fn::ForEach::L3": [
                                "V3",
                                ["c"],
                                {
                                    "Fn::ForEach::L4": [
                                        "V4",
                                        ["d"],
                                        {
                                            "Fn::ForEach::L5": [
                                                "V5",
                                                ["e"],
                                                {
                                                    "Fn::ForEach::L6": [
                                                        "V6",
                                                        ["f"],
                                                        {
                                                            "${V1}${V2}${V3}${V4}${V5}${V6}Resource": {
                                                                "Type": "AWS::SNS::Topic"
                                                            }
                                                        },
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ]
                },
            ]
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 6

    def test_calculate_depth_parallel_foreach_returns_max(self, processor: ForEachProcessor):
        """Test that parallel ForEach blocks return the maximum depth of all branches."""
        template = {
            "Fn::ForEach::Shallow": [
                "Name",
                ["a"],
                {"${Name}Resource": {"Type": "AWS::SNS::Topic"}},
            ],
            "Fn::ForEach::Deep": [
                "V1",
                ["b"],
                {
                    "Fn::ForEach::Nested": [
                        "V2",
                        ["c"],
                        {"${V1}${V2}Resource": {"Type": "AWS::SQS::Queue"}},
                    ]
                },
            ],
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 2  # Maximum of 1 (Shallow) and 2 (Deep)

    def test_calculate_depth_empty_resources(self, processor: ForEachProcessor):
        """Test depth calculation for empty Resources section."""
        template: dict = {}
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 0

    def test_calculate_depth_no_foreach(self, processor: ForEachProcessor):
        """Test depth calculation for template with no ForEach blocks."""
        template = {
            "MyBucket": {"Type": "AWS::S3::Bucket"},
            "MyTopic": {"Type": "AWS::SNS::Topic"},
        }
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 0

    def test_validate_depth_accepts_valid_template(self, processor: ForEachProcessor):
        """Test that validation passes for templates with depth <= 5.

        Requirement 18.2: Accept templates with 5 or fewer levels of nesting
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
        # Should not raise
        processor._validate_foreach_nesting_depth(template)

    def test_validate_depth_accepts_depth_5(self, processor: ForEachProcessor):
        """Test that validation passes for templates with exactly 5 levels.

        Requirement 18.2: Accept templates with 5 or fewer levels of nesting
        """
        template = {
            "Resources": {
                "Fn::ForEach::L1": [
                    "V1",
                    ["a"],
                    {
                        "Fn::ForEach::L2": [
                            "V2",
                            ["b"],
                            {
                                "Fn::ForEach::L3": [
                                    "V3",
                                    ["c"],
                                    {
                                        "Fn::ForEach::L4": [
                                            "V4",
                                            ["d"],
                                            {
                                                "Fn::ForEach::L5": [
                                                    "V5",
                                                    ["e"],
                                                    {"${V1}${V2}${V3}${V4}${V5}Resource": {"Type": "AWS::SNS::Topic"}},
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }
        # Should not raise
        processor._validate_foreach_nesting_depth(template)

    def test_validate_depth_rejects_depth_6(self, processor: ForEachProcessor):
        """Test that validation fails for templates with depth > 5.

        Requirements:
            - 18.3: Reject templates with more than 5 levels of nesting
            - 18.4: Error message indicates maximum nesting depth of 5
            - 18.5: Error message indicates actual nesting depth found
        """
        template = {
            "Resources": {
                "Fn::ForEach::L1": [
                    "V1",
                    ["a"],
                    {
                        "Fn::ForEach::L2": [
                            "V2",
                            ["b"],
                            {
                                "Fn::ForEach::L3": [
                                    "V3",
                                    ["c"],
                                    {
                                        "Fn::ForEach::L4": [
                                            "V4",
                                            ["d"],
                                            {
                                                "Fn::ForEach::L5": [
                                                    "V5",
                                                    ["e"],
                                                    {
                                                        "Fn::ForEach::L6": [
                                                            "V6",
                                                            ["f"],
                                                            {
                                                                "${V1}${V2}${V3}${V4}${V5}${V6}Resource": {
                                                                    "Type": "AWS::SNS::Topic"
                                                                }
                                                            },
                                                        ]
                                                    },
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor._validate_foreach_nesting_depth(template)

        error_message = str(exc_info.value)
        # Requirement 18.4: Error message indicates maximum nesting depth of 5
        assert "5" in error_message
        # Requirement 18.5: Error message indicates actual nesting depth found
        assert "6" in error_message
        # Should mention the limit
        assert "maximum" in error_message.lower() or "exceeds" in error_message.lower()

    def test_validate_depth_checks_all_sections(self, processor: ForEachProcessor):
        """Test that validation checks Resources, Conditions, and Outputs sections."""
        # Deep nesting in Conditions section
        template = {
            "Resources": {},
            "Conditions": {
                "Fn::ForEach::L1": [
                    "V1",
                    ["a"],
                    {
                        "Fn::ForEach::L2": [
                            "V2",
                            ["b"],
                            {
                                "Fn::ForEach::L3": [
                                    "V3",
                                    ["c"],
                                    {
                                        "Fn::ForEach::L4": [
                                            "V4",
                                            ["d"],
                                            {
                                                "Fn::ForEach::L5": [
                                                    "V5",
                                                    ["e"],
                                                    {
                                                        "Fn::ForEach::L6": [
                                                            "V6",
                                                            ["f"],
                                                            {
                                                                "Is${V1}${V2}${V3}${V4}${V5}${V6}": {
                                                                    "Fn::Equals": ["a", "a"]
                                                                }
                                                            },
                                                        ]
                                                    },
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            },
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor._validate_foreach_nesting_depth(template)

        error_message = str(exc_info.value)
        assert "6" in error_message

    def test_process_template_validates_depth_before_processing(
        self, processor: ForEachProcessor, context: TemplateProcessingContext
    ):
        """Test that process_template validates nesting depth before processing.

        Requirement 18.7: Build command fails before attempting to build resources
        """
        context.fragment = {
            "Resources": {
                "Fn::ForEach::L1": [
                    "V1",
                    ["a"],
                    {
                        "Fn::ForEach::L2": [
                            "V2",
                            ["b"],
                            {
                                "Fn::ForEach::L3": [
                                    "V3",
                                    ["c"],
                                    {
                                        "Fn::ForEach::L4": [
                                            "V4",
                                            ["d"],
                                            {
                                                "Fn::ForEach::L5": [
                                                    "V5",
                                                    ["e"],
                                                    {
                                                        "Fn::ForEach::L6": [
                                                            "V6",
                                                            ["f"],
                                                            {
                                                                "${V1}${V2}${V3}${V4}${V5}${V6}Resource": {
                                                                    "Type": "AWS::SNS::Topic"
                                                                }
                                                            },
                                                        ]
                                                    },
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "6" in error_message
        assert "5" in error_message

    def test_calculate_depth_handles_malformed_foreach(self, processor: ForEachProcessor):
        """Test depth calculation handles malformed ForEach syntax gracefully."""
        # ForEach with less than 3 elements
        template = {
            "Fn::ForEach::Malformed": ["V1", ["a"]],  # Missing body
        }
        # Should still count this as depth 1 (the ForEach exists)
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 1

    def test_calculate_depth_handles_non_list_foreach_value(self, processor: ForEachProcessor):
        """Test depth calculation handles non-list ForEach value."""
        template = {
            "Fn::ForEach::Invalid": "not-a-list",
        }
        # Should still count this as depth 1 (the ForEach key exists)
        depth = processor._calculate_max_foreach_depth(template, current_depth=0)
        assert depth == 1


class TestAmpersandIdentifierSubstitution:
    """Tests for &{identifier} syntax that strips non-alphanumeric characters."""

    def test_ampersand_substitution_strips_non_alphanumeric_in_keys(self):
        """&{identifier} in dictionary keys strips dots, slashes, etc. from the value."""
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Subnets": [
                        "CIDR",
                        ["10.0.2.0/24", "10.0.3.0/24"],
                        {
                            "Subnet&{CIDR}": {
                                "Type": "AWS::EC2::Subnet",
                                "Properties": {"CidrBlock": {"Ref": "CIDR"}},
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert "Subnet1002024" in context.fragment["Resources"]
        assert "Subnet1003024" in context.fragment["Resources"]

    def test_ampersand_substitution_strips_non_alphanumeric_in_values(self):
        """&{identifier} in string values strips non-alphanumeric characters."""
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Items": [
                        "Name",
                        ["hello-world", "foo.bar"],
                        {
                            "Resource&{Name}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {"TopicName": "&{Name}"},
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert "Resourcehelloworld" in context.fragment["Resources"]
        assert "Resourcefoobar" in context.fragment["Resources"]
        assert context.fragment["Resources"]["Resourcehelloworld"]["Properties"]["TopicName"] == "helloworld"
        assert context.fragment["Resources"]["Resourcefoobar"]["Properties"]["TopicName"] == "foobar"

    def test_mixed_dollar_and_ampersand_substitution(self):
        """${identifier} and &{identifier} can coexist — dollar keeps value as-is, ampersand strips."""
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Subnets": [
                        "CIDR",
                        ["10.0.2.0/24"],
                        {
                            "Subnet&{CIDR}": {
                                "Type": "AWS::EC2::Subnet",
                                "Properties": {"CidrBlock": "${CIDR}"},
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert "Subnet1002024" in context.fragment["Resources"]
        assert context.fragment["Resources"]["Subnet1002024"]["Properties"]["CidrBlock"] == "10.0.2.0/24"

    def test_ampersand_with_alphanumeric_only_value(self):
        """&{identifier} with a purely alphanumeric value is identical to ${identifier}."""
        processor = ForEachProcessor()
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Loop": [
                        "Item",
                        ["Alpha"],
                        {
                            "Res&{Item}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {},
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert "ResAlpha" in context.fragment["Resources"]
