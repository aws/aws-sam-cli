import copy
from typing import Any, Dict, List
from unittest import TestCase
from unittest.mock import patch, MagicMock

from parameterized import parameterized

from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException


class TestLanguageExtensionsCheck(TestCase):
    """Tests for check_using_language_extension."""

    @parameterized.expand(
        [
            ({"Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]}, True),
            ({"Transform": ["AWS::LanguageExtensions"]}, True),
            ({"Transform": ["AWS::LanguageExtensions-extension"]}, False),
            ({"Transform": "AWS::LanguageExtensions"}, True),
            ({"Transform": "AWS::LanguageExtensions-extension"}, False),
            ({"Transform": "AWS::Serverless-2016-10-31"}, False),
            ({}, False),
        ]
    )
    def test_check_using_language_extension(self, template, expected):
        self.assertEqual(check_using_language_extension(template), expected)


class TestBuildPseudoParameters(TestCase):
    """Tests for _build_pseudo_parameters in sam_integration module."""

    def test_build_pseudo_parameters_with_all_values(self):
        """Test building pseudo parameters when all values are present."""
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        parameter_values = {
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "123456789012",
            "AWS::StackName": "my-stack",
            "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/guid",
            "AWS::Partition": "aws",
            "AWS::URLSuffix": "amazonaws.com",
            "MyParam": "my-value",  # Non-pseudo parameter
        }
        pseudo_params = _build_pseudo_parameters(parameter_values)

        self.assertIsNotNone(pseudo_params)
        self.assertEqual(pseudo_params.region, "us-east-1")
        self.assertEqual(pseudo_params.account_id, "123456789012")
        self.assertEqual(pseudo_params.stack_name, "my-stack")
        self.assertEqual(pseudo_params.stack_id, "arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/guid")
        self.assertEqual(pseudo_params.partition, "aws")
        self.assertEqual(pseudo_params.url_suffix, "amazonaws.com")

    def test_build_pseudo_parameters_with_partial_values(self):
        """Test building pseudo parameters when only some values are present."""
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        parameter_values = {
            "AWS::Region": "us-west-2",
            "AWS::AccountId": "987654321098",
            "MyParam": "my-value",
        }
        pseudo_params = _build_pseudo_parameters(parameter_values)

        self.assertIsNotNone(pseudo_params)
        self.assertEqual(pseudo_params.region, "us-west-2")
        self.assertEqual(pseudo_params.account_id, "987654321098")
        self.assertIsNone(pseudo_params.stack_name)
        self.assertIsNone(pseudo_params.stack_id)
        self.assertIsNone(pseudo_params.partition)
        self.assertIsNone(pseudo_params.url_suffix)

    def test_build_pseudo_parameters_with_no_pseudo_params(self):
        """Test building pseudo parameters when no pseudo params are present."""
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        parameter_values = {
            "MyParam": "my-value",
            "AnotherParam": "another-value",
        }
        pseudo_params = _build_pseudo_parameters(parameter_values)

        self.assertIsNone(pseudo_params)

    def test_build_pseudo_parameters_with_none_parameter_values(self):
        """Test building pseudo parameters when parameter_values is None."""
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        pseudo_params = _build_pseudo_parameters(None)

        self.assertIsNone(pseudo_params)

    def test_build_pseudo_parameters_with_empty_parameter_values(self):
        """Test building pseudo parameters when parameter_values is empty."""
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        pseudo_params = _build_pseudo_parameters({})

        self.assertIsNone(pseudo_params)


class TestProcessLanguageExtensions(TestCase):
    """Tests for expand_language_extensions in sam_integration module (formerly _process_language_extensions on wrapper)."""

    @patch("samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli")
    def test_expand_language_extensions_success(self, mock_process):
        """Test successful expansion of language extensions."""
        from samcli.lib.cfn_language_extensions.sam_integration import expand_language_extensions

        input_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"FunctionName": {"Fn::Sub": "${Name}-function"}},
                        }
                    },
                ]
            },
        }
        expected_output = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"FunctionName": "Alpha-function"},
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"FunctionName": "Beta-function"},
                },
            },
        }
        mock_process.return_value = expected_output

        result = expand_language_extensions(input_template, parameter_values={"AWS::Region": "us-east-1"})

        self.assertTrue(result.had_language_extensions)
        self.assertEqual(result.expanded_template, expected_output)
        mock_process.assert_called_once()

    @patch("samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli")
    def test_expand_language_extensions_with_pseudo_params(self, mock_process):
        """Test that pseudo parameters are passed correctly."""
        from samcli.lib.cfn_language_extensions.sam_integration import expand_language_extensions

        template = {"Transform": "AWS::LanguageExtensions", "Resources": {}}
        parameter_values = {
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "123456789012",
            "MyParam": "value",
        }
        mock_process.return_value = template

        result = expand_language_extensions(template, parameter_values=parameter_values)

        self.assertTrue(result.had_language_extensions)
        # Verify process_template_for_sam_cli was called with correct arguments
        call_args = mock_process.call_args
        self.assertEqual(call_args.kwargs["parameter_values"], parameter_values)
        pseudo_params = call_args.kwargs["pseudo_parameters"]
        self.assertIsNotNone(pseudo_params)
        self.assertEqual(pseudo_params.region, "us-east-1")
        self.assertEqual(pseudo_params.account_id, "123456789012")

    @patch("samcli.lib.cfn_language_extensions.sam_integration.process_template_for_sam_cli")
    def test_expand_language_extensions_error_handling(self, mock_process):
        """Test that InvalidTemplateException is converted to InvalidSamDocumentException."""
        from samcli.lib.cfn_language_extensions import InvalidTemplateException as LangExtInvalidTemplateException
        from samcli.lib.cfn_language_extensions.sam_integration import expand_language_extensions

        template = {"Transform": "AWS::LanguageExtensions", "Resources": {}}
        mock_process.side_effect = LangExtInvalidTemplateException("Invalid Fn::ForEach syntax")

        with self.assertRaises(InvalidSamDocumentException) as context:
            expand_language_extensions(template)

        self.assertIn("Invalid Fn::ForEach syntax", str(context.exception))


