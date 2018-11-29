from unittest import TestCase
from mock import Mock, patch

from samtranslator.public.exceptions import InvalidDocumentException

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.lib.sam_template_validator import SamTemplateValidator


class TestSamTemplateValidator(TestCase):

    @patch('samcli.commands.validate.lib.sam_template_validator.Translator')
    @patch('samcli.commands.validate.lib.sam_template_validator.parser')
    def test_is_valid_returns_true(self, sam_parser, sam_translator):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        translate_mock = Mock()
        translate_mock.translate.return_value = {"c": "d"}
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an Exception
        validator.is_valid()

        sam_translator.assert_called_once_with(managed_policy_map={"policy": "SomePolicy"},
                                               sam_parser=parser,
                                               plugins=[])
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    @patch('samcli.commands.validate.lib.sam_template_validator.Translator')
    @patch('samcli.commands.validate.lib.sam_template_validator.parser')
    def test_is_valid_raises_exception(self, sam_parser, sam_translator):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([Exception('message')])
        sam_translator.return_value = translate_mock

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.is_valid()

        sam_translator.assert_called_once_with(managed_policy_map={"policy": "SomePolicy"},
                                               sam_parser=parser,
                                               plugins=[])
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()

    def test_init(self):
        managed_policy_mock = Mock()
        template = {"a": "b"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        self.assertEquals(validator.managed_policy_loader, managed_policy_mock)
        self.assertEquals(validator.sam_template, template)

        # check to see if SamParser was created
        self.assertIsNotNone(validator.sam_parser)

    def test_uri_is_s3_uri(self):
        self.assertTrue(SamTemplateValidator.is_s3_uri("s3://bucket/key"))

    def test_uri_is_not_s3_uri(self):
        self.assertFalse(SamTemplateValidator.is_s3_uri("www.amazon.com"))

    def test_int_is_not_s3_uri(self):
        self.assertFalse(SamTemplateValidator.is_s3_uri(100))

    def test_update_to_s3_uri_with_non_s3_uri(self):
        property_value = {"CodeUri": "somevalue"}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEquals(property_value.get("CodeUri"), "s3://bucket/value")

    def test_update_to_s3_url_with_dict(self):
        property_value = {"CodeUri": {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212}}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEquals(property_value.get("CodeUri"),
                          {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212})

    def test_update_to_s3_url_with_s3_uri(self):
        property_value = {"CodeUri": "s3://bucket/key/version"}
        SamTemplateValidator._update_to_s3_uri("CodeUri", property_value)

        self.assertEquals(property_value.get("CodeUri"), "s3://bucket/key/version")

    def test_replace_local_codeuri(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionUri": "./"
                    }
                },
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "CodeUri": "./",
                        "Runtime": "nodejs6.10",
                        "Timeout": 60
                    }
                },
                "ServerlessLayerVersion": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {
                        "ContentUri": "./"
                    }
                }
            }
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEquals(template_resources.get("ServerlessApi").get("Properties").get("DefinitionUri"),
                          "s3://bucket/value")
        self.assertEquals(template_resources.get("ServerlessFunction").get("Properties").get("CodeUri"),
                          "s3://bucket/value")
        self.assertEquals(template_resources.get("ServerlessLayerVersion").get("Properties").get("ContentUri"),
                          "s3://bucket/value")

    def test_replace_local_codeuri_when_no_codeuri_given(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                    }
                },
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "nodejs6.10",
                        "Timeout": 60
                    }
                }
            }
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        tempalte_resources = validator.sam_template.get("Resources")
        self.assertEquals(tempalte_resources.get("ServerlessApi").get("Properties").get("DefinitionUri"),
                          "s3://bucket/value")
        self.assertEquals(tempalte_resources.get("ServerlessFunction").get("Properties").get("CodeUri"),
                          "s3://bucket/value")

    def test_DefinitionUri_does_not_get_added_to_template_when_DefinitionBody_given(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": {
                            "swagger": {}
                        }
                    }
                }
            }
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        tempalte_resources = validator.sam_template.get("Resources")
        self.assertNotIn("DefinitionUri", tempalte_resources.get("ServerlessApi").get("Properties"))
        self.assertIn("DefinitionBody", tempalte_resources.get("ServerlessApi").get("Properties"))

    def test_replace_local_codeuri_with_no_resources(self):

        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {}
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        self.assertEquals(validator.sam_template.get("Resources"), {})
