from unittest import TestCase
from unittest.mock import Mock, patch

from samtranslator.public.exceptions import InvalidDocumentException

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.lib.sam_template_validator import SamTemplateValidator


class TestSamTemplateValidator(TestCase):
    @patch("samcli.commands.validate.lib.sam_template_validator.Session")
    @patch("samcli.commands.validate.lib.sam_template_validator.Translator")
    @patch("samcli.commands.validate.lib.sam_template_validator.parser")
    def test_is_valid_returns_true(self, sam_parser, sam_translator, boto_session_patch):
        managed_policy_mock = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.return_value = {"c": "d"}
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock, profile="profile", region="region")

        # Should not throw an Exception
        validator.is_valid()

        boto_session_patch.assert_called_once_with(profile_name="profile", region_name="region")
        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    @patch("samcli.commands.validate.lib.sam_template_validator.Session")
    @patch("samcli.commands.validate.lib.sam_template_validator.Translator")
    @patch("samcli.commands.validate.lib.sam_template_validator.parser")
    def test_is_valid_raises_exception(self, sam_parser, sam_translator, boto_session_patch):
        managed_policy_mock = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([Exception("message")])
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.is_valid()

        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )

        boto_session_patch.assert_called_once_with(profile_name=None, region_name=None)
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    def test_init(self):
        managed_policy_mock = Mock()
        template = {"a": "b"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        self.assertEqual(validator.managed_policy_loader, managed_policy_mock)
        self.assertEqual(validator.sam_template, template)

        # check to see if SamParser was created
        self.assertIsNotNone(validator.sam_parser)

    def test_update_to_s3_uri_with_non_s3_uri(self):
        property_value = {"CodeUri": "somevalue"}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEqual(property_value.get("CodeUri"), "s3://bucket/value")

    def test_update_to_s3_url_with_dict(self):
        property_value = {"CodeUri": {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212}}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEqual(
            property_value.get("CodeUri"), {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212}
        )

    def test_update_to_s3_url_with_s3_uri(self):
        property_value = {"CodeUri": "s3://bucket/key/version"}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEqual(property_value.get("CodeUri"), "s3://bucket/key/version")