class TestRunPluginsWithLanguageExtensions(TestCase):
    """Tests for run_plugins method — Phase 2 only (no language extensions processing)."""

    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_run_plugins_does_not_call_language_extensions(self, mock_parser_class):
        """Test that run_plugins no longer calls _process_language_extensions (Phase 2 only)."""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {"MyFunction": {"Type": "AWS::Serverless::Function"}},
        }

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        wrapper = SamTranslatorWrapper(template)
        # run_plugins should not attempt Phase 1 expansion
        wrapper.run_plugins()

        # Parser should still be called (Phase 2)
        mock_parser.parse.assert_called_once()

    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_run_plugins_works_with_pre_expanded_template(self, mock_parser_class):
        """Test that run_plugins works correctly with a pre-expanded template."""
        # This is what the template looks like AFTER expand_language_extensions()
        expanded_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "./src",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "./src",
                    },
                },
            },
        }

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        wrapper = SamTranslatorWrapper(expanded_template)
        result = wrapper.run_plugins()

        # Verify the parser received the expanded template
        mock_parser.parse.assert_called_once()
        parsed_template = mock_parser.parse.call_args[0][0]
        self.assertIn("AlphaFunction", parsed_template["Resources"])
        self.assertIn("BetaFunction", parsed_template["Resources"])

    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_run_plugins_with_language_extension_result(self, mock_parser_class):
        """Test that run_plugins works when LanguageExtensionResult is provided."""
        from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult

        expanded_template = {
            "Resources": {
                "AlphaFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./src"}},
            },
        }
        original_template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha"],
                    {"${Name}Function": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./src"}}},
                ],
            },
        }
        le_result = LanguageExtensionResult(
            expanded_template=expanded_template,
            original_template=original_template,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        wrapper = SamTranslatorWrapper(expanded_template, language_extension_result=le_result)
        wrapper.run_plugins()

        # Verify original template comes from the result
        preserved = wrapper.get_original_template()
        self.assertIn("Fn::ForEach::Functions", preserved["Resources"])

    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_run_plugins_without_language_extensions_template(self, mock_parser_class):
        """Test that run_plugins works normally for templates without language extensions."""
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"MyFunction": {"Type": "AWS::Serverless::Function"}},
        }

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        wrapper = SamTranslatorWrapper(template)
        wrapper.run_plugins()

        mock_parser.parse.assert_called_once()


