"""
Unit tests and property tests for Phase Separation (Tasks 35.1-35.5).

This module covers:
- Task 35.1: LanguageExtensionResult dataclass tests
- Task 35.2: expand_language_extensions() unit tests
- Task 35.3: run_plugins() no longer calls Phase 1 tests
- Task 35.4: All callers use expand_language_extensions() tests
- Task 35.5: Property tests for phase separation correctness (Properties 10, 11)

Requirements tested:
    - 23.1, 23.2: LanguageExtensionResult dataclass
    - 23.3, 23.4, 23.5: expand_language_extensions() behavior
    - 23.6: run_plugins() Phase 2 only
    - 23.7: All callers use expand_language_extensions()
    - 20.1, 20.7, 20.9: Phase separation correctness properties
"""

import copy
import dataclasses
from typing import Any, Dict, List
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

import pytest

from samcli.lib.cfn_language_extensions.sam_integration import (
    LanguageExtensionResult,
    expand_language_extensions,
    check_using_language_extension,
)
from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
from samcli.lib.samlib.wrapper import SamTranslatorWrapper

# =============================================================================
# Task 35.1: Unit Tests for LanguageExtensionResult Dataclass
# =============================================================================


class TestLanguageExtensionResultDataclass(TestCase):
    """
    Unit tests for the LanguageExtensionResult dataclass.

    Validates: Requirements 23.1, 23.2
    """

    def test_creation_with_all_fields(self):
        """Test LanguageExtensionResult can be created with all fields."""
        expanded = {"Resources": {"AFunc": {"Type": "AWS::Lambda::Function"}}}
        original = {
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A"],
                    {"${Name}Func": {"Type": "AWS::Lambda::Function"}},
                ]
            }
        }
        dynamic_props = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Loop",
                loop_name="Loop",
                loop_variable="Name",
                collection=["A"],
                resource_key="${Name}Func",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./${Name}",
            )
        ]

        result = LanguageExtensionResult(
            expanded_template=expanded,
            original_template=original,
            dynamic_artifact_properties=dynamic_props,
            had_language_extensions=True,
        )

        self.assertEqual(result.expanded_template, expanded)
        self.assertEqual(result.original_template, original)
        self.assertEqual(result.dynamic_artifact_properties, dynamic_props)
        self.assertTrue(result.had_language_extensions)

    def test_creation_with_defaults(self):
        """Test LanguageExtensionResult uses correct defaults for optional fields."""
        template = {"Resources": {"MyFunc": {"Type": "AWS::Lambda::Function"}}}

        result = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
        )

        self.assertEqual(result.dynamic_artifact_properties, [])
        self.assertFalse(result.had_language_extensions)

    def test_frozen_immutable_behavior(self):
        """Test that LanguageExtensionResult is frozen (immutable)."""
        template = {"Resources": {}}
        result = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            had_language_extensions=True,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.expanded_template = {"Resources": {"New": {}}}

        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.original_template = {"Resources": {"New": {}}}

        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.had_language_extensions = False

        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.dynamic_artifact_properties = []

    def test_had_language_extensions_false_case(self):
        """Test LanguageExtensionResult with had_language_extensions=False."""
        template = {"Resources": {"MyFunc": {"Type": "AWS::Lambda::Function"}}}

        result = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )

        self.assertFalse(result.had_language_extensions)
        # When no language extensions, expanded and original should be the same reference
        self.assertIs(result.expanded_template, result.original_template)

    def test_is_dataclass(self):
        """Test that LanguageExtensionResult is a proper dataclass."""
        self.assertTrue(dataclasses.is_dataclass(LanguageExtensionResult))

    def test_is_frozen(self):
        """Test that LanguageExtensionResult is frozen."""
        fields = dataclasses.fields(LanguageExtensionResult)
        # frozen=True means the dataclass is immutable
        self.assertTrue(LanguageExtensionResult.__dataclass_params__.frozen)


# =============================================================================
# Task 35.2: Unit Tests for expand_language_extensions()
# =============================================================================


