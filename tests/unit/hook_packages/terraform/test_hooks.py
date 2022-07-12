"""Test Terraform Hooks"""
from dataclasses import asdict
from subprocess import CalledProcessError
from unittest import TestCase
from unittest.mock import Mock, call, patch
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks import (
    AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING,
    RESOURCE_TRANSLATOR_MAPPING,
    SUPPORTED_RESOURCE_TYPES,
    PROVIDER_NAME,
    _get_s3_object_hash,
    _build_cfn_logical_id,
    _get_property_extractor,
    _build_lambda_function_environment_property,
    _build_lambda_function_code_property,
    _translate_properties,
    _translate_to_cfn,
    _map_s3_sources_to_functions,
    TerraformHooks,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)


class TestPrepareHook(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.mock_logical_id_hash = "12AB34CD"

        self.tf_function_common_properties = {
            "function_name": "myfunc",
            "architectures": ["x86_64"],
            "environment": {"variables": {"foo": "bar", "hello": "world"}},
            "handler": "index.handler",
            "package_type": "Zip",
            "runtime": "python3.7",
            "layers": ["layer_arn1", "layer_arn2"],
        }
        self.expected_cfn_function_common_properties = {
            "FunctionName": "myfunc",
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
            "Handler": "index.handler",
            "PackageType": "Zip",
            "Runtime": "python3.7",
            "Layers": ["layer_arn1", "layer_arn2"],
        }

        self.tf_zip_function_properties = {
            **self.tf_function_common_properties,
            "filename": "file.zip",
        }
        self.expected_cfn_zip_function_properties = {
            **self.expected_cfn_function_common_properties,
            "Code": {"ZipFile": "file.zip"},
        }

        self.tf_s3_function_properties = {
            **self.tf_function_common_properties,
            "function_name": "myfuncS3",
            "s3_bucket": "mybucket",
            "s3_key": "mykey",
        }
        self.expected_cfn_s3_function_properties = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": "myfuncS3",
            "Code": {"S3Bucket": "mybucket", "S3Key": "mykey"},
        }

        self.tf_function_properties_with_missing_or_none = {
            "function_name": "myfunc",
            "filename": "file.zip",
            "environment": None,
            "layers": None,
        }
        self.expected_cfn_function_properties_with_missing_or_none = {
            "FunctionName": "myfunc",
            "Code": {"ZipFile": "file.zip"},
        }

        self.tf_zip_function_properties_2 = {
            "function_name": "myfunc2",
            "architectures": ["x86_64"],
            "environment": {"variables": {"hi": "there"}},
            "handler": "index.handler2",
            "package_type": "Zip",
            "runtime": "python3.8",
            "layers": ["layer_arn"],
            "filename": "file2.zip",
        }
        self.expected_cfn_zip_function_properties_2 = {
            "FunctionName": "myfunc2",
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"hi": "there"}},
            "Handler": "index.handler2",
            "PackageType": "Zip",
            "Runtime": "python3.8",
            "Layers": ["layer_arn"],
            "Code": {"ZipFile": "file2.zip"},
        }

        self.tf_zip_function_properties_3 = {**self.tf_zip_function_properties_2, "function_name": "myfunc3"}
        self.expected_cfn_zip_function_properties_3 = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": "myfunc3",
        }
        self.tf_zip_function_properties_4 = {**self.tf_zip_function_properties_2, "function_name": "myfunc4"}
        self.expected_cfn_zip_function_properties_4 = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": "myfunc4",
        }

        self.tf_lambda_function_resource_common_attributes = {
            "type": "aws_lambda_function",
            "provider_name": PROVIDER_NAME,
        }

        self.tf_lambda_function_resource_zip = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties,
            "address": "aws_lambda_function.myfunc",
            "name": "myfunc",
        }
        self.expected_cfn_lambda_function_resource_zip = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties,
            "Metadata": {"SamResourceId": "aws_lambda_function.myfunc", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_2 = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_2,
            "address": "aws_lambda_function.myfunc2",
            "name": "myfunc2",
        }
        self.expected_cfn_lambda_function_resource_zip_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_2,
            "Metadata": {"SamResourceId": "aws_lambda_function.myfunc2", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_3 = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_3,
            "address": "aws_lambda_function.myfunc3",
            "name": "myfunc3",
        }
        self.expected_cfn_lambda_function_resource_zip_3 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_3,
            "Metadata": {"SamResourceId": "aws_lambda_function.myfunc3", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_4 = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_4,
            "address": "aws_lambda_function.myfunc4",
            "name": "myfunc4",
        }
        self.expected_cfn_lambda_function_resource_zip_4 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_4,
            "Metadata": {"SamResourceId": "aws_lambda_function.myfunc4", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_s3 = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_s3_function_properties,
            "address": "aws_lambda_function.myfuncS3",
            "name": "myfuncS3",
        }
        self.expected_cfn_lambda_function_resource_s3 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_s3_function_properties,
            "Metadata": {"SamResourceId": "aws_lambda_function.myfuncS3", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_s3_2 = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": {
                **self.tf_s3_function_properties,
                "function_name": "myfuncS3_2",
                "s3_bucket": "mybucket2",
                "s3_key": "mykey2",
            },
            "address": "module.mymodule.aws_lambda_function.myfuncS3_2",
            "name": "myfuncS3_2",
        }
        self.expected_cfn_lambda_function_resource_s3_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "FunctionName": "myfuncS3_2",
                "Code": {"S3Bucket": "mybucket2", "S3Key": "mykey2"},
            },
            "Metadata": {"SamResourceId": "module.mymodule.aws_lambda_function.myfuncS3_2", "SkipBuild": True},
        }

        self.tf_json_with_root_module_only = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_zip_2,
                    ]
                }
            }
        }
        self.expected_cfn_with_root_module_only = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
            },
        }

        self.tf_json_with_child_modules = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    **self.tf_lambda_function_resource_zip_2,
                                    "address": "module.mymodule1.aws_lambda_function.myfunc2",
                                },
                            ],
                            "child_modules": [
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_3,
                                            "address": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc3",
                                        },
                                    ],
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4",
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            }
        }
        self.expected_cfn_with_child_modules = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"ModuleMymodule1AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_2,
                    "Metadata": {"SamResourceId": "module.mymodule1.aws_lambda_function.myfunc2", "SkipBuild": True},
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc3{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_3,
                    "Metadata": {
                        "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc3",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc4{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_4,
                    "Metadata": {
                        "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4",
                        "SkipBuild": True,
                    },
                },
            },
        }

        self.tf_json_with_unsupported_provider = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        {**self.tf_lambda_function_resource_zip, "provider": "some.other.provider"},
                        self.tf_lambda_function_resource_zip_2,
                    ]
                }
            }
        }
        self.expected_cfn_with_unsupported_provider = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
            },
        }

        self.tf_json_with_unsupported_resource_type = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        {**self.tf_lambda_function_resource_zip, "type": "aws_iam_role"},
                        self.tf_lambda_function_resource_zip_2,
                    ]
                }
            }
        }
        self.expected_cfn_with_unsupported_resource_type = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
            },
        }

        self.tf_json_with_child_modules_and_s3_source_mapping = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_s3,
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    **self.tf_lambda_function_resource_zip_2,
                                    "address": "module.mymodule1.aws_lambda_function.myfunc2",
                                },
                            ],
                            "child_modules": [
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_s3_2,
                                            "address": "module.mymodule1.module.mymodule2.aws_lambda_function.myfuncS3_2",
                                        },
                                    ],
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4",
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            }
        }
        self.expected_cfn_with_child_modules_and_s3_source_mapping = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfuncS3{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_s3,
                    "Properties": {
                        **self.expected_cfn_s3_function_properties,
                    },
                },
                f"ModuleMymodule1AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_2,
                    "Metadata": {"SamResourceId": "module.mymodule1.aws_lambda_function.myfunc2", "SkipBuild": True},
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfuncS32{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_s3_2,
                    "Metadata": {
                        "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfuncS3_2",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc4{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_4,
                    "Metadata": {
                        "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4",
                        "SkipBuild": True,
                    },
                },
            },
        }

        self.prepare_params = {
            "IACProjectPath": "iac/project/path",
            "OutputDirPath": "output/dir/path",
            "Debug": False,
            "Profile": None,
            "Region": None,
        }

    def test_get_s3_object_hash(self):
        bucket = "mybucket"
        key = "mykey"

        different_bucket = "bucket123"
        different_key = "key123"

        self.assertEqual(_get_s3_object_hash(bucket, key), _get_s3_object_hash(bucket, key))
        self.assertNotEqual(_get_s3_object_hash(bucket, key), _get_s3_object_hash(different_bucket, different_key))
        self.assertNotEqual(_get_s3_object_hash(bucket, key), _get_s3_object_hash(different_bucket, key))
        self.assertNotEqual(_get_s3_object_hash(bucket, key), _get_s3_object_hash(bucket, different_key))

    @parameterized.expand(
        [
            ("aws_lambda_function.s3_lambda", "AwsLambdaFunctionS3Lambda"),
            ("aws_lambda_function.S3-Lambda", "AwsLambdaFunctionS3Lambda"),
            ("aws_lambda_function.s3Lambda", "AwsLambdaFunctionS3Lambda"),
            (
                "module.lambda1.module.lambda5.aws_iam_role.iam_for_lambda",
                "ModuleLambda1ModuleLambda5AwsIamRoleIamForLambda",
            ),
            (
                # Name too long, logical id human (non-hash) part will be cut to 247 characters max
                "module.lambda1.module.lambda5.aws_iam_role.reallyreallyreallyreallyreallyreallyreallyreally"
                "reallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreally"
                "reallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreally_long_name",
                "ModuleLambda1ModuleLambda5AwsIamRoleReallyreallyreallyreallyreallyreallyreallyreallyreally"
                "reallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreallyreally"
                "reallyreallyreallyreallyreallyreallyreallyreallyreallyreallyr",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_build_cfn_logical_id(self, tf_address, expected_logical_id_human_part, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash

        logical_id = _build_cfn_logical_id(tf_address)
        checksum_mock.assert_called_once_with(tf_address)
        self.assertEqual(logical_id, expected_logical_id_human_part + self.mock_logical_id_hash)

    def test_build_cfn_logical_id_hash(self):
        # these two addresses should end up with the same human part of the logical id but should
        # have different logical IDs overall because of the hash
        tf_address1 = "aws_lambda_function.s3_lambda"
        tf_address2 = "aws_lambda_function.S3-Lambda"

        logical_id1 = _build_cfn_logical_id(tf_address1)
        logical_id2 = _build_cfn_logical_id(tf_address2)
        self.assertNotEqual(logical_id1, logical_id2)

    @parameterized.expand(["function_name", "handler"])
    def test_get_property_extractor(self, tf_property_name):
        property_extractor = _get_property_extractor(tf_property_name)
        self.assertEqual(
            property_extractor(self.tf_zip_function_properties), self.tf_zip_function_properties[tf_property_name]
        )

    def test_build_lambda_function_environment_property(self):
        expected_cfn_property = self.expected_cfn_zip_function_properties["Environment"]
        translated_cfn_property = _build_lambda_function_environment_property(self.tf_zip_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_environment_property_no_variables(self):
        tf_properties = {"function_name": "myfunc"}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties))

        tf_properties = {"environment": [], "function_name": "myfunc"}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties))

    def test_build_lambda_function_code_property_zip(self):
        expected_cfn_property = self.expected_cfn_zip_function_properties["Code"]
        translated_cfn_property = _build_lambda_function_code_property(self.tf_zip_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_code_property_s3(self):
        expected_cfn_property = self.expected_cfn_s3_function_properties["Code"]
        translated_cfn_property = _build_lambda_function_code_property(self.tf_s3_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_translate_resource_zip_function(self):
        translated_cfn_properties = _translate_properties(
            self.tf_zip_function_properties, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_zip_function_properties)

    def test_translate_resource_function_with_missing_or_none_properties(self):
        translated_cfn_properties = _translate_properties(
            self.tf_function_properties_with_missing_or_none, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_function_properties_with_missing_or_none)

    def test_ensure_all_supported_resources_types_are_in_translator_mapping(self):
        for resource_type in SUPPORTED_RESOURCE_TYPES:
            self.assertIsNotNone(RESOURCE_TRANSLATOR_MAPPING.get(resource_type))

    @patch("samcli.hook_packages.terraform.hooks.hashlib")
    def test_map_s3_sources_to_functions(self, mock_hashlib):
        mock_md5 = Mock()
        mock_hashlib.md5.return_value = mock_md5
        mock_md5.hexdigest.side_effect = ["hash1", "hash2"]

        s3_hash_to_source = {"hash1": "source1.zip", "hash2": "source2.zip"}
        cfn_resources = {
            "s3Function1": self.expected_cfn_lambda_function_resource_s3,
            "s3Function2": self.expected_cfn_lambda_function_resource_s3_2,
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,
        }

        expected_cfn_resources_after_mapping_s3_sources = {
            "s3Function1": {
                **self.expected_cfn_lambda_function_resource_s3,
                "Properties": {**self.expected_cfn_s3_function_properties, "Code": {"ZipFile": "source1.zip"}},
            },
            "s3Function2": {
                **self.expected_cfn_lambda_function_resource_s3_2,
                "Properties": {
                    **self.expected_cfn_s3_function_properties,
                    "FunctionName": self.expected_cfn_lambda_function_resource_s3_2["Properties"]["FunctionName"],
                    "Code": {"ZipFile": "source2.zip"},
                },
            },
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,  # should be unchanged
        }
        _map_s3_sources_to_functions(s3_hash_to_source, cfn_resources)

        self.assertEqual(cfn_resources, expected_cfn_resources_after_mapping_s3_sources)

    def test_translate_to_cfn_empty(self):
        expected_empty_cfn_dict = {"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}

        tf_json_empty = {}
        tf_json_empty_planned_values = {"planned_values": {}}
        tf_json_empty_root_module = {"planned_values": {"root_module": {}}}
        tf_json_no_child_modules_and_no_resources = {"planned_values": {"root_module": {"resources": []}}}

        tf_jsons = [
            tf_json_empty,
            tf_json_empty_planned_values,
            tf_json_empty_root_module,
            tf_json_no_child_modules_and_no_resources,
        ]

        for tf_json in tf_jsons:
            translated_cfn_dict = _translate_to_cfn(tf_json)
            self.assertEqual(translated_cfn_dict, expected_empty_cfn_dict)

    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_translate_to_cfn_with_root_module_only(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_root_module_only)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_root_module_only)

    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_translate_to_cfn_with_child_modules(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules)

    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_translate_to_cfn_with_unsupported_provider(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_unsupported_provider)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_provider)

    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_translate_to_cfn_with_unsupported_resource_type(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_unsupported_resource_type)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_resource_type)

    @patch("samcli.hook_packages.terraform.hooks.str_checksum")
    def test_translate_to_cfn_with_mapping_s3_source_to_function(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules_and_s3_source_mapping)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules_and_s3_source_mapping)

    @patch("samcli.hook_packages.terraform.hooks._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.NamedTemporaryFile")
    @patch("samcli.hook_packages.terraform.hooks.os")
    @patch("samcli.hook_packages.terraform.hooks.json")
    @patch("samcli.hook_packages.terraform.hooks.run")
    def test_prepare(
        self, mock_subprocess_run, mock_json, mock_os, named_temporary_file_mock, mock_open, mock_translate_to_cfn
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"{output_dir_path}/template.json"
        mock_cfn_dict = Mock()
        mock_metadata_file = Mock()

        named_temporary_file_mock.return_value.__enter__.return_value.name = tf_plan_filename
        mock_json.loads.return_value = self.tf_json_with_child_modules_and_s3_source_mapping
        mock_translate_to_cfn.return_value = mock_cfn_dict
        mock_os.path.exists.return_value = True
        mock_os.path.join.return_value = metadata_file_path
        mock_open.return_value.__enter__.return_value = mock_metadata_file

        tf_hooks = TerraformHooks()

        expected_prepare_output_dict = {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}
        iac_prepare_output = tf_hooks.prepare(self.prepare_params)

        mock_subprocess_run.assert_has_calls(
            [
                call(["terraform", "init", "-upgrade"], check=True, capture_output=True),
                call(["terraform", "plan", "-out", tf_plan_filename], check=True, capture_output=True),
                call(["terraform", "show", "-json", tf_plan_filename], check=True, capture_output=True),
            ]
        )
        mock_translate_to_cfn.assert_called_once_with(self.tf_json_with_child_modules_and_s3_source_mapping)
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.run")
    def test_prepare_with_called_process_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = CalledProcessError(-2, "terraform init -upgrade")
        tf_hooks = TerraformHooks()
        with self.assertRaises(PrepareHookException):
            tf_hooks.prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks._translate_to_cfn")
    @patch("samcli.hook_packages.terraform.hooks.NamedTemporaryFile")
    @patch("samcli.hook_packages.terraform.hooks.os")
    @patch("samcli.hook_packages.terraform.hooks.json")
    @patch("samcli.hook_packages.terraform.hooks.run")
    def test_prepare_with_os_error(
        self, mock_subprocess_run, mock_json, mock_os, named_temporary_file_mock, mock_translate_to_cfn
    ):
        mock_os.side_effect = OSError
        tf_hooks = TerraformHooks()
        with self.assertRaises(PrepareHookException):
            tf_hooks.prepare(self.prepare_params)