class TestSamTranslatorWrapperTemplate(TestCase):
    """Tests for template property."""

    def test_template_returns_deep_copy(self):
        """Test that template property returns a deep copy."""
        original = {"Resources": {"MyResource": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "test"}}}}
        wrapper = SamTranslatorWrapper(original)

        template_copy = wrapper.template
        template_copy["Resources"]["MyResource"]["Properties"]["BucketName"] = "modified"

        # Original should be unchanged
        self.assertEqual(original["Resources"]["MyResource"]["Properties"]["BucketName"], "test")


# =============================================================================
# Tests for Transform Detection
# =============================================================================


class TestTransformDetectionProperties(TestCase):
    """
    Tests for transform detection.

    Feature: cfn-language-extensions-integration
    """

    @parameterized.expand(
        [
            ("string_transform", "AWS::LanguageExtensions", "MyTopic", "AWS::SNS::Topic"),
            (
                "list_transform",
                ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                "MyFunc",
                "AWS::Lambda::Function",
            ),
        ]
    )
    def test_property_1_language_extensions_detected_by_check(
        self,
        name: str,
        transform: Any,
        resource_id: str,
        resource_type: str,
    ):
        """
        Property 1: Language Extensions Detected by Transform Check

        *For any* template containing `AWS::LanguageExtensions` in its Transform field
        (either as a string or in a list), `check_using_language_extension()` SHALL return True.

        **Validates: Requirements 1.1, 1.2**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        template: Dict[str, Any] = {
            "Transform": transform,
            "Resources": {
                resource_id: {
                    "Type": resource_type,
                    "Properties": {},
                }
            },
        }

        self.assertTrue(check_using_language_extension(template))

    @parameterized.expand(
        [
            ("no_transform", None, "MyTopic", "AWS::SNS::Topic"),
            ("serverless_only", "AWS::Serverless-2016-10-31", "MyFunc", "AWS::Serverless::Function"),
            ("list_without_lang_ext", ["AWS::Serverless-2016-10-31", "AWS::Include"], "MyBucket", "AWS::S3::Bucket"),
        ]
    )
    def test_property_2_language_extensions_not_detected_without_transform(
        self,
        name: str,
        transform: Any,
        resource_id: str,
        resource_type: str,
    ):
        """
        Property 2: Language Extensions Not Detected Without Transform

        *For any* template that does NOT contain `AWS::LanguageExtensions` in its Transform field,
        `check_using_language_extension()` SHALL return False.

        **Validates: Requirements 1.1, 1.2**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        template: Dict[str, Any] = {
            "Resources": {
                resource_id: {
                    "Type": resource_type,
                    "Properties": {},
                }
            },
        }

        if transform is not None:
            template["Transform"] = transform

        self.assertFalse(check_using_language_extension(template))


# =============================================================================
# Tests for Template Immutability
# =============================================================================


