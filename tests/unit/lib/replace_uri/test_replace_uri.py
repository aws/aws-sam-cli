from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.utils.packagetype import IMAGE

from samcli.lib.replace_uri import replace_uri
from samcli.lib.replace_uri.replace_uri import replace_local_codeuri


class TestReplaceUri(TestCase):
    def test_uri_is_s3_uri(self):
        self.assertTrue(replace_uri.is_s3_uri("s3://bucket/key"))

    def test_uri_is_not_s3_uri(self):
        self.assertFalse(replace_uri.is_s3_uri("www.amazon.com"))

    def test_int_is_not_s3_uri(self):
        self.assertFalse(replace_uri.is_s3_uri(100))

    def test_replace_local_codeuri(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"StageName": "Prod", "DefinitionUri": "./"},
                },
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "CodeUri": "./", "Runtime": "nodejs6.10", "Timeout": 60},
                },
                "ServerlessLayerVersion": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "./"}},
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {"DefinitionUri": "./", "Role": "test-role-arn"},
                },
            },
        }

        # check template
        template_resources = replace_local_codeuri(template).get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessApi").get("Properties").get("DefinitionUri"), "s3://bucket/value"
        )
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("CodeUri"), "s3://bucket/value"
        )
        self.assertEqual(
            template_resources.get("ServerlessLayerVersion").get("Properties").get("ContentUri"), "s3://bucket/value"
        )
        self.assertEqual(
            template_resources.get("ServerlessStateMachine").get("Properties").get("DefinitionUri"), "s3://bucket/value"
        )

    def test_replace_local_codeuri_when_no_codeuri_given(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "Runtime": "nodejs6.10", "Timeout": 60},
                },
            },
        }

        # check template
        tempalte_resources = replace_local_codeuri(template).get("Resources")
        self.assertEqual(
            tempalte_resources.get("ServerlessFunction").get("Properties").get("CodeUri"), "s3://bucket/value"
        )

    def test_dont_replace_local_codeuri_when_no_codeuri_given_packagetype_image(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": IMAGE, "ImageUri": "myimage:latest", "Timeout": 60},
                },
            },
        }

        # check template
        template_resources = replace_local_codeuri(template).get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("CodeUri", "NotPresent"), "NotPresent"
        )

    def test_dont_replace_codeuri_when_global_code_uri_given_packagetype_image(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Globals": {"Function": {"CodeUri": "globalcodeuri", "Timeout": "3"}},
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": IMAGE, "ImageUri": "myimage:latest", "Timeout": 60},
                },
            },
        }

        # check template
        template_resources = replace_local_codeuri(template).get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("CodeUri", "NotPresent"), "NotPresent"
        )

    def test_dont_replace_codeuri_when_global_code_uri_given__both_packagetype(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Globals": {
                "Function": {
                    "CodeUri": "s3://globalcodeuri",
                }
            },
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunctionImage": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": IMAGE, "ImageUri": "myimage:latest", "Timeout": 60},
                },
                "ServerlessFunctionZip": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "Runtime": "nodejs6.10", "Timeout": 60},
                },
            },
        }

        # check template
        template_resources = replace_local_codeuri(template).get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunctionImage").get("Properties").get("CodeUri", "NotPresent"),
            "NotPresent",
        )
        # Globals not set since they cant apply to both Zip and Image based packagetypes.
        self.assertEqual(
            template_resources.get("ServerlessFunctionZip").get("Properties").get("CodeUri"), "s3://bucket/value"
        )

    def test_DefinitionUri_does_not_get_added_to_template_when_DefinitionBody_given(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"StageName": "Prod", "DefinitionBody": {"swagger": {}}},
                }
            },
        }

        tempalte_resources = replace_local_codeuri(template).get("Resources")
        self.assertNotIn("DefinitionUri", tempalte_resources.get("ServerlessApi").get("Properties"))
        self.assertIn("DefinitionBody", tempalte_resources.get("ServerlessApi").get("Properties"))

    def test_replace_local_codeuri_with_no_resources(self):

        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {},
        }

        # check template
        self.assertEqual(replace_local_codeuri(template).get("Resources"), {})
