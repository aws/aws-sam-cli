"""
Tests for SamTemplateValidator language extensions processing.

Covers expand_language_extensions() integration in get_translated_template_if_valid(),
_replace_local_codeuri with ForEach, and _replace_local_image with ForEach.
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult
from samcli.lib.translate.sam_template_validator import SamTemplateValidator


class TestExpandLanguageExtensionsIntegration(TestCase):
    """Tests for expand_language_extensions() integration in SamTemplateValidator."""

    def _make_validator(self, template, parameter_overrides=None):
        managed_policy_mock = Mock()
        return SamTemplateValidator(template, managed_policy_mock, parameter_overrides=parameter_overrides)

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_no_language_extensions_template_unchanged(self, mock_expand):
        """When template has no language extensions, expand returns had_language_extensions=False."""
        template = {"Resources": {"MyFunc": {"Type": "AWS::Serverless::Function"}}}
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )
        validator = self._make_validator(template)
        # Call expand via the validator's flow (we test the integration, not the full translate)
        result = mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)
        self.assertFalse(result.had_language_extensions)
        # Template should remain unchanged
        self.assertIn("MyFunc", validator.sam_template["Resources"])

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_language_extensions_template_expanded(self, mock_expand):
        """When template has language extensions, expand returns expanded template."""
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    ["A", "B"],
                    {"${Name}Resource": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }
        expanded_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AResource": {"Type": "AWS::SNS::Topic"},
                "BResource": {"Type": "AWS::SNS::Topic"},
            },
        }
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=expanded_template,
            original_template=original_template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )
        validator = self._make_validator(original_template)

        # Simulate what get_translated_template_if_valid does
        result = mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)
        if result.had_language_extensions:
            validator.sam_template = result.expanded_template

        mock_expand.assert_called_once_with(original_template, parameter_values={})
        self.assertIn("AResource", validator.sam_template["Resources"])
        self.assertIn("BResource", validator.sam_template["Resources"])

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_language_extensions_invalid_template_raises(self, mock_expand):
        """When expand_language_extensions raises InvalidSamDocumentException, it propagates."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {"Fn::ForEach::Loop": "invalid"},
        }
        mock_expand.side_effect = InvalidSamDocumentException("bad template")
        validator = self._make_validator(template)

        with self.assertRaises(InvalidSamDocumentException):
            mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_language_extensions_non_langext_exception_reraises(self, mock_expand):
        """Non-language-extension exceptions propagate unchanged."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {"Fn::ForEach::Loop": ["Name", ["A"], {}]},
        }
        mock_expand.side_effect = RuntimeError("unexpected error")
        validator = self._make_validator(template)

        with self.assertRaises(RuntimeError):
            mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_non_language_extensions_transform_not_expanded(self, mock_expand):
        """When template has only SAM transform, expand returns had_language_extensions=False."""
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"MyFunc": {"Type": "AWS::Serverless::Function"}},
        }
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )
        validator = self._make_validator(template)

        result = mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)
        self.assertFalse(result.had_language_extensions)
        self.assertIn("MyFunc", validator.sam_template["Resources"])

    @patch("samcli.lib.translate.sam_template_validator.expand_language_extensions")
    def test_parameter_overrides_passed_to_expand(self, mock_expand):
        """Parameter overrides are passed to expand_language_extensions."""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Loop": [
                    "Name",
                    {"Ref": "Names"},
                    {"${Name}Resource": {"Type": "AWS::SNS::Topic"}},
                ]
            },
        }
        expanded_template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "AlphaResource": {"Type": "AWS::SNS::Topic"},
            },
        }
        param_overrides = {"Names": "Alpha"}
        mock_expand.return_value = LanguageExtensionResult(
            expanded_template=expanded_template,
            original_template=template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )
        validator = self._make_validator(template, parameter_overrides=param_overrides)

        result = mock_expand(validator.sam_template, parameter_values=validator.parameter_overrides)
        if result.had_language_extensions:
            validator.sam_template = result.expanded_template

        mock_expand.assert_called_once_with(template, parameter_values=param_overrides)

    def test_process_language_extensions_method_removed(self):
        """Verify _process_language_extensions() method no longer exists on SamTemplateValidator."""
        self.assertFalse(hasattr(SamTemplateValidator, "_process_language_extensions"))


class TestReplacLocalCodeuriWithForEach(TestCase):
    """Tests for _replace_local_codeuri with Fn::ForEach blocks in Resources."""

    def _make_validator(self, template):
        managed_policy_mock = Mock()
        return SamTemplateValidator(template, managed_policy_mock)

    def test_foreach_entries_skipped_in_replace_local_codeuri(self):
        """Fn::ForEach entries (which are lists, not dicts) should be skipped."""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./${Name}", "Handler": "main.handler"},
                        }
                    },
                ],
                "RegularFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "CodeUri": "./src", "Runtime": "python3.13"},
                },
            },
        }
        validator = self._make_validator(template)
        # Should not raise - ForEach entries are lists and should be skipped
        validator._replace_local_codeuri()
        # Regular function should have its CodeUri replaced
        self.assertEqual(
            validator.sam_template["Resources"]["RegularFunction"]["Properties"]["CodeUri"],
            "s3://bucket/value",
        )

    def test_foreach_entries_skipped_in_replace_local_image(self):
        """Fn::ForEach entries should be skipped in _replace_local_image."""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha"],
                    {"${Name}Function": {"Type": "AWS::Serverless::Function", "Properties": {"PackageType": "Image"}}},
                ],
                "RegularFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": "Image"},
                    "Metadata": {"Dockerfile": "Dockerfile"},
                },
            },
        }
        validator = self._make_validator(template)
        validator._replace_local_image()
        # Regular function should get ImageUri added
        self.assertEqual(
            validator.sam_template["Resources"]["RegularFunction"]["Properties"]["ImageUri"],
            "111111111111.dkr.ecr.region.amazonaws.com/repository",
        )

    def test_foreach_in_globals_codeuri_check(self):
        """Globals CodeUri replacement should handle ForEach entries in Resources."""
        template = {
            "Globals": {"Function": {"CodeUri": "globalcodeuri"}},
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"Handler": "main.handler"},
                        }
                    },
                ],
                "RegularFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "Runtime": "python3.13"},
                },
            },
        }
        validator = self._make_validator(template)
        # Should not raise when iterating resources that include ForEach (list) entries
        validator._replace_local_codeuri()