class TestTemplateImmutabilityProperties(TestCase):
    """
    Tests for template immutability in SamTranslatorWrapper.

    Feature: cfn-language-extensions-integration, Property 5: Template Immutability
    """

    @parameterized.expand(
        [
            (
                "single_resource_with_lang_ext",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic", "Properties": {"TopicName": "test"}}},
                },
            ),
            (
                "list_transform_with_lang_ext",
                {
                    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                    "Resources": {
                        "MyFunc": {"Type": "AWS::Serverless::Function", "Properties": {"Runtime": "python3.9"}}
                    },
                },
            ),
            (
                "multiple_resources_with_lang_ext",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {
                        "TopicA": {"Type": "AWS::SNS::Topic", "Properties": {}},
                        "QueueB": {"Type": "AWS::SQS::Queue", "Properties": {"VisibilityTimeout": 30}},
                    },
                },
            ),
        ]
    )
    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_property_5_template_immutability_with_language_extensions(
        self,
        name: str,
        template: Dict[str, Any],
        mock_parser_class: MagicMock,
    ):
        """
        Property 5: Template Immutability (with language extensions)

        *For any* template processed by `SamTranslatorWrapper`, the original template
        dictionary passed to the constructor SHALL remain unchanged after `run_plugins()`
        completes (whether successfully or with an error).

        **Validates: Requirements 1.5**
        """
        # Create a deep copy of the original template to compare later
        original_template = copy.deepcopy(template)

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Execute — run_plugins is Phase 2 only now
        wrapper = SamTranslatorWrapper(template)
        wrapper.run_plugins()

        # Verify the original template passed to constructor is unchanged
        self.assertEqual(template, original_template)

    @parameterized.expand(
        [
            (
                "single_resource_no_lang_ext",
                {
                    "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "test"}}},
                },
            ),
            (
                "multiple_resources_no_lang_ext",
                {
                    "Resources": {
                        "TopicA": {"Type": "AWS::SNS::Topic", "Properties": {}},
                        "TableB": {"Type": "AWS::DynamoDB::Table", "Properties": {"TableName": "items"}},
                    },
                },
            ),
        ]
    )
    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_property_5_template_immutability_without_language_extensions(
        self,
        name: str,
        template: Dict[str, Any],
        mock_parser_class: MagicMock,
    ):
        """
        Property 5: Template Immutability (without language extensions)

        *For any* template processed by `SamTranslatorWrapper`, the original template
        dictionary passed to the constructor SHALL remain unchanged after `run_plugins()`
        completes (whether successfully or with an error).

        **Validates: Requirements 1.5**
        """
        # Create a deep copy of the original template to compare later
        original_template = copy.deepcopy(template)

        # Setup mocks
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Execute
        wrapper = SamTranslatorWrapper(template)
        wrapper.run_plugins()

        # Verify the original template passed to constructor is unchanged
        self.assertEqual(template, original_template)

    @parameterized.expand(
        [
            (
                "single_resource_error",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic", "Properties": {}}},
                },
            ),
            (
                "list_transform_error",
                {
                    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                    "Resources": {
                        "MyFunc": {"Type": "AWS::Lambda::Function", "Properties": {"Handler": "index.handler"}}
                    },
                },
            ),
        ]
    )
    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_property_5_template_immutability_on_error(
        self,
        name: str,
        template: Dict[str, Any],
        mock_parser_class: MagicMock,
    ):
        """
        Property 5: Template Immutability (on error)

        *For any* template processed by `SamTranslatorWrapper`, the original template
        dictionary passed to the constructor SHALL remain unchanged after `run_plugins()`
        completes with an error.

        **Validates: Requirements 1.5**
        """
        from samtranslator.model.exceptions import InvalidDocumentException, InvalidTemplateException

        # Create a deep copy of the original template to compare later
        original_template = copy.deepcopy(template)

        # Setup mocks - simulate a parser error (Phase 2 error)
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = InvalidDocumentException([InvalidTemplateException("Test error")])
        mock_parser_class.return_value = mock_parser

        # Execute and expect exception
        wrapper = SamTranslatorWrapper(template)
        with self.assertRaises(InvalidSamDocumentException):
            wrapper.run_plugins()

        # Verify the original template passed to constructor is unchanged
        self.assertEqual(template, original_template)


# =============================================================================
# Tests for Pseudo-Parameter Extraction
# =============================================================================


