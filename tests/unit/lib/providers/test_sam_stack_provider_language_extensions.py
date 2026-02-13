"""
Tests for language extensions integration in SamLocalStackProvider.get_stacks().

Verifies that get_stacks() calls expand_language_extensions() directly
and uses LanguageExtensionResult to populate Stack objects.
"""

from unittest import TestCase
from unittest.mock import patch, MagicMock

from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult


class TestGetStacksLanguageExtensions(TestCase):
    """Tests that get_stacks() calls expand_language_extensions() directly."""

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_calls_expand_language_extensions(self, mock_expand, mock_get_template):
        """get_stacks() should call expand_language_extensions() directly."""
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

        mock_expand.assert_called_once()
        # Verify the expanded template is used for the stack
        self.assertEqual(stacks[0].template_dict, expanded)

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_stores_original_template_on_stack(self, mock_expand, mock_get_template):
        """get_stacks() should store original_template on Stack when language extensions are present."""
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

        # original_template_dict should be set when language extensions were present
        self.assertEqual(stacks[0].original_template_dict, template)

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_no_original_template_without_language_extensions(self, mock_expand, mock_get_template):
        """get_stacks() should not store original_template when no language extensions."""
        from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"MyFunc": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "src/"}}},
        }
        mock_get_template.return_value = template
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )

        stacks, _ = SamLocalStackProvider.get_stacks(template_file="template.yaml")

        # original_template_dict should be None when no language extensions
        self.assertIsNone(stacks[0].original_template_dict)

    @patch("samcli.lib.providers.sam_stack_provider.get_template_data")
    @patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions")
    def test_get_stacks_passes_merged_params_with_pseudo_params(self, mock_expand, mock_get_template):
        """get_stacks() should pass merged parameter overrides including pseudo-params."""
        from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    {"Ref": "Names"},
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

        SamLocalStackProvider.get_stacks(
            template_file="template.yaml",
            parameter_overrides={"Names": "A,B"},
        )

        call_kwargs = mock_expand.call_args
        param_values = call_kwargs[1]["parameter_values"]
        # Should include user overrides
        self.assertIn("Names", param_values)
        self.assertEqual(param_values["Names"], "A,B")
        # Should include pseudo-parameters
        self.assertIn("AWS::Region", param_values)
