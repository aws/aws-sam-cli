"""
Unit tests for deploy exceptions
"""

from unittest import TestCase

from samcli.commands.deploy.exceptions import (
    parse_findmap_error,
    MissingMappingKeyError,
    DeployFailedError,
)


class TestParseFindmapError(TestCase):
    """Tests for the parse_findmap_error function"""

    def test_parse_findmap_error_with_single_quotes(self):
        """Test parsing error message with single quotes around key and mapping name"""
        error_message = "Fn::FindInMap - Key 'Products' not found in Mapping 'SAMCodeUriServices'"
        result = parse_findmap_error(error_message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Products")
        self.assertEqual(result[1], "SAMCodeUriServices")

    def test_parse_findmap_error_with_double_quotes(self):
        """Test parsing error message with double quotes around key and mapping name"""
        error_message = 'Fn::FindInMap - Key "Products" not found in Mapping "SAMCodeUriServices"'
        result = parse_findmap_error(error_message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Products")
        self.assertEqual(result[1], "SAMCodeUriServices")

    def test_parse_findmap_error_without_quotes(self):
        """Test parsing error message without quotes around key and mapping name"""
        error_message = "Fn::FindInMap - Key Products not found in Mapping SAMCodeUriServices"
        result = parse_findmap_error(error_message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Products")
        self.assertEqual(result[1], "SAMCodeUriServices")

    def test_parse_findmap_error_with_waiter_error_wrapper(self):
        """Test parsing error message wrapped in WaiterError format"""
        error_message = (
            "Waiter StackCreateComplete failed: Waiter encountered a terminal failure state: "
            'For expression "Stacks[].StackStatus" we matched expected path: "CREATE_FAILED" '
            "at least once. Resource handler returned message: \"Fn::FindInMap - Key 'NewService' "
            "not found in Mapping 'SAMCodeUriMyLoop'\" (RequestToken: abc123)"
        )
        result = parse_findmap_error(error_message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "NewService")
        self.assertEqual(result[1], "SAMCodeUriMyLoop")

    def test_parse_findmap_error_with_different_mapping_names(self):
        """Test parsing error message with various mapping name patterns"""
        test_cases = [
            ("Fn::FindInMap - Key 'Alpha' not found in Mapping 'SAMContentUriLayers'", "Alpha", "SAMContentUriLayers"),
            (
                "Fn::FindInMap - Key 'Beta' not found in Mapping 'SAMDefinitionUriAPIs'",
                "Beta",
                "SAMDefinitionUriAPIs",
            ),
            ("Fn::FindInMap - Key 'Gamma' not found in Mapping 'CustomMapping'", "Gamma", "CustomMapping"),
        ]
        for error_message, expected_key, expected_mapping in test_cases:
            with self.subTest(error_message=error_message):
                result = parse_findmap_error(error_message)
                self.assertIsNotNone(result)
                self.assertEqual(result[0], expected_key)
                self.assertEqual(result[1], expected_mapping)

    def test_parse_findmap_error_returns_none_for_non_matching_error(self):
        """Test that non-matching error messages return None"""
        non_matching_errors = [
            "Some other CloudFormation error",
            "Resource creation failed",
            "Invalid template format",
            "Stack already exists",
            "",
        ]
        for error_message in non_matching_errors:
            with self.subTest(error_message=error_message):
                result = parse_findmap_error(error_message)
                self.assertIsNone(result)

    def test_parse_findmap_error_with_special_characters_in_key(self):
        """Test parsing error message with special characters in key name"""
        # Keys with hyphens
        error_message = "Fn::FindInMap - Key 'user-service' not found in Mapping 'SAMCodeUriServices'"
        result = parse_findmap_error(error_message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "user-service")
        self.assertEqual(result[1], "SAMCodeUriServices")


class TestMissingMappingKeyError(TestCase):
    """Tests for the MissingMappingKeyError exception"""

    def test_missing_mapping_key_error_message_format(self):
        """Test that the error message is formatted correctly"""
        error = MissingMappingKeyError(
            stack_name="my-stack",
            missing_key="Products",
            mapping_name="SAMCodeUriServices",
            original_error="Fn::FindInMap - Key 'Products' not found in Mapping 'SAMCodeUriServices'",
        )

        # Check that key information is in the message
        self.assertIn("my-stack", str(error))
        self.assertIn("Products", str(error))
        self.assertIn("SAMCodeUriServices", str(error))

        # Check that helpful guidance is included
        self.assertIn("sam package", str(error))
        self.assertIn("sam deploy", str(error))
        self.assertIn("parameter values", str(error))

        # Check that the original error is preserved
        self.assertIn("Original CloudFormation error", str(error))

    def test_missing_mapping_key_error_attributes(self):
        """Test that the error attributes are set correctly"""
        error = MissingMappingKeyError(
            stack_name="test-stack",
            missing_key="NewValue",
            mapping_name="SAMCodeUriLoop",
            original_error="original error message",
        )

        self.assertEqual(error.stack_name, "test-stack")
        self.assertEqual(error.missing_key, "NewValue")
        self.assertEqual(error.mapping_name, "SAMCodeUriLoop")
        self.assertEqual(error.original_error, "original error message")

    def test_missing_mapping_key_error_suggests_repackaging(self):
        """Test that the error message suggests re-running sam package"""
        error = MissingMappingKeyError(
            stack_name="my-stack",
            missing_key="NewService",
            mapping_name="SAMCodeUriServices",
            original_error="test error",
        )

        message = str(error)
        self.assertIn("Re-run 'sam package'", message)
        self.assertIn("--parameter-overrides", message)

    def test_missing_mapping_key_error_explains_foreach_constraint(self):
        """Test that the error message explains the Fn::ForEach constraint"""
        error = MissingMappingKeyError(
            stack_name="my-stack",
            missing_key="NewService",
            mapping_name="SAMCodeUriServices",
            original_error="test error",
        )

        message = str(error)
        self.assertIn("Fn::ForEach", message)
        self.assertIn("package time", message)


class TestIsSamGeneratedMapping(TestCase):
    """Tests for the is_sam_generated_mapping classifier.

    The classifier gates whether Deployer wraps a CloudFormation
    Fn::FindInMap failure as MissingMappingKeyError (which emits
    SAM-specific guidance). False positives mis-direct users whose
    own Mappings happen to start with SAM; false negatives fall
    through to generic DeployFailedError, which is still safe.
    """

    def test_sam_generated_names_match(self):
        from samcli.lib.cfn_language_extensions.utils import is_sam_generated_mapping

        for name in (
            "SAMCodeUriServices",
            "SAMContentUriLayers",
            "SAMDefinitionUriEnvsFunctions",
            "SAMImageUriFunctionsApi",
            # Digit-leading loop name: Fn::ForEach::1stBatch
            "SAMCodeUri1stBatch",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_sam_generated_mapping(name))

    def test_user_mapping_names_do_not_match(self):
        from samcli.lib.cfn_language_extensions.utils import is_sam_generated_mapping

        for name in (
            "RegionMap",
            "EnvironmentConfig",
            "AmiMap",
            # Accidental SAM prefix
            "SAMPLE",
            "SAMSUNG",
            # Bare prefix with no property segment
            "SAM",
            # Lower-case prefix is not ours
            "sam_CodeUri",
            "SamCodeUri",
            # Empty and None
            "",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_sam_generated_mapping(name))

    def test_none_input_is_false(self):
        from samcli.lib.cfn_language_extensions.utils import is_sam_generated_mapping

        self.assertFalse(is_sam_generated_mapping(None))