class TestPseudoParameterExtractionProperties(TestCase):
    """
    Tests for pseudo-parameter extraction.

    Feature: cfn-language-extensions-integration
    """

    @parameterized.expand(
        [
            (
                "region_only",
                {"AWS::Region": "us-east-1"},
            ),
            (
                "region_and_account",
                {"AWS::Region": "us-west-2", "AWS::AccountId": "123456789012"},
            ),
            (
                "all_pseudo_params",
                {
                    "AWS::Region": "eu-west-1",
                    "AWS::AccountId": "987654321098",
                    "AWS::StackName": "my-stack",
                    "AWS::StackId": "arn:aws:cloudformation:eu-west-1:987654321098:stack/my-stack/guid",
                    "AWS::Partition": "aws",
                    "AWS::URLSuffix": "amazonaws.com",
                },
            ),
        ]
    )
    def test_property_6_pseudo_parameter_extraction_completeness(
        self,
        name: str,
        parameter_values: Dict[str, Any],
    ):
        """
        Property 6: Pseudo-Parameter Extraction Completeness

        *For any* parameter_values dictionary containing one or more AWS pseudo-parameters
        (`AWS::Region`, `AWS::AccountId`, `AWS::StackName`, `AWS::StackId`, `AWS::Partition`,
        `AWS::URLSuffix`), the `_build_pseudo_parameters()` function SHALL return a
        `PseudoParameterValues` object with all present pseudo-parameters correctly populated.

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        result = _build_pseudo_parameters(parameter_values)

        # Result should NOT be None since we have at least one pseudo-parameter
        self.assertIsNotNone(result, "Expected PseudoParameterValues but got None")
        assert result is not None  # For mypy

        # Verify each pseudo-parameter is correctly extracted if present in input
        if "AWS::Region" in parameter_values:
            self.assertEqual(result.region, parameter_values["AWS::Region"])
        else:
            self.assertEqual(result.region, "")

        if "AWS::AccountId" in parameter_values:
            self.assertEqual(result.account_id, parameter_values["AWS::AccountId"])
        else:
            self.assertEqual(result.account_id, "")

        if "AWS::StackName" in parameter_values:
            self.assertEqual(result.stack_name, parameter_values["AWS::StackName"])
        else:
            self.assertIsNone(result.stack_name)

        if "AWS::StackId" in parameter_values:
            self.assertEqual(result.stack_id, parameter_values["AWS::StackId"])
        else:
            self.assertIsNone(result.stack_id)

        if "AWS::Partition" in parameter_values:
            self.assertEqual(result.partition, parameter_values["AWS::Partition"])
        else:
            self.assertIsNone(result.partition)

        if "AWS::URLSuffix" in parameter_values:
            self.assertEqual(result.url_suffix, parameter_values["AWS::URLSuffix"])
        else:
            self.assertIsNone(result.url_suffix)

    @parameterized.expand(
        [
            ("none_input", None),
            ("empty_dict", {}),
            ("non_pseudo_only", {"MyParam": "value", "AnotherParam": "other"}),
        ]
    )
    def test_property_7_pseudo_parameter_extraction_returns_none_for_empty_input(
        self,
        name: str,
        parameter_values: Any,
    ):
        """
        Property 7: Pseudo-Parameter Extraction Returns None for Empty Input

        *For any* parameter_values that is None, empty, or contains no AWS pseudo-parameters,
        the `_build_pseudo_parameters()` function SHALL return None.

        **Validates: Requirements 2.7, 2.8**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import _build_pseudo_parameters

        result = _build_pseudo_parameters(parameter_values)

        self.assertIsNone(
            result,
            f"Expected None but got PseudoParameterValues for parameter_values: {parameter_values}",
        )


# =============================================================================
# Tests for Original Template Preservation
# =============================================================================


