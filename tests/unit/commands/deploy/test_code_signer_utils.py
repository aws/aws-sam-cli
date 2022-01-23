from collections import OrderedDict
from unittest import TestCase

from samcli.commands.deploy.code_signer_utils import (
    extract_profile_name_and_owner_from_existing,
    signer_config_per_function,
)
from samcli.lib.providers.provider import Stack


class TestCodeSignerUtils(TestCase):
    def test_extract_profile_name_and_owner_from_existing(self):
        given_function_name = "MyFunction"
        given_profile_name = "MyProfile"
        given_profile_owner = "MyProfileOwner"
        given_code_signing_config = {
            given_function_name: {"profile_name": given_profile_name, "profile_owner": given_profile_owner}
        }

        (profile_name, profile_owner) = extract_profile_name_and_owner_from_existing(
            given_function_name, given_code_signing_config
        )

        self.assertEqual(profile_name, given_profile_name)
        self.assertEqual(profile_owner, given_profile_owner)

    def test_signer_config_per_function(self):
        function_name_1 = "HelloWorldFunction1"
        function_name_2 = "HelloWorldFunction2"
        layer_name = "HelloWorldFunctionLayer"
        template_dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Description": "\nSample SAM Template for Tests\n",
            "Globals": OrderedDict([("Function", OrderedDict([("Timeout", 3)]))]),
            "Resources": OrderedDict(
                [
                    (
                        function_name_1,
                        OrderedDict(
                            [
                                ("Type", "AWS::Serverless::Function"),
                                (
                                    "Properties",
                                    OrderedDict(
                                        [
                                            ("CodeUri", "HelloWorldFunction"),
                                            ("Handler", "app.lambda_handler"),
                                            ("Runtime", "python3.7"),
                                            ("CodeSigningConfigArn", "MyCodeSigningConfigArn"),
                                            (
                                                "Layers",
                                                [
                                                    OrderedDict([("Ref", layer_name)]),
                                                ],
                                            ),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    ),
                    (
                        function_name_2,
                        OrderedDict(
                            [
                                ("Type", "AWS::Serverless::Function"),
                                (
                                    "Properties",
                                    OrderedDict(
                                        [
                                            ("CodeUri", "HelloWorldFunction2"),
                                            ("Handler", "app.lambda_handler2"),
                                            ("Runtime", "python3.7"),
                                            ("CodeSigningConfigArn", "MyCodeSigningConfigArn"),
                                            (
                                                "Layers",
                                                [
                                                    OrderedDict([("Ref", layer_name)]),
                                                ],
                                            ),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    ),
                    (
                        layer_name,
                        OrderedDict(
                            [
                                ("Type", "AWS::Serverless::LayerVersion"),
                                (
                                    "Properties",
                                    OrderedDict(
                                        [
                                            ("LayerName", "dependencies"),
                                            ("ContentUri", "dependencies/"),
                                            ("CompatibleRuntimes", ["python3.7"]),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    ),
                ]
            ),
        }
        (functions_with_code_sign, layers_with_code_sign) = signer_config_per_function(
            [Stack("", "", "", {}, template_dict)]
        )

        self.assertEqual(functions_with_code_sign, {function_name_1, function_name_2})
        self.assertEqual(layers_with_code_sign, {layer_name: {function_name_1, function_name_2}})
