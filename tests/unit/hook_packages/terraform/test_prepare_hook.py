"""Test Terraform prepare hook"""
from subprocess import CalledProcessError
from unittest import TestCase
from unittest.mock import Mock, call, patch, MagicMock
import copy
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare import (
    AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING,
    PROVIDER_NAME,
    prepare,
    _get_s3_object_hash,
    _build_cfn_logical_id,
    _get_property_extractor,
    _build_lambda_function_environment_property,
    _build_lambda_function_code_property,
    _translate_properties,
    _translate_to_cfn,
    _map_s3_sources_to_functions,
    _update_resources_paths,
    _build_lambda_function_image_config_property,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)


class TestPrepareHook(TestCase):
    def setUp(self) -> None:
        self.mock_logical_id_hash = "12AB34CD"

        self.s3_bucket = "mybucket"
        self.s3_key = "mykey"
        self.s3_source = "mysource1.zip"
        self.s3_bucket_2 = "mybucket2"
        self.s3_key_2 = "mykey2"
        self.s3_source_2 = "mysource2.zip"

        self.zip_function_name = "myfunc"
        self.zip_function_name_2 = "myfunc2"
        self.zip_function_name_3 = "myfunc3"
        self.zip_function_name_4 = "myfunc4"
        self.s3_function_name = "myfuncS3"
        self.s3_function_name_2 = "myfuncS3_2"
        self.image_function_name = "image_func"

        self.tf_function_common_properties: dict = {
            "function_name": self.zip_function_name,
            "architectures": ["x86_64"],
            "environment": [{"variables": {"foo": "bar", "hello": "world"}}],
            "handler": "index.handler",
            "package_type": "Zip",
            "runtime": "python3.7",
            "layers": ["layer_arn1", "layer_arn2"],
            "timeout": 3,
        }
        self.expected_cfn_function_common_properties: dict = {
            "FunctionName": self.zip_function_name,
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
            "Handler": "index.handler",
            "PackageType": "Zip",
            "Runtime": "python3.7",
            "Layers": ["layer_arn1", "layer_arn2"],
            "Timeout": 3,
        }

        self.tf_image_package_type_function_common_properties: dict = {
            "function_name": self.image_function_name,
            "architectures": ["x86_64"],
            "environment": [{"variables": {"foo": "bar", "hello": "world"}}],
            "package_type": "Image",
            "timeout": 3,
        }
        self.expected_cfn_image_package_type_function_common_properties: dict = {
            "FunctionName": self.image_function_name,
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
            "PackageType": "Image",
            "Timeout": 3,
        }

        self.tf_zip_function_properties: dict = {
            **self.tf_function_common_properties,
            "filename": "file.zip",
        }
        self.expected_cfn_zip_function_properties: dict = {
            **self.expected_cfn_function_common_properties,
            "Code": "file.zip",
        }

        self.tf_iamge_package_type_function_properties: dict = {
            **self.tf_image_package_type_function_common_properties,
            "image_config": [
                {
                    "command": ["cmd1", "cmd2"],
                    "entry_point": ["entry1", "entry2"],
                    "working_directory": "/working/dir/path",
                }
            ],
            "image_uri": "image/uri:tag",
        }
        self.expected_cfn_image_package_function_properties: dict = {
            **self.expected_cfn_image_package_type_function_common_properties,
            "ImageConfig": {
                "Command": ["cmd1", "cmd2"],
                "EntryPoint": ["entry1", "entry2"],
                "WorkingDirectory": "/working/dir/path",
            },
            "Code": {
                "ImageUri": "image/uri:tag",
            },
        }

        self.tf_s3_function_properties: dict = {
            **self.tf_function_common_properties,
            "function_name": self.s3_function_name,
            "s3_bucket": self.s3_bucket,
            "s3_key": self.s3_key,
        }
        self.expected_cfn_s3_function_properties: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name,
            "Code": {"S3Bucket": self.s3_bucket, "S3Key": self.s3_key},
        }
        self.expected_cfn_s3_function_properties_after_source_mapping: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name,
            "Code": self.s3_source,
        }

        self.tf_s3_function_properties_2: dict = {
            **self.tf_function_common_properties,
            "function_name": self.s3_function_name_2,
            "s3_bucket": self.s3_bucket_2,
            "s3_key": self.s3_key_2,
        }
        self.expected_cfn_s3_function_properties_2: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name_2,
            "Code": {"S3Bucket": self.s3_bucket_2, "S3Key": self.s3_key_2},
        }
        self.expected_cfn_s3_function_properties_after_source_mapping_2: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name_2,
            "Code": self.s3_source_2,
        }

        self.tf_function_properties_with_missing_or_none: dict = {
            "function_name": self.zip_function_name,
            "filename": "file.zip",
            "environment": None,
            "layers": None,
        }
        self.expected_cfn_function_properties_with_missing_or_none: dict = {
            "FunctionName": self.zip_function_name,
            "Code": "file.zip",
        }

        self.tf_zip_function_properties_2: dict = {
            "function_name": self.zip_function_name_2,
            "architectures": ["x86_64"],
            "environment": [{"variables": {"hi": "there"}}],
            "handler": "index.handler2",
            "package_type": "Zip",
            "runtime": "python3.8",
            "layers": ["layer_arn"],
            "filename": "file2.zip",
        }
        self.expected_cfn_zip_function_properties_2: dict = {
            "FunctionName": self.zip_function_name_2,
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"hi": "there"}},
            "Handler": "index.handler2",
            "PackageType": "Zip",
            "Runtime": "python3.8",
            "Layers": ["layer_arn"],
            "Code": "file2.zip",
        }

        self.tf_zip_function_properties_3: dict = {
            **self.tf_zip_function_properties_2,
            "function_name": self.zip_function_name_3,
        }
        self.expected_cfn_zip_function_properties_3: dict = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": self.zip_function_name_3,
        }
        self.tf_zip_function_properties_4: dict = {
            **self.tf_zip_function_properties_2,
            "function_name": self.zip_function_name_4,
        }
        self.expected_cfn_zip_function_properties_4: dict = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": self.zip_function_name_4,
        }

        self.tf_lambda_function_resource_common_attributes: dict = {
            "type": "aws_lambda_function",
            "provider_name": PROVIDER_NAME,
        }

        self.tf_lambda_function_resource_zip: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties,
            "address": f"aws_lambda_function.{self.zip_function_name}",
            "name": self.zip_function_name,
        }
        self.expected_cfn_lambda_function_resource_zip: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.zip_function_name}", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_2: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_2,
            "address": f"aws_lambda_function.{self.zip_function_name_2}",
            "name": self.zip_function_name_2,
        }
        self.expected_cfn_lambda_function_resource_zip_2: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_2,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.zip_function_name_2}", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_3: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_3,
            "address": f"aws_lambda_function.{self.zip_function_name_3}",
            "name": self.zip_function_name_3,
        }
        self.expected_cfn_lambda_function_resource_zip_3: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_3,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.zip_function_name_3}", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_zip_4: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties_4,
            "address": f"aws_lambda_function.{self.zip_function_name_4}",
            "name": self.zip_function_name_4,
        }
        self.expected_cfn_lambda_function_resource_zip_4: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_4,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.zip_function_name_4}", "SkipBuild": True},
        }

        self.tf_image_package_type_lambda_function_resource: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_iamge_package_type_function_properties,
            "address": f"aws_lambda_function.{self.image_function_name}",
            "name": self.image_function_name,
        }
        self.expected_cfn_image_package_type_lambda_function_resource: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_image_package_function_properties,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.image_function_name}", "SkipBuild": True},
        }

        self.tf_lambda_function_resource_s3: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_s3_function_properties,
            "address": f"aws_lambda_function.{self.s3_function_name}",
            "name": self.s3_function_name,
        }
        self.expected_cfn_lambda_function_resource_s3: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_s3_function_properties,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.s3_function_name}", "SkipBuild": True},
        }
        self.expected_cfn_lambda_function_resource_s3_after_source_mapping: dict = {
            **self.expected_cfn_lambda_function_resource_s3,
            "Properties": self.expected_cfn_s3_function_properties_after_source_mapping,
        }

        self.tf_lambda_function_resource_s3_2: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_s3_function_properties_2,
            "address": f"aws_lambda_function.{self.s3_function_name_2}",
            "name": self.s3_function_name_2,
        }
        self.expected_cfn_lambda_function_resource_s3_2: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_s3_function_properties_2,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.s3_function_name_2}", "SkipBuild": True},
        }
        self.expected_cfn_lambda_function_resource_s3_after_source_mapping_2: dict = {
            **self.expected_cfn_lambda_function_resource_s3_2,
            "Properties": self.expected_cfn_s3_function_properties_after_source_mapping_2,
        }

        self.tf_s3_object_resource_common_attributes: dict = {
            "type": "aws_s3_object",
            "provider_name": PROVIDER_NAME,
        }

        self.tf_s3_object_resource: dict = {
            **self.tf_s3_object_resource_common_attributes,
            "values": {"bucket": self.s3_bucket, "key": self.s3_key, "source": self.s3_source},
            "address": "aws_s3_object.s3_lambda_code",
            "name": "s3_lambda_code",
        }

        self.tf_s3_object_resource_2: dict = {
            **self.tf_s3_object_resource_common_attributes,
            "values": {"bucket": self.s3_bucket_2, "key": self.s3_key_2, "source": self.s3_source_2},
            "address": "aws_s3_object.s3_lambda_code_2",
            "name": "s3_lambda_code_2",
        }

        self.tf_json_with_root_module_only: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_zip_2,
                        self.tf_image_package_type_lambda_function_resource,
                    ]
                }
            }
        }
        self.expected_cfn_with_root_module_only: dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
                f"AwsLambdaFunctionImageFunc{self.mock_logical_id_hash}": self.expected_cfn_image_package_type_lambda_function_resource,
            },
        }

        self.tf_json_with_child_modules: dict = {
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
                                    "address": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                                },
                            ],
                            "child_modules": [
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_3,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}",
                                        },
                                    ],
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            }
        }
        self.expected_cfn_with_child_modules: dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"ModuleMymodule1AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_2,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc3{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_3,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc4{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_4,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                        "SkipBuild": True,
                    },
                },
            },
        }

        self.tf_json_with_unsupported_provider: dict = {
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
        self.expected_cfn_with_unsupported_provider: dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
            },
        }

        self.tf_json_with_unsupported_resource_type: dict = {
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
        self.expected_cfn_with_unsupported_resource_type: dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip_2,
            },
        }

        self.tf_json_with_child_modules_and_s3_source_mapping: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_s3,
                        self.tf_s3_object_resource,
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    **self.tf_lambda_function_resource_zip_2,
                                    "address": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                                },
                                {
                                    **self.tf_s3_object_resource_2,
                                    "address": "module.mymodule1.aws_lambda_function.s3_lambda_code_2",
                                },
                            ],
                            "child_modules": [
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_s3_2,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.s3_function_name_2}",
                                        },
                                    ],
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            }
        }
        self.expected_cfn_with_child_modules_and_s3_source_mapping: dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                f"AwsLambdaFunctionMyfunc{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_zip,
                f"AwsLambdaFunctionMyfuncS3{self.mock_logical_id_hash}": self.expected_cfn_lambda_function_resource_s3_after_source_mapping,
                f"ModuleMymodule1AwsLambdaFunctionMyfunc2{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_2,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfuncS32{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_s3_after_source_mapping_2,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.s3_function_name_2}",
                        "SkipBuild": True,
                    },
                },
                f"ModuleMymodule1ModuleMymodule2AwsLambdaFunctionMyfunc4{self.mock_logical_id_hash}": {
                    **self.expected_cfn_lambda_function_resource_zip_4,
                    "Metadata": {
                        "SamResourceId": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                        "SkipBuild": True,
                    },
                },
            },
        }

        self.prepare_params: dict = {
            "IACProjectPath": "iac/project/path",
            "OutputDirPath": "output/dir/path",
            "Debug": False,
            "Profile": None,
            "Region": None,
        }

    def test_get_s3_object_hash(self):
        self.assertEqual(
            _get_s3_object_hash(self.s3_bucket, self.s3_key), _get_s3_object_hash(self.s3_bucket, self.s3_key)
        )
        self.assertNotEqual(
            _get_s3_object_hash(self.s3_bucket, self.s3_key), _get_s3_object_hash(self.s3_bucket_2, self.s3_key_2)
        )
        self.assertNotEqual(
            _get_s3_object_hash(self.s3_bucket, self.s3_key), _get_s3_object_hash(self.s3_bucket_2, self.s3_key)
        )
        self.assertNotEqual(
            _get_s3_object_hash(self.s3_bucket, self.s3_key), _get_s3_object_hash(self.s3_bucket, self.s3_key_2)
        )

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
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
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
        tf_properties = {"function_name": self.zip_function_name}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties))

        tf_properties = {"environment": [], "function_name": self.zip_function_name}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties))

    def test_build_lambda_function_code_property_zip(self):
        expected_cfn_property = self.expected_cfn_zip_function_properties["Code"]
        translated_cfn_property = _build_lambda_function_code_property(self.tf_zip_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_code_property_s3(self):
        expected_cfn_property = self.expected_cfn_s3_function_properties["Code"]
        translated_cfn_property = _build_lambda_function_code_property(self.tf_s3_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_code_property_image(self):
        expected_cfn_property = self.expected_cfn_image_package_function_properties["Code"]
        translated_cfn_property = _build_lambda_function_code_property(self.tf_iamge_package_type_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property(self):
        expected_cfn_property = self.expected_cfn_image_package_function_properties["ImageConfig"]
        translated_cfn_property = _build_lambda_function_image_config_property(
            self.tf_iamge_package_type_function_properties
        )
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property_no_image_config(self):
        tf_properties = {**self.tf_iamge_package_type_function_properties}
        del tf_properties["image_config"]
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties)
        self.assertEqual(translated_cfn_property, None)

    def test_build_lambda_function_image_config_property_empty_image_config_list(self):
        tf_properties = {**self.tf_iamge_package_type_function_properties}
        tf_properties["image_config"] = []
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties)
        self.assertEqual(translated_cfn_property, None)

    @parameterized.expand(
        [("command", "Command"), ("entry_point", "EntryPoint"), ("working_directory", "WorkingDirectory")]
    )
    def test_build_lambda_function_image_config_property_not_all_properties_exist(
        self, missing_tf_property, missing_cfn_property
    ):
        expected_cfn_property = {**self.expected_cfn_image_package_function_properties["ImageConfig"]}
        del expected_cfn_property[missing_cfn_property]
        tf_properties = {**self.tf_iamge_package_type_function_properties}
        del tf_properties["image_config"][0][missing_tf_property]
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_translate_properties_function(self):
        translated_cfn_properties = _translate_properties(
            self.tf_zip_function_properties, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_zip_function_properties)

    def test_translate_properties_function_with_missing_or_none_properties(self):
        translated_cfn_properties = _translate_properties(
            self.tf_function_properties_with_missing_or_none, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_function_properties_with_missing_or_none)

    @patch("samcli.hook_packages.terraform.hooks.prepare._get_s3_object_hash")
    def test_map_s3_sources_to_functions(self, mock_get_s3_object_hash):
        mock_get_s3_object_hash.side_effect = ["hash1", "hash2"]

        s3_hash_to_source = {"hash1": self.s3_source, "hash2": self.s3_source_2}
        cfn_resources = {
            "s3Function1": copy.deepcopy(self.expected_cfn_lambda_function_resource_s3),
            "s3Function2": copy.deepcopy(self.expected_cfn_lambda_function_resource_s3_2),
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,
        }

        expected_cfn_resources_after_mapping_s3_sources = {
            "s3Function1": self.expected_cfn_lambda_function_resource_s3_after_source_mapping,
            "s3Function2": {
                **self.expected_cfn_lambda_function_resource_s3_2,
                "Properties": {
                    **self.expected_cfn_lambda_function_resource_s3_2["Properties"],
                    "Code": self.s3_source_2,
                },
            },
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,  # should be unchanged
        }
        _map_s3_sources_to_functions(s3_hash_to_source, cfn_resources)

        s3Function1CodeBeforeMapping = self.expected_cfn_lambda_function_resource_s3["Properties"]["Code"]
        s3Function2CodeBeforeMapping = self.expected_cfn_lambda_function_resource_s3_2["Properties"]["Code"]
        mock_get_s3_object_hash.assert_has_calls(
            [
                call(s3Function1CodeBeforeMapping["S3Bucket"], s3Function1CodeBeforeMapping["S3Key"]),
                call(s3Function2CodeBeforeMapping["S3Bucket"], s3Function2CodeBeforeMapping["S3Key"]),
            ]
        )
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_root_module_only(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_root_module_only)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_root_module_only)

    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_child_modules(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules)

    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_unsupported_provider(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_unsupported_provider)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_provider)

    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_unsupported_resource_type(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_unsupported_resource_type)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_resource_type)

    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_mapping_s3_source_to_function(self, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules_and_s3_source_mapping)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules_and_s3_source_mapping)

    @patch("samcli.hook_packages.terraform.hooks.prepare._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.NamedTemporaryFile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.run")
    def test_prepare(
        self,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_open,
        mock_translate_to_cfn,
        mock_update_resources_paths,
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"{output_dir_path}/template.json"
        mock_cfn_dict = Mock()
        mock_metadata_file = Mock()
        mock_cfn_dict_resources = Mock()
        mock_cfn_dict.get.return_value = mock_cfn_dict_resources

        named_temporary_file_mock.return_value.__enter__.return_value.name = tf_plan_filename
        mock_json.loads.return_value = self.tf_json_with_child_modules_and_s3_source_mapping
        mock_translate_to_cfn.return_value = mock_cfn_dict
        mock_os.path.exists.return_value = True
        mock_os.path.join.return_value = metadata_file_path
        mock_open.return_value.__enter__.return_value = mock_metadata_file

        expected_prepare_output_dict = {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}
        iac_prepare_output = prepare(self.prepare_params)

        mock_subprocess_run.assert_has_calls(
            [
                call(["terraform", "init"], check=True, capture_output=True, cwd="iac/project/path"),
                call(
                    ["terraform", "plan", "-out", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="iac/project/path",
                ),
                call(
                    ["terraform", "show", "-json", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="iac/project/path",
                ),
            ]
        )
        mock_translate_to_cfn.assert_called_once_with(self.tf_json_with_child_modules_and_s3_source_mapping)
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        mock_update_resources_paths.assert_called_once_with(mock_cfn_dict_resources, "iac/project/path")
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.prepare.run")
    def test_prepare_with_called_process_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = CalledProcessError(-2, "terraform init")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare._translate_to_cfn")
    @patch("samcli.hook_packages.terraform.hooks.prepare.NamedTemporaryFile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.run")
    def test_prepare_with_os_error(
        self, mock_subprocess_run, mock_json, mock_os, named_temporary_file_mock, mock_translate_to_cfn
    ):
        mock_os.path.exists.return_value = False
        mock_os.mkdir.side_effect = OSError()
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    def test_prepare_with_no_output_dir_path(self):
        with self.assertRaises(PrepareHookException, msg="OutputDirPath was not supplied"):
            prepare({})

    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.Path")
    def test_update_resources_paths(self, mock_path, mock_os):
        abs_path = "/abs/path/value"
        relative_path = "relative/path/value"
        terraform_application_root = "/path/terraform/app/root"

        def side_effect_func(value):
            return value == abs_path

        mock_os.path.isabs = MagicMock(side_effect=side_effect_func)
        updated_relative_path = f"{terraform_application_root}/{relative_path}"
        mock_path_init = Mock()
        mock_path.return_value = mock_path_init
        mock_path_init.joinpath.return_value = updated_relative_path
        resources = {
            "AbsResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": abs_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Resource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "Timeout": 10,
                    "Handler": "app.func",
                },
            },
            "RelativeResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
            "OtherResource1": {
                "Type": "AWS::Lambda::NotFunction",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
        }
        expected_resources = {
            "AbsResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": abs_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Resource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "Timeout": 10,
                    "Handler": "app.func",
                },
            },
            "RelativeResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": updated_relative_path, "Timeout": 10, "Handler": "app.func"},
            },
            "OtherResource1": {
                "Type": "AWS::Lambda::NotFunction",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
        }
        _update_resources_paths(resources, terraform_application_root)
        self.assertDictEqual(resources, expected_resources)