class TestOriginalTemplatePreservation(TestCase):
    """
    Tests for original template preservation in SamTranslatorWrapper.

    Feature: cfn-language-extensions-integration
    **Validates: Requirements 15.1, 15.2, 15.3**
    """

    def test_get_original_template_returns_deep_copy(self):
        """Test that get_original_template() returns a deep copy of the original template."""
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"Handler": "${Name}.handler"},
                        }
                    },
                ]
            },
        }
        wrapper = SamTranslatorWrapper(original)

        # Get the original template
        result = wrapper.get_original_template()

        # Verify it contains the Fn::ForEach structure
        self.assertIn("Fn::ForEach::Functions", result["Resources"])

        # Modify the returned template
        result["Resources"]["NewResource"] = {"Type": "AWS::S3::Bucket"}

        # Get original again and verify it's unchanged
        result2 = wrapper.get_original_template()
        self.assertNotIn("NewResource", result2["Resources"])
        self.assertIn("Fn::ForEach::Functions", result2["Resources"])

    def test_get_original_template_returns_unexpanded_template(self):
        """
        Test that get_original_template() returns the unexpanded template with Fn::ForEach intact.

        **Validates: Requirements 15.1**
        """
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "ServiceName",
                    ["Users", "Orders", "Products"],
                    {
                        "${ServiceName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "${ServiceName}.handler",
                                "Runtime": "python3.9",
                                "CodeUri": "./src",
                            },
                        }
                    },
                ]
            },
        }
        wrapper = SamTranslatorWrapper(original)

        # Get the original template
        result = wrapper.get_original_template()

        # Verify it returns the unexpanded template (Fn::ForEach intact)
        self.assertIn("Fn::ForEach::Services", result["Resources"])
        # Verify expanded resources are NOT present
        self.assertNotIn("UsersFunction", result["Resources"])
        self.assertNotIn("OrdersFunction", result["Resources"])
        self.assertNotIn("ProductsFunction", result["Resources"])
        # Verify the Fn::ForEach structure is complete
        foreach_block = result["Resources"]["Fn::ForEach::Services"]
        self.assertEqual(foreach_block[0], "ServiceName")  # Loop variable
        self.assertEqual(foreach_block[1], ["Users", "Orders", "Products"])  # Collection
        self.assertIn("${ServiceName}Function", foreach_block[2])  # Output template

    def test_foreach_structure_preserved_with_all_elements(self):
        """
        Test that Fn::ForEach structure is preserved with all its elements intact.

        **Validates: Requirements 15.3**
        """
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta", "Gamma"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": {"Fn::Sub": "${Name}.handler"},
                                "Runtime": "python3.9",
                                "CodeUri": "./src",
                                "Environment": {
                                    "Variables": {
                                        "FUNCTION_NAME": {"Fn::Sub": "${Name}"},
                                    }
                                },
                            },
                        }
                    },
                ]
            },
        }
        wrapper = SamTranslatorWrapper(original)

        # Get the original template
        result = wrapper.get_original_template()

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Functions", result["Resources"])
        foreach_block = result["Resources"]["Fn::ForEach::Functions"]

        # Verify all three elements are preserved
        self.assertEqual(len(foreach_block), 3)

        # Element 1: Loop variable
        self.assertEqual(foreach_block[0], "Name")

        # Element 2: Collection
        self.assertEqual(foreach_block[1], ["Alpha", "Beta", "Gamma"])

        # Element 3: Output template with resource definition
        output_template = foreach_block[2]
        self.assertIn("${Name}Function", output_template)
        resource_def = output_template["${Name}Function"]
        self.assertEqual(resource_def["Type"], "AWS::Serverless::Function")
        self.assertEqual(resource_def["Properties"]["Handler"], {"Fn::Sub": "${Name}.handler"})
        self.assertEqual(resource_def["Properties"]["Runtime"], "python3.9")
        self.assertEqual(resource_def["Properties"]["CodeUri"], "./src")
        self.assertEqual(
            resource_def["Properties"]["Environment"]["Variables"]["FUNCTION_NAME"], {"Fn::Sub": "${Name}"}
        )

    def test_multiple_foreach_blocks_preserved(self):
        """
        Test that multiple Fn::ForEach blocks are all preserved in the original template.

        **Validates: Requirements 15.3**
        """
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FuncName",
                    ["Alpha", "Beta"],
                    {
                        "${FuncName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"Handler": "index.handler"},
                        }
                    },
                ],
                "Fn::ForEach::Tables": [
                    "TableName",
                    ["Users", "Orders"],
                    {
                        "${TableName}Table": {
                            "Type": "AWS::DynamoDB::Table",
                            "Properties": {"TableName": {"Fn::Sub": "${TableName}"}},
                        }
                    },
                ],
                "StaticResource": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": "my-bucket"},
                },
            },
        }
        wrapper = SamTranslatorWrapper(original)

        # Get the original template
        result = wrapper.get_original_template()

        # Verify both Fn::ForEach blocks are preserved
        self.assertIn("Fn::ForEach::Functions", result["Resources"])
        self.assertIn("Fn::ForEach::Tables", result["Resources"])
        # Verify static resource is also preserved
        self.assertIn("StaticResource", result["Resources"])

        # Verify expanded resources are NOT present
        self.assertNotIn("AlphaFunction", result["Resources"])
        self.assertNotIn("BetaFunction", result["Resources"])
        self.assertNotIn("UsersTable", result["Resources"])
        self.assertNotIn("OrdersTable", result["Resources"])

        # Verify Fn::ForEach::Functions structure
        func_foreach = result["Resources"]["Fn::ForEach::Functions"]
        self.assertEqual(func_foreach[0], "FuncName")
        self.assertEqual(func_foreach[1], ["Alpha", "Beta"])

        # Verify Fn::ForEach::Tables structure
        table_foreach = result["Resources"]["Fn::ForEach::Tables"]
        self.assertEqual(table_foreach[0], "TableName")
        self.assertEqual(table_foreach[1], ["Users", "Orders"])

    def test_original_template_unchanged_after_run_plugins(self):
        """
        Test that original template is unchanged after run_plugins() processes it.

        **Validates: Requirements 15.2**
        """
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "${Name}.handler",
                                "Runtime": "python3.9",
                                "CodeUri": "./src",
                            },
                        }
                    },
                ]
            },
        }
        import copy

        original_copy = copy.deepcopy(original)

        with patch("samcli.lib.samlib.wrapper._SamParserReimplemented") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            wrapper = SamTranslatorWrapper(original)

            # Run plugins (Phase 2 only — no expansion)
            wrapper.run_plugins()

            # Get original template - should still have Fn::ForEach
            preserved = wrapper.get_original_template()
            self.assertIn("Fn::ForEach::Functions", preserved["Resources"])

            # Verify the entire original structure is preserved
            self.assertEqual(preserved, original_copy)

    def test_foreach_structure_preserved_after_run_plugins(self):
        """
        Test that Fn::ForEach structure is preserved in original template after run_plugins().

        This test verifies that after run_plugins() processes the template (Phase 2 only),
        the original template still contains the complete Fn::ForEach structure.

        **Validates: Requirements 15.2, 15.3**
        """
        original = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "Environment": {"Type": "String", "Default": "dev"},
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "ServiceName",
                    ["Auth", "Payment", "Notification"],
                    {
                        "${ServiceName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "FunctionName": {"Fn::Sub": "${ServiceName}-${Environment}"},
                                "Handler": {"Fn::Sub": "${ServiceName}.handler"},
                                "Runtime": "python3.9",
                                "CodeUri": "./services",
                                "Environment": {
                                    "Variables": {
                                        "SERVICE_NAME": {"Fn::Sub": "${ServiceName}"},
                                    }
                                },
                            },
                        }
                    },
                ]
            },
        }

        with patch("samcli.lib.samlib.wrapper._SamParserReimplemented") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            wrapper = SamTranslatorWrapper(original)

            # Run plugins (Phase 2 only)
            wrapper.run_plugins()

            # Get original template
            preserved = wrapper.get_original_template()

            # Verify Fn::ForEach structure is preserved
            self.assertIn("Fn::ForEach::Services", preserved["Resources"])
            foreach_block = preserved["Resources"]["Fn::ForEach::Services"]

            # Verify all three elements of Fn::ForEach are intact
            self.assertEqual(len(foreach_block), 3)
            self.assertEqual(foreach_block[0], "ServiceName")  # Loop variable
            self.assertEqual(foreach_block[1], ["Auth", "Payment", "Notification"])  # Collection

            # Verify output template structure
            output_template = foreach_block[2]
            self.assertIn("${ServiceName}Function", output_template)
            resource_def = output_template["${ServiceName}Function"]
            self.assertEqual(resource_def["Type"], "AWS::Serverless::Function")
            self.assertEqual(resource_def["Properties"]["FunctionName"], {"Fn::Sub": "${ServiceName}-${Environment}"})
            self.assertEqual(resource_def["Properties"]["Handler"], {"Fn::Sub": "${ServiceName}.handler"})

    def test_original_template_preserved_on_error(self):
        """Test that original template is preserved even when run_plugins fails."""
        from samtranslator.model.exceptions import InvalidDocumentException, InvalidTemplateException

        original = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "Fn::ForEach::Invalid": ["missing", "arguments"],
            },
        }

        with patch("samcli.lib.samlib.wrapper._SamParserReimplemented") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.parse.side_effect = InvalidDocumentException([InvalidTemplateException("Parse error")])
            mock_parser_class.return_value = mock_parser

            wrapper = SamTranslatorWrapper(original)

            # Run plugins should raise an exception (Phase 2 error)
            with self.assertRaises(InvalidSamDocumentException):
                wrapper.run_plugins()

            # Original template should still be preserved
            preserved = wrapper.get_original_template()
            self.assertIn("Fn::ForEach::Invalid", preserved["Resources"])

    def test_original_template_independent_of_input_modifications(self):
        """Test that original template is independent of modifications to the input dict."""
        original = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler"},
                }
            },
        }

        wrapper = SamTranslatorWrapper(original)

        # Modify the original dict after creating wrapper
        original["Resources"]["NewResource"] = {"Type": "AWS::S3::Bucket"}
        original["Resources"]["MyFunction"]["Properties"]["Handler"] = "modified.handler"

        # Get original template - should NOT have the modifications
        preserved = wrapper.get_original_template()
        self.assertNotIn("NewResource", preserved["Resources"])
        self.assertEqual(preserved["Resources"]["MyFunction"]["Properties"]["Handler"], "index.handler")


