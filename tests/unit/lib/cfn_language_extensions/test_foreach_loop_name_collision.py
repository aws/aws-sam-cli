"""
Tests for Fn::ForEach loop name vs parameter name collision detection.

This module tests that the ForEachProcessor raises InvalidTemplateException
when a loop name (the suffix after Fn::ForEach::) exactly matches a template
parameter name. CloudFormation's AWS::LanguageExtensions transform rejects
such templates, so the local library must do the same.

Bug Condition: get_foreach_loop_name(key) IN _get_parameter_names(context)
Expected Behavior: InvalidTemplateException is raised with descriptive message

Requirements:
    - 1.1: Current behavior processes templates without error when loop name matches parameter
    - 1.2: Current behavior processes multiple loops without error when loop names match parameters
    - 1.3: Current behavior processes nested loops without error when loop name matches parameter
    - 2.1: Expected: raise InvalidTemplateException when loop name matches parameter name
    - 2.2: Expected: raise InvalidTemplateException on first conflicting loop
    - 2.3: Expected: raise InvalidTemplateException for nested loop name collision
"""

import pytest

from samcli.lib.cfn_language_extensions.models import (
    ParsedTemplate,
    TemplateProcessingContext,
)
from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException


class TestForEachLoopNameParameterCollision:
    """Bug condition exploration tests: loop name collides with parameter name.

    **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**

    These tests encode the EXPECTED behavior (InvalidTemplateException raised).
    On UNFIXED code, they will FAIL — confirming the bug exists.
    After the fix, they will PASS — confirming the bug is resolved.
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_loop_name_collides_with_parameter_name(self, processor: ForEachProcessor):
        """Loop name 'MyParam' matches parameter 'MyParam' — should raise.

        **Validates: Requirements 2.1**

        Bug condition: Fn::ForEach::MyParam where MyParam is in Parameters.
        Expected: InvalidTemplateException with message about loop name conflict.
        On unfixed code: template processes successfully (bug).
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"MyParam": {"Type": "String", "Default": "val1"}},
                "Resources": {
                    "Fn::ForEach::MyParam": [
                        "Item",
                        ["A", "B"],
                        {"Resource${Item}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_msg = str(exc_info.value)
        assert "loop name" in error_msg.lower() or "loop name" in error_msg
        assert "conflicts with parameter" in error_msg.lower() or "conflicts with parameter" in error_msg

    def test_loop_name_collides_with_parameter_from_parsed_template(self, processor: ForEachProcessor):
        """Loop name matches parameter from parsed_template — should raise.

        **Validates: Requirements 2.1**

        Bug condition: Fn::ForEach::Env where Env is in parsed_template.parameters.
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Env": [
                        "Item",
                        ["Dev", "Prod"],
                        {"${Item}Bucket": {"Type": "AWS::S3::Bucket"}},
                    ]
                }
            }
        )
        context.parsed_template = ParsedTemplate(
            parameters={"Env": {"Type": "String", "Default": "Dev"}},
            resources={},
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_msg = str(exc_info.value)
        assert "loop name" in error_msg.lower() or "loop name" in error_msg
        assert "conflicts with parameter" in error_msg.lower() or "conflicts with parameter" in error_msg

    def test_nested_loop_name_collides_with_parameter(self, processor: ForEachProcessor):
        """Inner loop name 'InnerParam' matches parameter — should raise.

        **Validates: Requirements 2.3**

        Bug condition: nested Fn::ForEach::InnerParam where InnerParam is a parameter.
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"InnerParam": {"Type": "String", "Default": "x"}},
                "Resources": {
                    "Fn::ForEach::Outer": [
                        "OuterItem",
                        ["A", "B"],
                        {
                            "Fn::ForEach::InnerParam": [
                                "InnerItem",
                                ["X", "Y"],
                                {"${OuterItem}${InnerItem}Res": {"Type": "AWS::SNS::Topic"}},
                            ]
                        },
                    ]
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_msg = str(exc_info.value)
        assert "loop name" in error_msg.lower() or "loop name" in error_msg
        assert "conflicts with parameter" in error_msg.lower() or "conflicts with parameter" in error_msg

    def test_multiple_loops_first_collides_with_parameter(self, processor: ForEachProcessor):
        """First of two loops has colliding name — should raise.

        **Validates: Requirements 2.2**

        Bug condition: Fn::ForEach::ParamA where ParamA is a parameter,
        alongside a non-colliding Fn::ForEach::SafeLoop.
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"ParamA": {"Type": "String", "Default": "v"}},
                "Resources": {
                    "Fn::ForEach::ParamA": [
                        "Item1",
                        ["A", "B"],
                        {"Res1${Item1}": {"Type": "AWS::SNS::Topic"}},
                    ],
                    "Fn::ForEach::SafeLoop": [
                        "Item2",
                        ["C", "D"],
                        {"Res2${Item2}": {"Type": "AWS::S3::Bucket"}},
                    ],
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_msg = str(exc_info.value)
        assert "loop name" in error_msg.lower() or "loop name" in error_msg
        assert "conflicts with parameter" in error_msg.lower() or "conflicts with parameter" in error_msg


class TestForEachLoopNamePreservation:
    """Preservation tests: non-conflicting templates must remain unaffected by the fix.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

    These tests capture baseline behavior on UNFIXED code. They must PASS both
    before and after the fix, confirming no regressions are introduced.
    """

    @pytest.fixture
    def processor(self) -> ForEachProcessor:
        """Create a ForEachProcessor for testing."""
        return ForEachProcessor()

    def test_non_colliding_loop_name_with_parameters_processes_successfully(self, processor: ForEachProcessor):
        """Loop name 'Topics' with parameter 'Env' — no collision, should process.

        **Validates: Requirements 3.1**

        Preservation: non-matching loop name and parameter name must expand correctly.
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Env": {"Type": "String", "Default": "dev"}},
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        processor.process_template(context)

        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]
        assert context.fragment["Resources"]["TopicAlerts"] == {"Type": "AWS::SNS::Topic"}
        assert context.fragment["Resources"]["TopicNotifications"] == {"Type": "AWS::SNS::Topic"}

    def test_no_parameters_section_processes_successfully(self, processor: ForEachProcessor):
        """Loop name 'Topics' with no Parameters section — should process.

        **Validates: Requirements 3.3**

        Preservation: templates without a Parameters section must work without error.
        """
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    "Fn::ForEach::Topics": [
                        "TopicName",
                        ["Alerts", "Notifications"],
                        {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        processor.process_template(context)

        assert "TopicAlerts" in context.fragment["Resources"]
        assert "TopicNotifications" in context.fragment["Resources"]

    def test_partial_match_does_not_trigger_collision(self, processor: ForEachProcessor):
        """Loop name 'Topic' with parameter 'Topics' — partial match, should process.

        **Validates: Requirements 3.4**

        Preservation: partial name matches (substring, not exact) must NOT be treated
        as conflicts. Only exact matches constitute a collision.
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"Topics": {"Type": "String", "Default": "val"}},
                "Resources": {
                    "Fn::ForEach::Topic": [
                        "Item",
                        ["A", "B"],
                        {"Resource${Item}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        processor.process_template(context)

        assert "ResourceA" in context.fragment["Resources"]
        assert "ResourceB" in context.fragment["Resources"]

    def test_identifier_conflict_with_parameter_still_raises(self, processor: ForEachProcessor):
        """Loop identifier 'MyParam' matches parameter 'MyParam' — existing check should raise.

        **Validates: Requirements 3.2**

        Preservation: the existing _check_identifier_conflicts validation must continue
        to detect loop identifier vs parameter name conflicts, independent of any
        loop name validation.
        """
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {"MyParam": {"Type": "String", "Default": "val"}},
                "Resources": {
                    "Fn::ForEach::SafeLoop": [
                        "MyParam",  # identifier conflicts with parameter name
                        ["A", "B"],
                        {"Resource${MyParam}": {"Type": "AWS::SNS::Topic"}},
                    ]
                },
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        assert "identifier 'MyParam' conflicts with parameter name" in str(exc_info.value)
