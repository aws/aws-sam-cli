from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.utils.packagetype import IMAGE, ZIP
from samtranslator.public.exceptions import InvalidDocumentException

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.lib.sam_template_validator import SamTemplateValidator

from samcli.yamlhelper import parse_yaml_file, yaml_parse
from pprint import pformat
from pathlib import Path

import logging

LOG = logging.getLogger(__name__)


class TestSamTemplateValidator(TestCase):
    @patch("samcli.commands.validate.lib.sam_template_validator.Validator")
    @patch("samcli.commands.validate.lib.sam_template_validator.Session")
    @patch("samcli.commands.validate.lib.sam_template_validator.Translator")
    @patch("samcli.commands.validate.lib.sam_template_validator.parser")
    def test_is_valid_returns_true(self, sam_parser, sam_translator, boto_session_patch, validator_mock):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.return_value = {"c": "d"}
        sam_translator.return_value = translate_mock

        validator_mock.return_value.get_errors.return_value = []

        validator = SamTemplateValidator(template, managed_policy_mock, profile="profile", region="region")

        # Should not throw an Exception
        validator.is_valid()

        boto_session_patch.assert_called_once_with(profile_name="profile", region_name="region")
        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )
        translate_mock.translate.assert_called_once_with(sam_template=template, parameter_values={})
        sam_parser.Parser.assert_called_once()
        validator_mock.return_value.get_errors.assert_called_once_with(template)

    @patch("samcli.commands.validate.lib.sam_template_validator.Validator")
    @patch("samcli.commands.validate.lib.sam_template_validator.Session")
    @patch("samcli.commands.validate.lib.sam_template_validator.Translator")
    @patch("samcli.commands.validate.lib.sam_template_validator.parser")
    def test_is_valid_raises_exception_on_validation(
        self, sam_parser, sam_translator, boto_session_patch, validator_mock
    ):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([Exception("message")])
        sam_translator.return_value = translate_mock

        validator_mock.return_value.get_errors.return_value = ["Error message M4RK3R"]

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.is_valid()

        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )
        validator_mock.return_value.get_errors.assert_called_once_with(template)
        boto_session_patch.assert_called_once_with(profile_name=None, region_name=None)
        translate_mock.translate.assert_not_called()
        sam_parser.Parser.assert_called_once()

    @patch("samcli.commands.validate.lib.sam_template_validator.Validator")
    @patch("samcli.commands.validate.lib.sam_template_validator.Session")
    @patch("samcli.commands.validate.lib.sam_template_validator.Translator")
    @patch("samcli.commands.validate.lib.sam_template_validator.parser")
    def test_is_valid_raises_exception_on_translation(
        self, sam_parser, sam_translator, boto_session_patch, validator_mock
    ):
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"policy": "SomePolicy"}
        template = {"a": "b"}

        parser = Mock()
        sam_parser.Parser.return_value = parser

        boto_session_mock = Mock()
        boto_session_patch.return_value = boto_session_mock

        translate_mock = Mock()
        translate_mock.translate.side_effect = InvalidDocumentException([Exception("message")])
        sam_translator.return_value = translate_mock

        validator_mock.return_value.get_errors.return_value = []

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.is_valid()

        sam_translator.assert_called_once_with(
            managed_policy_map={"policy": "SomePolicy"}, sam_parser=parser, plugins=[], boto_session=boto_session_mock
        )
        validator_mock.return_value.get_errors.assert_called_once_with(template)
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

    def test_uri_is_s3_uri(self):
        self.assertTrue(SamTemplateValidator.is_s3_uri("s3://bucket/key"))

    def test_uri_is_not_s3_uri(self):
        self.assertFalse(SamTemplateValidator.is_s3_uri("www.amazon.com"))

    def test_int_is_not_s3_uri(self):
        self.assertFalse(SamTemplateValidator.is_s3_uri(100))

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

    def test_replace_local_codeuri(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"StageName": "Prod", "DefinitionUri": "./"},
                },
                "ServerlessHttpApi": {
                    "Type": "AWS::Serverless::HttpApi",
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

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessApi").get("Properties").get("DefinitionUri"), "s3://bucket/value"
        )
        self.assertEqual(
            template_resources.get("ServerlessHttpApi").get("Properties").get("DefinitionUri"), "s3://bucket/value"
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
                "ServerlessHttpApi": {"Type": "AWS::Serverless::HttpApi", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "Runtime": "nodejs6.10", "Timeout": 60},
                },
                "ServerlessStateMachine": {
                    "Type": "AWS::Serverless::StateMachine",
                    "Properties": {"Role": "test-role-arn"},
                },
            },
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("CodeUri"), "s3://bucket/value"
        )
        self.assertEqual(template_resources.get("ServerlessApi").get("Properties").get("DefinitionUri", ""), "")
        self.assertEqual(template_resources.get("ServerlessHttpApi").get("Properties").get("DefinitionUri", ""), "")
        self.assertEqual(
            template_resources.get("ServerlessStateMachine").get("Properties").get("DefinitionUri", ""), ""
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

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
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

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
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
                },
                "Api": {
                    "Cors": "true",
                },
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

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunctionImage").get("Properties").get("CodeUri", "NotPresent"),
            "NotPresent",
        )
        # Globals not set since they cant apply to both Zip and Image based packagetypes.
        self.assertEqual(
            template_resources.get("ServerlessFunctionZip").get("Properties").get("CodeUri"), "s3://bucket/value"
        )

    def test_replace_local_codeuri_in_global_section(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Globals": {
                "Function": {
                    "CodeUri": "./my.zip",
                },
            },
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": ZIP, "Timeout": 60},
                },
            },
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        global_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            global_resources.get("ServerlessFunction").get("Properties").get("CodeUri"), "s3://bucket/value"
        )

    def test_replace_local_image_gets_replaced(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Metadata": {"Dockerfile": "./Dockerfile"},
                    "Properties": {"PackageType": IMAGE, "Timeout": 60},
                },
            },
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_image()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("ImageUri"),
            "111111111111.dkr.ecr.region.amazonaws.com/repository",
        )

    def test_replace_local_image_doesnt_get_replaced_if_exists(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {"Type": "AWS::Serverless::Api", "Properties": {"StageName": "Prod"}},
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Metadata": {"Dockerfile": "./Dockerfile"},
                    "Properties": {
                        "PackageType": IMAGE,
                        "ImageUri": "222222222222.dkr.ecr.region.amazonaws.com/repository",
                        "Timeout": 60,
                    },
                },
            },
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_image()

        # check template
        template_resources = validator.sam_template.get("Resources")
        self.assertEqual(
            template_resources.get("ServerlessFunction").get("Properties").get("ImageUri"),
            "222222222222.dkr.ecr.region.amazonaws.com/repository",
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

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        template_resources = validator.sam_template.get("Resources")
        self.assertNotIn("DefinitionUri", template_resources.get("ServerlessApi").get("Properties"))
        self.assertIn("DefinitionBody", template_resources.get("ServerlessApi").get("Properties"))

    def test_replace_local_codeuri_with_no_resources(self):

        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {},
        }

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_codeuri()

        # check template
        self.assertEqual(validator.sam_template.get("Resources"), {})

    @patch("pathlib.Path.is_file")
    @patch("samcli.commands.validate.lib.sam_template_validator.parse_yaml_file")
    def test_DefinitionBody_gets_replaced_in_api(self, yaml_mock, path_mock):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": {
                            "Fn::Transform": {
                                "Name": "AWS::Include",
                                "Parameters": {"Location": "./tests/unit/commands/validate/lib/openapi/openapi.yaml"},
                            }
                        },
                    },
                },
            },
        }
        openapi_yaml = """openapi: 3.0.0
info:
    version: "1.0.0"
    title: title
paths:
    '/test':
        get:
            responses:
                200:
                    description: description"""

        # mock file access
        path_mock.return_value = True
        yaml_mock.return_value = yaml_parse(openapi_yaml)

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_openapi()

        template_resources = validator.sam_template.get("Resources")
        self.assertIn("DefinitionBody", template_resources.get("ServerlessApi").get("Properties"))
        self.assertNotIn(
            "Fn::Transform", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody")
        )
        self.assertIn("openapi", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertIn("info", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertIn("paths", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))

    @patch("pathlib.Path.is_file")
    def test_DefinitionBody_not_replaced_if_file_not_found(self, path_mock):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::HttpApi",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": {
                            "Fn::Transform": {
                                "Name": "AWS::Include",
                                "Parameters": {"Location": "./tests/unit/commands/validate/lib/openapi/notafile.yaml"},
                            }
                        },
                    },
                }
            },
        }

        # mock file access
        path_mock.return_value = False

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_openapi()

        template_resources = validator.sam_template.get("Resources")
        self.assertIn("DefinitionBody", template_resources.get("ServerlessApi").get("Properties"))
        self.assertIn("Fn::Transform", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertNotIn("openapi", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertNotIn("info", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertNotIn("paths", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))

    @patch("pathlib.Path.is_file")
    @patch("samcli.commands.validate.lib.sam_template_validator.parse_yaml_file")
    def test_DefinitionBody_gets_replaced_if_json(self, yaml_mock, path_mock):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::HttpApi",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": {
                            "Fn::Transform": {
                                "Name": "AWS::Include",
                                "Parameters": {"Location": "./tests/unit/commands/validate/lib/openapi/openapi.json"},
                            }
                        },
                    },
                }
            },
        }
        openapi_json = {
            "openapi": "3.0.0",
            "info": {"version": "1.0.0", "title": "title"},
            "paths": {"/test": {"get": {"responses": {"200": {"description": "description"}}}}},
        }

        # mock file access
        path_mock.return_value = True
        yaml_mock.return_value = openapi_json

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_openapi()

        template_resources = validator.sam_template.get("Resources")
        self.assertIn("DefinitionBody", template_resources.get("ServerlessApi").get("Properties"))
        self.assertNotIn(
            "Fn::Transform", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody")
        )
        self.assertIn("openapi", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertIn("info", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertIn("paths", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))

    @patch("pathlib.Path.is_file")
    @patch("samcli.commands.validate.lib.sam_template_validator.parse_yaml_file")
    def test_DefinitionBody_not_replaced_if_not_include(self, yaml_mock, path_mock):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::HttpApi",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": {
                            "Fn::Transform": {
                                "Name": "AWS::NotInclude",
                            }
                        },
                    },
                }
            },
        }
        openapi_json = {
            "openapi": "3.0.0",
            "info": {"version": "1.0.0", "title": "title"},
            "paths": {"/test": {"get": {"responses": {"200": {"description": "description"}}}}},
        }

        # mock file access
        path_mock.return_value = True
        yaml_mock.side_effect = openapi_json

        managed_policy_mock = Mock()

        validator = SamTemplateValidator(template, managed_policy_mock)

        validator._replace_local_openapi()

        template_resources = validator.sam_template.get("Resources")
        self.assertIn("DefinitionBody", template_resources.get("ServerlessApi").get("Properties"))
        self.assertNotIn("openapi", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
        self.assertIn("Fn::Transform", template_resources.get("ServerlessApi").get("Properties").get("DefinitionBody"))