# =============================================================================
# Tests for Original Template Preservation (Parameterized)
# =============================================================================


class TestOriginalTemplatePreservationProperties(TestCase):
    """
    Tests for original template preservation in SamTranslatorWrapper.

    Feature: cfn-language-extensions-integration
    **Validates: Requirements 1.5, 3.1, 3.2, 3.3, 3.4**
    """

    @parameterized.expand(
        [
            (
                "single_resource",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic", "Properties": {"TopicName": "test"}}},
                },
            ),
            (
                "list_transform",
                {
                    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                    "Resources": {
                        "MyFunc": {"Type": "AWS::Serverless::Function", "Properties": {"Runtime": "python3.9"}}
                    },
                },
            ),
            (
                "multiple_resources",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {
                        "TopicA": {"Type": "AWS::SNS::Topic", "Properties": {}},
                        "QueueB": {"Type": "AWS::SQS::Queue", "Properties": {}},
                    },
                },
            ),
        ]
    )
    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_property_3_original_template_preserved_for_output(
        self,
        name: str,
        template: Dict[str, Any],
        mock_parser_class: MagicMock,
    ):
        """
        Property 3: Original Template Preserved for Output

        *For any* template with `Fn::ForEach` constructs, after processing,
        the `get_original_template()` method SHALL return a template that
        preserves the original `Fn::ForEach` structure.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Create a deep copy of the original template to compare later
        original_template = copy.deepcopy(template)

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Execute — run_plugins is Phase 2 only
        wrapper = SamTranslatorWrapper(template)
        wrapper.run_plugins()

        # Verify get_original_template() returns the original structure
        preserved = wrapper.get_original_template()
        self.assertEqual(preserved, original_template)

    @parameterized.expand(
        [
            (
                "single_resource",
                {
                    "Transform": "AWS::LanguageExtensions",
                    "Resources": {"MyTopic": {"Type": "AWS::SNS::Topic", "Properties": {}}},
                },
            ),
            (
                "list_transform",
                {
                    "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
                    "Resources": {
                        "MyFunc": {"Type": "AWS::Serverless::Function", "Properties": {"Runtime": "python3.9"}}
                    },
                },
            ),
        ]
    )
    def test_get_original_template_returns_independent_copy(
        self,
        name: str,
        template: Dict[str, Any],
    ):
        """
        Test that get_original_template() returns an independent deep copy.

        Modifying the returned template should not affect subsequent calls
        to get_original_template().

        **Validates: Requirements 1.5**
        """
        original_template = copy.deepcopy(template)

        wrapper = SamTranslatorWrapper(template)

        # Get original template and modify it
        result1 = wrapper.get_original_template()
        result1["Resources"]["ModifiedResource"] = {"Type": "AWS::S3::Bucket"}

        # Get original template again
        result2 = wrapper.get_original_template()

        # result2 should match the original, not the modified result1
        self.assertEqual(result2, original_template)
        self.assertNotIn("ModifiedResource", result2["Resources"])