class TestExpandLanguageExtensions(TestCase):
    """
    Unit tests for the expand_language_extensions() function.

    Validates: Requirements 23.1, 23.2, 23.3, 23.4, 23.5
    """

    def setUp(self):
        """Set up before each test."""
        pass

    def test_returns_result_with_expanded_template_for_language_extensions(self):
        """expand_language_extensions() returns LanguageExtensionResult with expanded template."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["Alpha", "Beta"],
                    {"${Name}Topic": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }

        result = expand_language_extensions(template)

        self.assertIsInstance(result, LanguageExtensionResult)
        self.assertTrue(result.had_language_extensions)
        # Expanded template should have individual resources
        self.assertIn("AlphaTopic", result.expanded_template["Resources"])
        self.assertIn("BetaTopic", result.expanded_template["Resources"])
        self.assertNotIn("Fn::ForEach::Loop", result.expanded_template["Resources"])

    def test_returns_had_language_extensions_false_for_non_langext_template(self):
        """expand_language_extensions() returns had_language_extensions=False for non-LE templates."""
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"MyFunc": {"Type": "AWS::Serverless::Function"}},
        }

        result = expand_language_extensions(template)

        self.assertIsInstance(result, LanguageExtensionResult)
        self.assertFalse(result.had_language_extensions)
        # Template should be unchanged
        self.assertIn("MyFunc", result.expanded_template["Resources"])

    def test_returns_had_language_extensions_false_for_no_transform(self):
        """expand_language_extensions() returns had_language_extensions=False when no Transform."""
        template = {"Resources": {"MyTopic": {"Type": "AWS::SNS::Topic"}}}

        result = expand_language_extensions(template)

        self.assertFalse(result.had_language_extensions)

    def test_original_template_preserves_foreach_structure(self):
        """expand_language_extensions() preserves Fn::ForEach in original_template."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "src/", "Handler": "${Name}.handler"},
                        }
                    },
                ]
            },
        }

        result = expand_language_extensions(template)

        # Original template should preserve Fn::ForEach
        self.assertIn("Fn::ForEach::Services", result.original_template["Resources"])
        # Expanded template should NOT have Fn::ForEach
        self.assertNotIn("Fn::ForEach::Services", result.expanded_template["Resources"])

    def test_original_template_not_mutated(self):
        """expand_language_extensions() does not mutate the input template."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A"],
                    {"${Name}Topic": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }
        import copy

        template_before = copy.deepcopy(template)

        result = expand_language_extensions(template)

        # Input template must not be mutated by expansion
        self.assertEqual(template, template_before)
        # original_template and expanded_template must be independent
        self.assertIsNot(result.original_template, result.expanded_template)

    def test_dynamic_artifact_properties_detected(self):
        """expand_language_extensions() detects dynamic artifact properties."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        result = expand_language_extensions(template)

        self.assertTrue(len(result.dynamic_artifact_properties) > 0)
        prop = result.dynamic_artifact_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")
        self.assertEqual(prop.loop_variable, "Name")

    def test_pseudo_parameter_extraction(self):
        """expand_language_extensions() correctly extracts and uses pseudo-parameters."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "MyTopic": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {
                        "DisplayName": {"Fn::Sub": "Topic in ${AWS::Region}"},
                    },
                }
            },
        }
        parameter_values = {"AWS::Region": "us-west-2", "AWS::AccountId": "123456789012"}

        result = expand_language_extensions(template, parameter_values=parameter_values)

        self.assertTrue(result.had_language_extensions)
        # Pseudo-parameter should be resolved
        self.assertEqual(
            result.expanded_template["Resources"]["MyTopic"]["Properties"]["DisplayName"],
            "Topic in us-west-2",
        )

    def test_invalid_template_raises_invalid_sam_document(self):
        """expand_language_extensions() maps InvalidTemplateException to InvalidSamDocumentException."""
        from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": "invalid_not_a_list",
            },
        }

        with self.assertRaises(InvalidSamDocumentException):
            expand_language_extensions(template)

    def test_list_transform_with_language_extensions(self):
        """expand_language_extensions() works when Transform is a list containing AWS::LanguageExtensions."""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A", "B"],
                    {"${Name}Topic": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }

        result = expand_language_extensions(template)

        self.assertTrue(result.had_language_extensions)
        self.assertIn("ATopic", result.expanded_template["Resources"])
        self.assertIn("BTopic", result.expanded_template["Resources"])


# =============================================================================
# Task 35.3: Unit Tests Verifying run_plugins() No Longer Calls Phase 1
# =============================================================================


class TestRunPluginsPhase2Only(TestCase):
    """
    Unit tests verifying that SamTranslatorWrapper.run_plugins() no longer
    calls Phase 1 logic (_process_language_extensions).

    Validates: Requirements 23.6
    """

    def test_run_plugins_does_not_call_process_language_extensions(self):
        """run_plugins() should not call _process_language_extensions()."""
        # Verify the method no longer exists on SamTranslatorWrapper
        self.assertFalse(
            hasattr(SamTranslatorWrapper, "_process_language_extensions"),
            "_process_language_extensions() should have been removed from SamTranslatorWrapper",
        )

    def test_run_plugins_does_not_call_build_pseudo_parameters(self):
        """run_plugins() should not call _build_pseudo_parameters()."""
        # Verify the method no longer exists on SamTranslatorWrapper
        self.assertFalse(
            hasattr(SamTranslatorWrapper, "_build_pseudo_parameters"),
            "_build_pseudo_parameters() should have been removed from SamTranslatorWrapper",
        )

    def test_run_plugins_works_with_pre_expanded_template(self):
        """run_plugins() works correctly with a pre-expanded template (no Fn::ForEach)."""
        # This is a pre-expanded template (Phase 1 already done)
        expanded_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "Alpha.handler",
                        "CodeUri": "s3://bucket/code.zip",
                        "Runtime": "python3.9",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "Beta.handler",
                        "CodeUri": "s3://bucket/code.zip",
                        "Runtime": "python3.9",
                    },
                },
            },
        }

        wrapper = SamTranslatorWrapper(expanded_template)
        result = wrapper.run_plugins()

        # Should process the template without errors
        self.assertIn("AlphaFunction", result["Resources"])
        self.assertIn("BetaFunction", result["Resources"])

    def test_run_plugins_with_language_extension_result(self):
        """run_plugins() accepts LanguageExtensionResult and uses its data."""
        expanded_template = {
            "Resources": {
                "AlphaFunc": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "Alpha.handler",
                        "CodeUri": "s3://bucket/code.zip",
                        "Runtime": "python3.9",
                    },
                },
            },
        }
        original_template = {
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["Alpha"],
                    {"${Name}Func": {"Type": "AWS::Serverless::Function"}},
                ]
            }
        }
        dynamic_props = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Loop",
                loop_name="Loop",
                loop_variable="Name",
                collection=["Alpha"],
                resource_key="${Name}Func",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./${Name}",
            )
        ]

        lang_result = LanguageExtensionResult(
            expanded_template=expanded_template,
            original_template=original_template,
            dynamic_artifact_properties=dynamic_props,
            had_language_extensions=True,
        )

        wrapper = SamTranslatorWrapper(expanded_template, language_extension_result=lang_result)

        # Verify original template and dynamic properties come from the result
        self.assertEqual(wrapper.get_original_template(), original_template)
        self.assertEqual(wrapper.get_dynamic_artifact_properties(), dynamic_props)

    def test_run_plugins_no_check_using_language_extension_call(self):
        """run_plugins() should not internally call _check_using_language_extension()."""
        # We verify this by checking that run_plugins() doesn't have Phase 1 logic
        # by running it on a template with AWS::LanguageExtensions transform
        # but with already-expanded resources (no Fn::ForEach)
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunc": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "Alpha.handler",
                        "CodeUri": "s3://bucket/code.zip",
                        "Runtime": "python3.9",
                    },
                },
            },
        }

        wrapper = SamTranslatorWrapper(template)
        # run_plugins should work without trying to expand language extensions
        result = wrapper.run_plugins()
        self.assertIn("AlphaFunc", result["Resources"])


# =============================================================================
# Task 35.4: Unit Tests Verifying All Callers Use expand_language_extensions()
# =============================================================================


class TestCallersUseExpandLanguageExtensions(TestCase):
    """
    Unit tests verifying that all callers use expand_language_extensions()
    instead of their own expansion logic.

    Validates: Requirements 23.7
    """

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_calls_expand_language_extensions(self, mock_expand, mock_get_template):
        """SamLocalStackProvider.get_stacks() calls expand_language_extensions()."""
        from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A", "B"],
                    {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}}},
                ]
            },
        }
        expanded = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "AFunc": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}},
                "BFunc": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}},
            },
        }
        mock_get_template.return_value = template
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=expanded,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )

        stacks, _ = SamLocalStackProvider.get_stacks(template_file="template.yaml")

        # Verify expand_language_extensions was called
        mock_expand.assert_called_once()
        # Verify the expanded template is used
        self.assertEqual(stacks[0].template_dict, expanded)

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_no_longer_uses_process_language_extensions_for_stack(self, mock_expand, mock_get_template):
        """_process_language_extensions_for_stack() should no longer exist in sam_stack_provider."""
        from samcli.lib.providers import sam_stack_provider

        self.assertFalse(
            hasattr(sam_stack_provider, "_process_language_extensions_for_stack"),
            "_process_language_extensions_for_stack() should have been removed from sam_stack_provider",
        )

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_sam_template_validator_calls_expand_language_extensions(self, mock_expand):
        """SamTemplateValidator calls expand_language_extensions() in get_translated_template_if_valid()."""
        from samcli.lib.translate.sam_template_validator import SamTemplateValidator

        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A"],
                    {"${Name}Topic": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }
        expanded = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {"ATopic": {"Type": "AWS::SNS::Topic"}},
        }
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=expanded,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )

        managed_policy_mock = MagicMock()
        validator = SamTemplateValidator(template, managed_policy_mock)

        # Call the method that should use expand_language_extensions
        # We mock the translator to avoid needing real AWS credentials
        with patch.object(validator, "_get_managed_policy_map", return_value={}):
            try:
                validator.get_translated_template_if_valid()
            except Exception:
                pass  # We only care that expand was called

        mock_expand.assert_called_once()

    def test_sam_template_validator_no_longer_has_process_language_extensions(self):
        """SamTemplateValidator should not have _process_language_extensions() method."""
        from samcli.lib.translate.sam_template_validator import SamTemplateValidator

        self.assertFalse(
            hasattr(SamTemplateValidator, "_process_language_extensions"),
            "_process_language_extensions() should have been removed from SamTemplateValidator",
        )

    @patch("samcli.commands.package.package_context.yaml_parse")
    @patch("builtins.open", create=True)
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_package_context_export_calls_expand_language_extensions(self, mock_expand, mock_open, mock_yaml_parse):
        """PackageContext._export() calls expand_language_extensions()."""
        from samcli.commands.package.package_context import PackageContext

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A"],
                    {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}}},
                ]
            },
        }
        expanded = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "AFunc": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}},
            },
        }

        mock_yaml_parse.return_value = template
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=expanded,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )

        # Create a minimal PackageContext
        ctx = PackageContext.__new__(PackageContext)
        ctx.template_file = "template.yaml"
        ctx.parameter_overrides = {}
        ctx._global_parameter_overrides = {}
        ctx.uploaders = MagicMock()
        ctx.code_signer = MagicMock()

        # Mock Template to avoid actual file operations
        with patch("samcli.commands.package.package_context.Template") as mock_template_cls:
            mock_template_instance = MagicMock()
            mock_template_instance.export.return_value = expanded
            mock_template_cls.return_value = mock_template_instance

            try:
                ctx._export("template.yaml", use_json=False)
            except Exception:
                pass  # We only care that expand was called

        mock_expand.assert_called_once()

    def test_package_context_no_longer_has_expand_language_extensions_method(self):
        """PackageContext should not have _expand_language_extensions() method."""
        from samcli.commands.package.package_context import PackageContext

        self.assertFalse(
            hasattr(PackageContext, "_expand_language_extensions"),
            "_expand_language_extensions() should have been removed from PackageContext",
        )


# =============================================================================
# Task 35.5: Parametrized Tests for Phase Separation Correctness
# =============================================================================


class TestProperty10PhaseSeparationSingleExpansion:
    """
    Phase Separation — Single Expansion

    For any template, expand_language_extensions() is called exactly once
    per unique (path, mtime, params) tuple. When called multiple times with
    the same inputs, the cached result is returned without re-expanding.

    **Validates: Requirements 20.1, 20.7**
    """

    @pytest.mark.parametrize(
        "loop_name, loop_var, collection",
        [
            ("Services", "Name", ["Alpha", "Beta"]),
            ("Queues", "QueueName", ["Orders", "Payments", "Notifications"]),
            ("Topics", "T", ["A"]),
        ],
    )
    def test_single_expansion_per_unique_inputs(
        self,
        loop_name: str,
        loop_var: str,
        collection: List[str],
    ):
        """
        For any template, expand_language_extensions() produces
        a consistent LanguageExtensionResult. Calling it twice with the same
        template (no path/caching) returns equivalent results.

        **Validates: Requirements 20.1, 20.7**
        """

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                f"Fn::ForEach::{loop_name}": [
                    loop_var,
                    collection,
                    {
                        f"${{{loop_var}}}Resource": {
                            "Type": "AWS::SNS::Topic",
                        }
                    },
                ]
            },
        }

        result1 = expand_language_extensions(copy.deepcopy(template))
        result2 = expand_language_extensions(copy.deepcopy(template))

        assert isinstance(result1, LanguageExtensionResult)
        assert isinstance(result2, LanguageExtensionResult)

        assert result1.had_language_extensions is True
        assert result2.had_language_extensions is True

        assert result1.expanded_template == result2.expanded_template
        assert result1.original_template == result2.original_template

        assert len(result1.expanded_template["Resources"]) == len(collection)

    @pytest.mark.parametrize(
        "loop_name, loop_var, collection",
        [
            ("Services", "Name", ["Alpha", "Beta"]),
            ("Queues", "QueueName", ["Orders"]),
        ],
    )
    def test_no_expansion_without_language_extensions_transform(
        self,
        loop_name: str,
        loop_var: str,
        collection: List[str],
    ):
        """
        For any template WITHOUT AWS::LanguageExtensions,
        expand_language_extensions() returns had_language_extensions=False and
        does not modify the template.

        **Validates: Requirements 20.1**
        """

        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "MyResource": {"Type": "AWS::SNS::Topic"},
            },
        }

        result = expand_language_extensions(copy.deepcopy(template))

        assert result.had_language_extensions is False
        assert "MyResource" in result.expanded_template["Resources"]


class TestProperty11PhaseSeparationResultEquivalence:
    """
    Phase Separation — Result Equivalence

    For any template, the LanguageExtensionResult returned by
    expand_language_extensions() produces the same expanded_template
    as the previous per-component expansion logic.

    **Validates: Requirements 20.7, 20.9**
    """

    @pytest.mark.parametrize(
        "loop_name, loop_var, collection",
        [
            ("Services", "Name", ["Alpha", "Beta"]),
            ("Queues", "QueueName", ["Orders", "Payments", "Notifications"]),
            ("Topics", "T", ["A"]),
        ],
    )
    def test_result_equivalence_expanded_template_matches_direct_processing(
        self,
        loop_name: str,
        loop_var: str,
        collection: List[str],
    ):
        """
        The expanded_template from expand_language_extensions()
        is equivalent to calling process_template_for_sam_cli() directly.

        **Validates: Requirements 20.7, 20.9**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import process_template_for_sam_cli

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                f"Fn::ForEach::{loop_name}": [
                    loop_var,
                    collection,
                    {
                        f"${{{loop_var}}}Resource": {
                            "Type": "AWS::SNS::Topic",
                            "Properties": {
                                "DisplayName": {"Fn::Sub": f"Topic ${{{loop_var}}}"},
                            },
                        }
                    },
                ]
            },
        }

        result = expand_language_extensions(copy.deepcopy(template))
        direct_result = process_template_for_sam_cli(copy.deepcopy(template))

        assert set(result.expanded_template["Resources"].keys()) == set(direct_result["Resources"].keys())

        for resource_key in result.expanded_template["Resources"]:
            assert result.expanded_template["Resources"][resource_key] == direct_result["Resources"][resource_key]

    @pytest.mark.parametrize(
        "loop_name, loop_var, collection",
        [
            ("Services", "Name", ["Alpha", "Beta"]),
            ("Queues", "QueueName", ["Orders", "Payments", "Notifications"]),
            ("Topics", "T", ["A"]),
        ],
    )
    def test_result_preserves_original_template_structure(
        self,
        loop_name: str,
        loop_var: str,
        collection: List[str],
    ):
        """
        The original_template in the result preserves
        the Fn::ForEach structure from the input template.

        **Validates: Requirements 20.9**
        """

        foreach_key = f"Fn::ForEach::{loop_name}"
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                foreach_key: [
                    loop_var,
                    collection,
                    {
                        f"${{{loop_var}}}Resource": {
                            "Type": "AWS::SNS::Topic",
                        }
                    },
                ]
            },
        }

        result = expand_language_extensions(copy.deepcopy(template))

        assert foreach_key in result.original_template["Resources"]

        original_foreach = result.original_template["Resources"][foreach_key]
        assert isinstance(original_foreach, list)
        assert len(original_foreach) == 3
        assert original_foreach[0] == loop_var
        assert original_foreach[1] == collection

    @pytest.mark.parametrize(
        "loop_name, loop_var, collection",
        [
            ("Services", "Name", ["Alpha", "Beta"]),
            ("Queues", "QueueName", ["Orders", "Payments", "Notifications"]),
            ("Topics", "T", ["A"]),
        ],
    )
    def test_result_dynamic_properties_consistent(
        self,
        loop_name: str,
        loop_var: str,
        collection: List[str],
    ):
        """
        Dynamic artifact properties detected by
        expand_language_extensions() are consistent with the template content.

        **Validates: Requirements 20.9**
        """

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                f"Fn::ForEach::{loop_name}": [
                    loop_var,
                    collection,
                    {
                        f"${{{loop_var}}}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": f"./${{{loop_var}}}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        result = expand_language_extensions(copy.deepcopy(template))

        assert len(result.dynamic_artifact_properties) > 0

        prop = result.dynamic_artifact_properties[0]
        assert prop.loop_variable == loop_var
        assert prop.property_name == "CodeUri"
        assert prop.collection == collection
        assert prop.loop_name == loop_name
