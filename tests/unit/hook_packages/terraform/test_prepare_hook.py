"""Test Terraform prepare hook"""
from subprocess import CalledProcessError
from unittest import TestCase
from unittest.mock import Mock, call, patch, MagicMock
import copy
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare import (
    AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING,
    AWS_PROVIDER_NAME,
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
    _check_image_config_value,
    NULL_RESOURCE_PROVIDER_NAME,
    SamMetadataResource,
    _validate_referenced_resource_matches_sam_metadata_type,
    _get_lambda_function_source_code_path,
    _enrich_mapped_resources,
    _get_relevant_cfn_resource,
)
from samcli.lib.hook.exceptions import PrepareHookException, InvalidSamMetadataPropertiesException
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)


class TestPrepareHook(TestCase):
    def setUp(self) -> None:
        self.output_dir = "/output/dir"
        self.project_root = "/project/root"

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
        self.tf_zip_function_sam_metadata_properties: dict = {
            "triggers": {
                "built_output_path": "builds/func.zip",
                "original_source_code": "./src/lambda_func",
                "resource_name": f"aws_lambda_function.{self.zip_function_name}",
                "resource_type": "ZIP_LAMBDA_FUNCTION",
            },
        }
        self.expected_cfn_zip_function_properties: dict = {
            **self.expected_cfn_function_common_properties,
            "Code": "file.zip",
        }

        self.tf_image_package_type_function_properties: dict = {
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
        self.tf_image_package_type_function_sam_metadata_properties: dict = {
            "triggers": {
                "resource_name": f"aws_lambda_function.{self.image_function_name}",
                "docker_build_args": '{"FOO":"bar"}',
                "docker_context": "context",
                "docker_file": "Dockerfile",
                "docker_tag": "2.0",
                "resource_type": "IMAGE_LAMBDA_FUNCTION",
            },
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
        self.tf_zip_function_sam_metadata_properties_2: dict = {
            "triggers": {
                "built_output_path": "builds/func2.zip",
                "original_source_code": "./src/lambda_func2",
                "resource_name": f"aws_lambda_function.{self.zip_function_name_2}",
                "resource_type": "ZIP_LAMBDA_FUNCTION",
            },
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
        self.tf_zip_function_sam_metadata_properties_3: dict = {
            "triggers": {
                "built_output_path": "builds/func3.zip",
                "original_source_code": "./src/lambda_func3",
                "resource_name": f"aws_lambda_function.{self.zip_function_name_3}",
                "resource_type": "ZIP_LAMBDA_FUNCTION",
            },
        }
        self.expected_cfn_zip_function_properties_3: dict = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": self.zip_function_name_3,
        }
        self.tf_zip_function_properties_4: dict = {
            **self.tf_zip_function_properties_2,
            "function_name": self.zip_function_name_4,
        }
        self.tf_zip_function_sam_metadata_properties_4: dict = {
            "triggers": {
                "built_output_path": "builds/func4.zip",
                "original_source_code": "./src/lambda_func4",
                "resource_name": f"aws_lambda_function.{self.zip_function_name_4}",
                "resource_type": "ZIP_LAMBDA_FUNCTION",
            },
        }
        self.expected_cfn_zip_function_properties_4: dict = {
            **self.expected_cfn_zip_function_properties_2,
            "FunctionName": self.zip_function_name_4,
        }

        self.tf_lambda_function_resource_common_attributes: dict = {
            "type": "aws_lambda_function",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_sam_metadata_resource_common_attributes: dict = {
            "type": "null_resource",
            "provider_name": NULL_RESOURCE_PROVIDER_NAME,
        }

        self.tf_lambda_function_resource_zip: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_zip_function_properties,
            "address": f"aws_lambda_function.{self.zip_function_name}",
            "name": self.zip_function_name,
        }
        self.tf_lambda_function_resource_zip_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_zip_function_sam_metadata_properties,
            "address": f"null_resource.sam_metadata_{self.zip_function_name}",
            "name": f"sam_metadata_{self.zip_function_name}",
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
        self.tf_lambda_function_resource_zip_2_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_zip_function_sam_metadata_properties_2,
            "address": f"null_resource.sam_metadata_{self.zip_function_name_2}",
            "name": f"sam_metadata_{self.zip_function_name_2}",
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
        self.tf_lambda_function_resource_zip_3_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_zip_function_sam_metadata_properties_3,
            "address": f"null_resource.sam_metadata_{self.zip_function_name_3}",
            "name": f"sam_metadata_{self.zip_function_name_3}",
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
        self.tf_lambda_function_resource_zip_4_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_zip_function_sam_metadata_properties_4,
            "address": f"null_resource.sam_metadata_{self.zip_function_name_4}",
            "name": f"sam_metadata_{self.zip_function_name_4}",
        }
        self.expected_cfn_lambda_function_resource_zip_4: dict = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": self.expected_cfn_zip_function_properties_4,
            "Metadata": {"SamResourceId": f"aws_lambda_function.{self.zip_function_name_4}", "SkipBuild": True},
        }

        self.tf_image_package_type_lambda_function_resource: dict = {
            **self.tf_lambda_function_resource_common_attributes,
            "values": self.tf_image_package_type_function_properties,
            "address": f"aws_lambda_function.{self.image_function_name}",
            "name": self.image_function_name,
        }
        self.tf_image_package_type_lambda_function_resource_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_image_package_type_function_sam_metadata_properties,
            "address": f"null_resource.sam_metadata_{self.image_function_name}",
            "name": f"sam_metadata_{self.image_function_name}",
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
            "provider_name": AWS_PROVIDER_NAME,
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

        self.tf_json_with_root_module_with_sam_metadata_resources: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_zip_2,
                        self.tf_image_package_type_lambda_function_resource,
                        self.tf_lambda_function_resource_zip_sam_metadata,
                        self.tf_lambda_function_resource_zip_2_sam_metadata,
                        self.tf_image_package_type_lambda_function_resource_sam_metadata,
                    ]
                }
            }
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
        self.tf_json_with_child_modules_with_sam_metadata_resource: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_zip_sam_metadata,
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    **self.tf_lambda_function_resource_zip_2,
                                    "address": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                                },
                                {
                                    **self.tf_lambda_function_resource_zip_2_sam_metadata,
                                    "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
                                },
                            ],
                            "address": "module.mymodule1",
                            "child_modules": [
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_3,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}",
                                        },
                                        {
                                            **self.tf_lambda_function_resource_zip_3_sam_metadata,
                                            "address": f"module.mymodule1.module.mymodule2.null_resource.sam_metadata_{self.zip_function_name_3}",
                                        },
                                    ],
                                    "address": "module.mymodule1.module.mymodule2",
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": f"module.mymodule1.module.mymodule3.aws_lambda_function.{self.zip_function_name_4}",
                                        },
                                        {
                                            **self.tf_lambda_function_resource_zip_4_sam_metadata,
                                            "address": f"module.mymodule1.module.mymodule3.null_resource.sam_metadata_{self.zip_function_name_4}",
                                        },
                                    ],
                                    "address": "module.mymodule1.module.mymodule3",
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
        translated_cfn_property = _build_lambda_function_code_property(self.tf_image_package_type_function_properties)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property(self):
        expected_cfn_property = self.expected_cfn_image_package_function_properties["ImageConfig"]
        translated_cfn_property = _build_lambda_function_image_config_property(
            self.tf_image_package_type_function_properties
        )
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property_no_image_config(self):
        tf_properties = {**self.tf_image_package_type_function_properties}
        del tf_properties["image_config"]
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties)
        self.assertEqual(translated_cfn_property, None)

    def test_build_lambda_function_image_config_property_empty_image_config_list(self):
        tf_properties = {**self.tf_image_package_type_function_properties}
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
        tf_properties = {**self.tf_image_package_type_function_properties}
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

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    def test_translate_to_cfn_empty(self, mock_enrich_mapped_resources):
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
            translated_cfn_dict = _translate_to_cfn(tf_json, self.output_dir, self.project_root)
            self.assertEqual(translated_cfn_dict, expected_empty_cfn_dict)
            mock_enrich_mapped_resources.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_root_module_only(self, checksum_mock, mock_enrich_mapped_resources):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_root_module_only, self.output_dir, self.project_root)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_root_module_only)
        mock_enrich_mapped_resources.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_child_modules(self, checksum_mock, mock_enrich_mapped_resources):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules, self.output_dir, self.project_root)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules)
        mock_enrich_mapped_resources.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_root_module_with_sam_metadata_resource(
        self, checksum_mock, mock_enrich_mapped_resources
    ):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_root_module_with_sam_metadata_resources, self.output_dir, self.project_root
        )

        mock_enrich_mapped_resources.assert_called_once_with(
            [
                SamMetadataResource(
                    current_module_address=None, resource=self.tf_lambda_function_resource_zip_sam_metadata
                ),
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                ),
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                ),
            ],
            translated_cfn_dict["Resources"],
            self.output_dir,
            self.project_root,
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_child_modules_with_sam_metadata_resource(
        self, checksum_mock, mock_enrich_mapped_resources
    ):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_child_modules_with_sam_metadata_resource, self.output_dir, self.project_root
        )
        mock_enrich_mapped_resources.assert_called_once_with(
            [
                SamMetadataResource(
                    current_module_address=None, resource=self.tf_lambda_function_resource_zip_sam_metadata
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1",
                    resource={
                        **self.tf_lambda_function_resource_zip_2_sam_metadata,
                        "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
                    },
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1.module.mymodule2",
                    resource={
                        **self.tf_lambda_function_resource_zip_3_sam_metadata,
                        "address": f"module.mymodule1.module.mymodule2.null_resource.sam_metadata_{self.zip_function_name_3}",
                    },
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1.module.mymodule3",
                    resource={
                        **self.tf_lambda_function_resource_zip_4_sam_metadata,
                        "address": f"module.mymodule1.module.mymodule3.null_resource.sam_metadata_{self.zip_function_name_4}",
                    },
                ),
            ],
            translated_cfn_dict["Resources"],
            self.output_dir,
            self.project_root,
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_unsupported_provider(self, checksum_mock, mock_enrich_mapped_resources):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_unsupported_provider, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_provider)
        mock_enrich_mapped_resources.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_unsupported_resource_type(self, checksum_mock, mock_enrich_mapped_resources):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_unsupported_resource_type, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_resource_type)
        mock_enrich_mapped_resources.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare._enrich_mapped_resources")
    @patch("samcli.hook_packages.terraform.hooks.prepare.str_checksum")
    def test_translate_to_cfn_with_mapping_s3_source_to_function(self, checksum_mock, mock_enrich_mapped_resources):
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_child_modules_and_s3_source_mapping, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules_and_s3_source_mapping)
        mock_enrich_mapped_resources.assert_not_called()

    @parameterized.expand(
        [
            ("expected_cfn_lambda_function_resource_zip", "tf_lambda_function_resource_zip_sam_metadata", "Zip"),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_image_package_type_lambda_function_resource_sam_metadata",
                "Image",
            ),
        ]
    )
    def test_validate_referenced_resource_matches_sam_metadata_type_valid_types(
        self, cfn_resource_name, sam_metadata_attributes_name, expected_package_type
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        try:
            _validate_referenced_resource_matches_sam_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address", expected_package_type
            )
        except InvalidSamMetadataPropertiesException:
            self.fail("The testing sam metadata resource type should be valid.")

    @parameterized.expand(
        [
            (
                "expected_cfn_lambda_function_resource_zip",
                "tf_image_package_type_lambda_function_resource_sam_metadata",
                "Image",
                "IMAGE_LAMBDA_FUNCTION",
            ),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_lambda_function_resource_zip_sam_metadata",
                "Zip",
                "ZIP_LAMBDA_FUNCTION",
            ),
        ]
    )
    def test_validate_referenced_resource_matches_sam_metadata_type_invalid_types(
        self, cfn_resource_name, sam_metadata_attributes_name, expected_package_type, metadata_source_type
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg=f"The sam metadata resource resource_address is referring to a resource that does not "
            f"match the resource type {metadata_source_type}.",
        ):
            _validate_referenced_resource_matches_sam_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address", expected_package_type
            )

    @parameterized.expand(
        [
            ("/src/code/path", None, "/src/code/path", True),
            ("src/code/path", None, "src/code/path", False),
            ('"/src/code/path"', None, "/src/code/path", True),
            ('"src/code/path"', None, "src/code/path", False),
            ('{"path":"/src/code/path"}', "path", "/src/code/path", True),
            ('{"path":"src/code/path"}', "path", "src/code/path", False),
            ({"path": "/src/code/path"}, "path", "/src/code/path", True),
            ({"path": "src/code/path"}, "path", "src/code/path", False),
            ('["/src/code/path"]', "None", "/src/code/path", True),
            ('["src/code/path"]', "None", "src/code/path", False),
            (["/src/code/path"], "None", "/src/code/path", True),
            (["src/code/path"], "None", "src/code/path", False),
            ('["/src/code/path", "/src/code/path2"]', "None", "/src/code/path", True),
            ('["src/code/path", "src/code/path2"]', "None", "src/code/path", False),
            (["/src/code/path", "/src/code/path2"], "None", "/src/code/path", True),
            (["src/code/path", "/src/code/path2"], "None", "src/code/path", False),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    def test_get_lambda_function_source_code_path_valid_metadata_resource(
        self, original_source_code, source_code_property, expected_path, is_abs, mock_os
    ):
        mock_path = Mock()
        mock_os.path = mock_path
        mock_isabs = Mock()
        mock_isabs.return_value = is_abs
        mock_path.isabs = mock_isabs

        mock_exists = Mock()
        mock_exists.return_value = True
        mock_path.exists = mock_exists

        if not is_abs:
            mock_normpath = Mock()
            mock_normpath.return_value = f"/project/root/dir/{expected_path}"
            expected_path = f"/project/root/dir/{expected_path}"
            mock_path.normpath = mock_normpath
            mock_join = Mock()
            mock_join.return_value = expected_path
            mock_path.join = mock_join
        sam_metadata_attributes = {
            **self.tf_zip_function_sam_metadata_properties,
            "original_source_code": original_source_code,
        }
        if source_code_property:
            sam_metadata_attributes = {
                **sam_metadata_attributes,
                "source_code_property": source_code_property,
            }
        path = _get_lambda_function_source_code_path(
            sam_metadata_attributes,
            "resource_address",
            "/project/root/dir",
            "original_source_code",
            "source_code_property",
            "source code",
        )
        self.assertEquals(path, expected_path)

    @parameterized.expand(
        [
            (
                "/src/code/path",
                None,
                False,
                "The sam metadata resource resource_address should contain a valid lambda function source code path",
            ),
            (
                None,
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code in "
                "property original_source_code",
            ),
            (
                '{"path":"/src/code/path"}',
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code property in "
                "property source_code_property as the original_source_code value is an object",
            ),
            (
                {"path": "/src/code/path"},
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code property "
                "in property source_code_property as the original_source_code value is an object",
            ),
            (
                '{"path":"/src/code/path"}',
                "path1",
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code "
                "property in property source_code_property as the original_source_code value is an object",
            ),
            (
                {"path": "/src/code/path"},
                "path1",
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code "
                "property in property source_code_property as the original_source_code value is an object",
            ),
            (
                "[]",
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function  source code in "
                "property original_source_code, and it should not be an empty list",
            ),
            (
                [],
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function  source code in "
                "property original_source_code, and it should not be an empty list",
            ),
            (
                "[null]",
                None,
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code in "
                "property original_source_code",
            ),
            (
                [None],
                None,
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code in "
                "property original_source_code",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    def test_get_lambda_function_source_code_path_invalid_metadata_resources(
        self, original_source_code, source_code_property, does_exist, exception_message, mock_os
    ):
        mock_path = Mock()
        mock_os.path = mock_path
        mock_isabs = Mock()
        mock_isabs.return_value = True
        mock_path.isabs = mock_isabs

        mock_exists = Mock()
        mock_exists.return_value = does_exist
        mock_path.exists = mock_exists

        sam_metadata_attributes = {
            **self.tf_zip_function_sam_metadata_properties,
            "original_source_code": original_source_code,
        }
        if source_code_property:
            sam_metadata_attributes = {
                **sam_metadata_attributes,
                "source_code_property": source_code_property,
            }
        with self.assertRaises(InvalidSamMetadataPropertiesException, msg=exception_message):
            _get_lambda_function_source_code_path(
                sam_metadata_attributes,
                "resource_address",
                "/project/root/dir",
                "original_source_code",
                "source_code_property",
                "source code",
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare._build_cfn_logical_id")
    def test_get_relevant_cfn_resource(self, mock_build_cfn_logical_id):
        sam_metadata_resource = SamMetadataResource(
            current_module_address="module.mymodule1",
            resource={
                **self.tf_lambda_function_resource_zip_2_sam_metadata,
                "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
            },
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = ["ABCDEFG"]
        relevant_resource, return_logical_id = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources)

        mock_build_cfn_logical_id.assert_called_once_with(
            f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}"
        )
        self.assertEquals(relevant_resource, self.expected_cfn_lambda_function_resource_zip_2)
        self.assertEquals(return_logical_id, "ABCDEFG")

    @parameterized.expand(
        [
            (
                None,
                "module.mymodule1",
                ["ABCDEFG"],
                "sam cli expects the sam metadata resource null_resource.sam_metadata_func2 to contain a resource name "
                "that will be enriched using this metadata resource",
            ),
            (
                "resource_name_value",
                None,
                ["Not_valid"],
                "There is no resource found that match the provided resource name null_resource.sam_metadata_func2",
            ),
            (
                "resource_name_value",
                "module.mymodule1",
                ["Not_valid", "Not_valid"],
                "There is no resource found that match the provided resource name null_resource.sam_metadata_func2",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare._build_cfn_logical_id")
    def test_get_relevant_cfn_resource_exceptions(
        self, resource_name, module_name, build_logical_id_output, exception_message, mock_build_cfn_logical_id
    ):
        sam_metadata_resource = SamMetadataResource(
            current_module_address=module_name,
            resource={
                **self.tf_sam_metadata_resource_common_attributes,
                "values": {
                    "triggers": {
                        "built_output_path": "builds/func2.zip",
                        "original_source_code": "./src/lambda_func2",
                        "resource_name": resource_name,
                        "resource_type": "ZIP_LAMBDA_FUNCTION",
                    },
                },
                "address": "null_resource.sam_metadata_func2",
                "name": "sam_metadata_func2",
            },
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = build_logical_id_output
        with self.assertRaises(InvalidSamMetadataPropertiesException, msg=exception_message):
            _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources)

    @patch("samcli.hook_packages.terraform.hooks.prepare._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare._get_lambda_function_source_code_path")
    def test_enrich_mapped_resources_zip_functions(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }
        zip_function_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file2.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func2", "SkipBuild": True},
        }
        cfn_resources = {
            "logical_id1": zip_function_1,
            "logical_id2": zip_function_2,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            (zip_function_1, "logical_id1"),
            (zip_function_2, "logical_id2"),
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None, resource=self.tf_lambda_function_resource_zip_sam_metadata
            ),
            SamMetadataResource(
                current_module_address=None, resource=self.tf_lambda_function_resource_zip_2_sam_metadata
            ),
        ]

        expected_zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }
        expected_zip_function_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "src/code/path2",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func2",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_zip_function_1,
            "logical_id2": expected_zip_function_2,
        }

        _enrich_mapped_resources(sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root")
        self.assertEquals(cfn_resources, expected_cfn_resources)

    def test_enrich_mapped_resources_invalid_source_type(self):
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        cfn_resources = {
            "logical_id1": image_function_1,
        }
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource={
                    **self.tf_sam_metadata_resource_common_attributes,
                    "values": {
                        "triggers": {
                            "resource_name": f"aws_lambda_function.{self.image_function_name}",
                            "docker_build_args": '{"FOO":"bar"}',
                            "docker_context": "context",
                            "docker_file": "Dockerfile",
                            "docker_tag": "2.0",
                            "resource_type": "Invalid_resource_type",
                        },
                    },
                    "address": f"null_resource.sam_metadata_func1",
                    "name": f"sam_metadata_func1",
                },
            ),
        ]
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg="The resource type Invalid_resource_type found in the sam metadata resource "
            "null_resource.sam_metadata_func1 is not a correct resource type. The resource type should be one of "
            "these values [ZIP_LAMBDA_FUNCTION, IMAGE_LAMBDA_FUNCTION]",
        ):
            _enrich_mapped_resources(sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root")

    @patch("samcli.hook_packages.terraform.hooks.prepare._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.osutils.tempfile_platform_independent")
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

        mock_path = Mock()
        mock_isabs = Mock()
        mock_path.isabs = mock_isabs
        mock_os.path = mock_path
        mock_isabs.return_value = True

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
        mock_translate_to_cfn.assert_called_once_with(
            self.tf_json_with_child_modules_and_s3_source_mapping, output_dir_path, "iac/project/path"
        )
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        mock_update_resources_paths.assert_called_once_with(mock_cfn_dict_resources, "iac/project/path")
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.prepare._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.run")
    def test_prepare_with_relative_paths(
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
        metadata_file_path = f"/current/dir/iac/project/path/{output_dir_path}/template.json"
        mock_cfn_dict = Mock()
        mock_metadata_file = Mock()
        mock_cfn_dict_resources = Mock()
        mock_cfn_dict.get.return_value = mock_cfn_dict_resources

        mock_os.getcwd.return_value = "/current/dir"

        mock_path = Mock()
        mock_isabs = Mock()
        mock_normpath = Mock()
        mock_join = Mock()
        mock_path.isabs = mock_isabs
        mock_path.normpath = mock_normpath
        mock_path.join = mock_join
        mock_os.path = mock_path
        mock_isabs.return_value = False
        mock_join.side_effect = [
            "/current/dir/iac/project/path",
            f"/current/dir/iac/project/path/{output_dir_path}",
            f"/current/dir/iac/project/path/{output_dir_path}/template.json",
        ]
        mock_normpath.side_effect = [
            "/current/dir/iac/project/path",
            f"/current/dir/iac/project/path/{output_dir_path}",
        ]

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
                call(["terraform", "init"], check=True, capture_output=True, cwd="/current/dir/iac/project/path"),
                call(
                    ["terraform", "plan", "-out", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="/current/dir/iac/project/path",
                ),
                call(
                    ["terraform", "show", "-json", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="/current/dir/iac/project/path",
                ),
            ]
        )
        mock_translate_to_cfn.assert_called_once_with(
            self.tf_json_with_child_modules_and_s3_source_mapping,
            f"/current/dir/iac/project/path/{output_dir_path}",
            "/current/dir/iac/project/path",
        )
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        mock_update_resources_paths.assert_called_once_with(mock_cfn_dict_resources, "/current/dir/iac/project/path")
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.prepare.run")
    def test_prepare_with_called_process_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = CalledProcessError(-2, "terraform init")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare._translate_to_cfn")
    @patch("samcli.hook_packages.terraform.hooks.prepare.osutils.tempfile_platform_independent")
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

    def test_check_image_config_value_valid(self):
        image_config = [
            {
                "command": ["cmd1", "cmd2"],
                "entry_point": ["entry1", "entry2"],
                "working_directory": "/working/dir/path",
            }
        ]
        res = _check_image_config_value(image_config)
        self.assertTrue(res)

    def test_check_image_config_value_invalid_type(self):
        image_config = {
            "command": ["cmd1", "cmd2"],
            "entry_point": ["entry1", "entry2"],
            "working_directory": "/working/dir/path",
        }
        expected_message = f"SAM CLI expects that the value of image_config of aws_lambda_function resource in "
        f"the terraform plan output to be of type list instead of {type(image_config)}"
        with self.assertRaises(PrepareHookException, msg=expected_message):
            _check_image_config_value(image_config)

    def test_check_image_config_value_invalid_length(self):
        image_config = [
            {
                "command": ["cmd1", "cmd2"],
                "entry_point": ["entry1", "entry2"],
                "working_directory": "/working/dir/path",
            },
            {
                "command": ["cmd1", "cmd2"],
                "entry_point": ["entry1", "entry2"],
                "working_directory": "/working/dir/path",
            },
        ]
        expected_message = f"SAM CLI expects that there is only one item in the  image_config property of "
        f"aws_lambda_function resource in the terraform plan output, but there are {len(image_config)} items"
        with self.assertRaises(PrepareHookException, msg=expected_message):
            _check_image_config_value(image_config)
