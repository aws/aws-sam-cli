"""Test Terraform prepare hook"""
from pathlib import Path
from subprocess import CalledProcessError, PIPE
from unittest import TestCase
from unittest.mock import Mock, call, patch, MagicMock, ANY
import copy
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.hook import (
    AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING,
    AWS_PROVIDER_NAME,
    prepare,
    _get_s3_object_hash,
    _get_property_extractor,
    _build_lambda_function_environment_property,
    _build_code_property,
    _translate_properties,
    _translate_to_cfn,
    _map_s3_sources_to_functions,
    _update_resources_paths,
    _build_lambda_function_image_config_property,
    _check_image_config_value,
    NULL_RESOURCE_PROVIDER_NAME,
    SamMetadataResource,
    _validate_referenced_resource_matches_sam_metadata_type,
    _get_source_code_path,
    _get_relevant_cfn_resource,
    _enrich_lambda_layer,
    _enrich_resources_and_generate_makefile,
    _enrich_zip_lambda_function,
    _enrich_image_lambda_function,
    _generate_makefile,
    _get_python_command_name,
    _generate_makefile_rule_for_lambda_resource,
    _get_makefile_build_target,
    _get_parent_modules,
    _build_jpath_string,
    _validate_referenced_resource_layer_matches_metadata_type,
    _format_makefile_recipe,
    _build_makerule_python_command,
    _link_lambda_functions_to_layers,
    _add_child_modules_to_queue,
    _check_dummy_remote_values,
    REMOTE_DUMMY_VALUE,
    _add_metadata_resource_to_metadata_list,
)
from samcli.hook_packages.terraform.hooks.prepare.types import TFModule, TFResource, ConstantValue, ResolvedReference
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidSamMetadataPropertiesException
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_LAMBDA_FUNCTION,
)
from samcli.lib.utils.subprocess_utils import LoadingPatternError


class TestPrepareHook(TestCase):
    def setUp(self) -> None:
        self.output_dir = "/output/dir"
        self.project_root = "/project/root"

        self.mock_logical_id_hash = "12AB34CD"

        self.s3_bucket = "mybucket"
        self.s3_key = "mykey"
        self.s3_object_version = "myversion"
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
        self.lambda_layer_name = "lambda_layer"

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

        self.tf_layer_common_properties: dict = {
            "layer_name": self.lambda_layer_name,
            "compatible_runtimes": ["nodejs14.x", "nodejs16.x"],
            "compatible_architectures": ["arm64"],
        }
        self.expected_cfn_layer_common_properties: dict = {
            "LayerName": self.lambda_layer_name,
            "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
            "CompatibleArchitectures": ["arm64"],
        }

        self.tf_lambda_layer_properties_zip: dict = {
            **self.tf_layer_common_properties,
            "filename": "file.zip",
        }
        self.tf_lambda_layer_properties_s3: dict = {
            **self.tf_layer_common_properties,
            "s3_bucket": "bucket_name",
            "s3_key": "bucket_key",
            "s3_object_version": "1",
        }
        self.tf_lambda_layer_sam_metadata_properties: dict = {
            "triggers": {
                "built_output_path": "builds/func.zip",
                "original_source_code": "./src/lambda_layer",
                "resource_name": f"aws_lambda_layer_version.{self.lambda_layer_name}",
                "resource_type": "LAMBDA_LAYER",
            },
        }
        self.expected_cfn_lambda_layer_properties_zip: dict = {
            **self.expected_cfn_layer_common_properties,
            "Content": "file.zip",
        }
        self.expected_cfn_lambda_layer_properties_s3: dict = {
            **self.expected_cfn_layer_common_properties,
            "Content": {
                "S3Bucket": "bucket_name",
                "S3Key": "bucket_key",
                "S3ObjectVersion": "1",
            },
        }

        self.expected_cfn_layer_resource_s3: dict = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": self.expected_cfn_lambda_layer_properties_s3,
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}", "SkipBuild": True},
        }

        self.expected_cfn_layer_resource_zip: dict = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": self.expected_cfn_lambda_layer_properties_zip,
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}", "SkipBuild": True},
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
            "s3_object_version": self.s3_object_version,
        }
        self.expected_cfn_s3_function_properties: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name,
            "Code": {"S3Bucket": self.s3_bucket, "S3Key": self.s3_key, "S3ObjectVersion": self.s3_object_version},
        }
        self.expected_cfn_s3_function_properties_after_source_mapping: dict = {
            **self.expected_cfn_function_common_properties,
            "FunctionName": self.s3_function_name,
            "Code": self.s3_source,
        }

        self.expected_cfn_s3_layer_properties_after_source_mapping: dict = {
            **self.expected_cfn_layer_common_properties,
            "LayerName": self.lambda_layer_name,
            "Content": self.s3_source,
        }

        self.expected_cfn_s3_layer_resource_after_source_mapping: dict = {
            **self.expected_cfn_layer_resource_s3,
            "Properties": self.expected_cfn_s3_layer_properties_after_source_mapping,
        }

        self.tf_s3_function_properties_2: dict = {
            **self.tf_function_common_properties,
            "function_name": self.s3_function_name_2,
            "s3_bucket": self.s3_bucket_2,
            "s3_key": self.s3_key_2,
            "s3_object_version": self.s3_object_version,
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

        self.tf_lambda_layer_resource_common_attributes: dict = {
            "type": "aws_lambda_layer_version",
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

        self.tf_lambda_layer_resource_zip: dict = {
            **self.tf_lambda_layer_resource_common_attributes,
            "values": self.tf_lambda_layer_properties_zip,
            "address": f"aws_lambda_function.{self.lambda_layer_name}",
            "name": self.lambda_layer_name,
        }
        self.tf_lambda_layer_resource_zip_sam_metadata: dict = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": self.tf_lambda_layer_sam_metadata_properties,
            "address": f"null_resource.sam_metadata_{self.lambda_layer_name}",
            "name": f"sam_metadata_{self.lambda_layer_name}",
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
                                    "address": "module.m1.module.m2",
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                                        },
                                    ],
                                    "address": "module.m1.module.m3",
                                },
                            ],
                            "address": "module.m1",
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
                                    "address": "module.m1.module.m2",
                                },
                                {
                                    "resources": [
                                        {
                                            **self.tf_lambda_function_resource_zip_4,
                                            "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                                        },
                                    ],
                                    "address": "module.m1.module.m2\3",
                                },
                            ],
                            "address": "module.m1",
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
            "SkipPrepareInfra": False,
        }

    def test_get_s3_object_hash(self):
        self.assertEqual(
            _get_s3_object_hash(self.s3_bucket, self.s3_key), _get_s3_object_hash(self.s3_bucket, self.s3_key)
        )
        self.assertEqual(
            _get_s3_object_hash(
                [ConstantValue("A"), ResolvedReference("aws_lambda_function.arn", "module.m1")], self.s3_key
            ),
            _get_s3_object_hash(
                [ResolvedReference("aws_lambda_function.arn", "module.m1"), ConstantValue("A")], self.s3_key
            ),
        )
        self.assertEqual(
            _get_s3_object_hash(
                self.s3_bucket, [ConstantValue("A"), ResolvedReference("aws_lambda_function.arn", "module.m1")]
            ),
            _get_s3_object_hash(
                self.s3_bucket, [ResolvedReference("aws_lambda_function.arn", "module.m1"), ConstantValue("A")]
            ),
        )
        self.assertEqual(
            _get_s3_object_hash(
                [ConstantValue("B"), ResolvedReference("aws_s3_bucket.id", "module.m2")],
                [ConstantValue("A"), ResolvedReference("aws_lambda_function.arn", "module.m1")],
            ),
            _get_s3_object_hash(
                [ResolvedReference("aws_s3_bucket.id", "module.m2"), ConstantValue("B")],
                [ResolvedReference("aws_lambda_function.arn", "module.m1"), ConstantValue("A")],
            ),
        )
        self.assertNotEqual(
            _get_s3_object_hash(
                [ConstantValue("B"), ConstantValue("C"), ResolvedReference("aws_s3_bucket.id", "module.m2")],
                [ConstantValue("A"), ResolvedReference("aws_lambda_function.arn", "module.m1")],
            ),
            _get_s3_object_hash(
                [ResolvedReference("aws_s3_bucket.id", "module.m2"), ConstantValue("B")],
                [ResolvedReference("aws_lambda_function.arn", "module.m1"), ConstantValue("A")],
            ),
        )
        self.assertNotEqual(
            _get_s3_object_hash([ConstantValue("B"), ResolvedReference("aws_s3_bucket.id", "module.m2")], self.s3_key),
            _get_s3_object_hash(
                [ResolvedReference("aws_s3_bucket.id", "module.m2"), ConstantValue("B")], self.s3_key_2
            ),
        )
        self.assertNotEqual(
            _get_s3_object_hash(
                self.s3_bucket, [ConstantValue("A"), ResolvedReference("aws_lambda_function.arn", "module.m1")]
            ),
            _get_s3_object_hash(
                self.s3_bucket_2, [ResolvedReference("aws_lambda_function.arn", "module.m1"), ConstantValue("A")]
            ),
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

    @parameterized.expand(["function_name", "handler"])
    def test_get_property_extractor(self, tf_property_name):
        property_extractor = _get_property_extractor(tf_property_name)
        self.assertEqual(
            property_extractor(self.tf_zip_function_properties, None), self.tf_zip_function_properties[tf_property_name]
        )

    def test_build_lambda_function_environment_property(self):
        expected_cfn_property = self.expected_cfn_zip_function_properties["Environment"]
        translated_cfn_property = _build_lambda_function_environment_property(self.tf_zip_function_properties, None)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_environment_property_no_variables(self):
        tf_properties = {"function_name": self.zip_function_name}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties, None))

        tf_properties = {"environment": [], "function_name": self.zip_function_name}
        self.assertIsNone(_build_lambda_function_environment_property(tf_properties, None))

    def test_build_lambda_function_code_property_zip(self):
        resource_mock = Mock()
        expected_cfn_property = self.expected_cfn_zip_function_properties["Code"]
        translated_cfn_property = _build_code_property(self.tf_zip_function_properties, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._resolve_resource_attribute")
    def test_build_lambda_function_code_property_s3_with_null_bucket_only_in_planned_values(
        self,
        mock_resolve_resource_attribute,
    ):
        resource_mock = Mock()
        reference_mock = Mock()
        mock_resolve_resource_attribute.return_value = reference_mock
        tf_s3_function_properties = {
            **self.tf_function_common_properties,
            "s3_key": "bucket_key",
            "s3_object_version": "1",
        }
        expected_cfn_property = {
            "S3Bucket": REMOTE_DUMMY_VALUE,
            "S3Bucket_config_value": reference_mock,
            "S3Key": "bucket_key",
            "S3ObjectVersion": "1",
        }
        translated_cfn_property = _build_code_property(tf_s3_function_properties, resource_mock)
        self.assertEqual(translated_cfn_property, expected_cfn_property)
        mock_resolve_resource_attribute.assert_has_calls(
            [call(resource_mock, "s3_bucket"), call(resource_mock, "s3_key"), call(resource_mock, "s3_object_version")]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._resolve_resource_attribute")
    def test_build_lambda_function_code_property_with_null_imageuri_only_in_planned_values(
        self,
        mock_resolve_resource_attribute,
    ):
        resource_mock = Mock()
        reference_mock = Mock()
        mock_resolve_resource_attribute.return_value = reference_mock
        tf_image_function_properties = {
            **self.tf_image_package_type_function_common_properties,
            "image_config": [
                {
                    "command": ["cmd1", "cmd2"],
                    "entry_point": ["entry1", "entry2"],
                    "working_directory": "/working/dir/path",
                }
            ],
        }
        expected_cfn_property = {
            "ImageUri": REMOTE_DUMMY_VALUE,
        }
        translated_cfn_property = _build_code_property(tf_image_function_properties, resource_mock)
        self.assertEqual(translated_cfn_property, expected_cfn_property)
        mock_resolve_resource_attribute.assert_has_calls([call(resource_mock, "image_uri")])

    def test_build_lambda_function_code_property_s3(self):
        resource_mock = Mock()
        expected_cfn_property = self.expected_cfn_s3_function_properties["Code"]
        translated_cfn_property = _build_code_property(self.tf_s3_function_properties, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_code_property_image(self):
        expected_cfn_property = self.expected_cfn_image_package_function_properties["Code"]
        resource_mock = Mock()
        translated_cfn_property = _build_code_property(self.tf_image_package_type_function_properties, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property(self):
        expected_cfn_property = self.expected_cfn_image_package_function_properties["ImageConfig"]
        translated_cfn_property = _build_lambda_function_image_config_property(
            self.tf_image_package_type_function_properties, None
        )
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_function_image_config_property_no_image_config(self):
        tf_properties = {**self.tf_image_package_type_function_properties}
        del tf_properties["image_config"]
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties, None)
        self.assertEqual(translated_cfn_property, None)

    def test_build_lambda_function_image_config_property_empty_image_config_list(self):
        tf_properties = {**self.tf_image_package_type_function_properties}
        tf_properties["image_config"] = []
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties, None)
        self.assertEqual(translated_cfn_property, None)

    def test_build_lambda_layer_code_property_zip(self):
        resource_mock = Mock()
        expected_cfn_property = self.expected_cfn_lambda_layer_properties_zip["Content"]
        translated_cfn_property = _build_code_property(self.tf_lambda_layer_properties_zip, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_build_lambda_layer_code_property_s3(self):
        resource_mock = Mock()
        expected_cfn_property = self.expected_cfn_lambda_layer_properties_s3["Content"]
        translated_cfn_property = _build_code_property(self.tf_lambda_layer_properties_s3, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

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
        translated_cfn_property = _build_lambda_function_image_config_property(tf_properties, None)
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    def test_translate_properties_function(self):
        translated_cfn_properties = _translate_properties(
            self.tf_zip_function_properties, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_zip_function_properties)

    def test_translate_properties_function_with_missing_or_none_properties(self):
        translated_cfn_properties = _translate_properties(
            self.tf_function_properties_with_missing_or_none, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_function_properties_with_missing_or_none)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_s3_object_hash")
    def test_map_s3_sources_to_functions(
        self, mock_get_s3_object_hash, mock_calculate_configuration_attribute_value_hash
    ):
        mock_get_s3_object_hash.side_effect = ["hash1", "hash2"]
        mock_calculate_configuration_attribute_value_hash.side_effect = ["code_hash1", "code_hash2"]

        s3_hash_to_source = {"hash1": (self.s3_source, None), "hash2": (self.s3_source_2, None)}
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
        functions_code_map = {}
        expected_functions_code_map = {
            "zip_code_hash1": [(self.expected_cfn_lambda_function_resource_s3_after_source_mapping, "s3Function1")],
            "zip_code_hash2": [
                (
                    {
                        **self.expected_cfn_lambda_function_resource_s3_2,
                        "Properties": {
                            **self.expected_cfn_lambda_function_resource_s3_2["Properties"],
                            "Code": self.s3_source_2,
                        },
                    },
                    "s3Function2",
                )
            ],
        }
        _map_s3_sources_to_functions(s3_hash_to_source, cfn_resources, functions_code_map)

        s3Function1CodeBeforeMapping = self.expected_cfn_lambda_function_resource_s3["Properties"]["Code"]
        s3Function2CodeBeforeMapping = self.expected_cfn_lambda_function_resource_s3_2["Properties"]["Code"]
        mock_get_s3_object_hash.assert_has_calls(
            [
                call(s3Function1CodeBeforeMapping["S3Bucket"], s3Function1CodeBeforeMapping["S3Key"]),
                call(s3Function2CodeBeforeMapping["S3Bucket"], s3Function2CodeBeforeMapping["S3Key"]),
            ]
        )
        mock_calculate_configuration_attribute_value_hash.assert_has_calls(
            [call(self.s3_source), call(self.s3_source_2)]
        )
        self.assertEqual(cfn_resources, expected_cfn_resources_after_mapping_s3_sources)
        self.assertEqual(functions_code_map, expected_functions_code_map)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_s3_object_hash")
    def test_map_s3_sources_to_layers(self, mock_get_s3_object_hash, mock_calculate_configuration_attribute_value_hash):
        mock_get_s3_object_hash.side_effect = ["hash1"]
        mock_calculate_configuration_attribute_value_hash.side_effect = ["code_hash1"]

        s3_hash_to_source = {"hash1": (self.s3_source, None)}
        cfn_resources = {
            "s3Layer": copy.deepcopy(self.expected_cfn_layer_resource_s3),
            "nonS3Layer": self.expected_cfn_layer_resource_zip,
        }

        expected_cfn_resources_after_mapping_s3_sources = {
            "s3Layer": self.expected_cfn_s3_layer_resource_after_source_mapping,
            "nonS3Layer": self.expected_cfn_layer_resource_zip,  # should be unchanged
        }
        layers_code_map = {}
        expected_layers_code_map = {
            "layer_code_hash1": [(self.expected_cfn_s3_layer_resource_after_source_mapping, "s3Layer")],
        }
        _map_s3_sources_to_functions(s3_hash_to_source, cfn_resources, layers_code_map)

        s3LayerCodeBeforeMapping = self.expected_cfn_layer_resource_s3["Properties"]["Content"]
        mock_get_s3_object_hash.assert_has_calls(
            [
                call(s3LayerCodeBeforeMapping["S3Bucket"], s3LayerCodeBeforeMapping["S3Key"]),
            ]
        )
        mock_calculate_configuration_attribute_value_hash.assert_has_calls([call(self.s3_source)])
        self.assertEqual(layers_code_map, expected_layers_code_map)
        self.assertEqual(cfn_resources, expected_cfn_resources_after_mapping_s3_sources)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_s3_object_hash")
    def test_map_s3_sources_to_functions_that_does_not_contain_constant_value_filename(
        self, mock_get_s3_object_hash, mock_calculate_configuration_attribute_value_hash
    ):
        mock_get_s3_object_hash.side_effect = ["hash1"]
        mock_calculate_configuration_attribute_value_hash.side_effect = ["code_hash1"]
        mock_reference = Mock()
        s3_hash_to_source = {"hash1": (None, mock_reference)}
        cfn_resources = {
            "s3Function1": copy.deepcopy(self.expected_cfn_lambda_function_resource_s3),
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,
        }

        expected_cfn_resources_after_mapping_s3_sources = {
            "s3Function1": copy.deepcopy(self.expected_cfn_lambda_function_resource_s3),
            "nonS3Function": self.expected_cfn_lambda_function_resource_zip,  # should be unchanged
        }
        functions_code_map = {}
        expected_functions_code_map = {
            "zip_code_hash1": [(copy.deepcopy(self.expected_cfn_lambda_function_resource_s3), "s3Function1")],
        }
        _map_s3_sources_to_functions(s3_hash_to_source, cfn_resources, functions_code_map)

        s3Function1CodeBeforeMapping = self.expected_cfn_lambda_function_resource_s3["Properties"]["Code"]
        mock_get_s3_object_hash.assert_has_calls(
            [
                call(s3Function1CodeBeforeMapping["S3Bucket"], s3Function1CodeBeforeMapping["S3Key"]),
            ]
        )
        mock_calculate_configuration_attribute_value_hash.assert_has_calls([call(mock_reference)])
        self.assertEqual(cfn_resources, expected_cfn_resources_after_mapping_s3_sources)
        self.assertEqual(functions_code_map, expected_functions_code_map)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    def test_translate_to_cfn_empty(
        self,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
    ):
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
            mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_root_module_only(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        config_resource = Mock()
        resources_mock.__getitem__.return_value = config_resource
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_root_module_only, self.output_dir, self.project_root)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_root_module_only)
        mock_enrich_resources_and_generate_makefile.assert_not_called()
        lambda_functions = dict(
            filter(
                lambda resource: resource[1].get("Type") == "AWS::Lambda::Function",
                translated_cfn_dict.get("Resources").items(),
            )
        )
        expected_arguments_in_call = [
            {mock_get_configuration_address(): config_resource},
            {mock_get_configuration_address(): [val for _, val in lambda_functions.items()]},
            {},
        ]
        mock_link_lambda_functions_to_layers.assert_called_once_with(*expected_arguments_in_call)
        mock_get_configuration_address.assert_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._resolve_resource_attribute")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_s3_object_which_linked_to_uncreated_bucket(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_resolve_resource_attribute,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resource_mock = Mock()
        resources_mock.__getitem__.return_value = resource_mock
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash

        tf_json_with_root_module_contains_s3_object: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        {
                            "type": "aws_s3_object",
                            "provider_name": AWS_PROVIDER_NAME,
                            "values": {"source": self.s3_source},
                            "address": "aws_lambda_function.code_object",
                            "name": "code_object",
                        }
                    ]
                }
            }
        }

        _translate_to_cfn(tf_json_with_root_module_contains_s3_object, self.output_dir, self.project_root)
        mock_resolve_resource_attribute.assert_has_calls([call(resource_mock, "bucket"), call(resource_mock, "key")])

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_child_modules(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        conf_resource = Mock()
        resources_mock.__getitem__.return_value = conf_resource
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(self.tf_json_with_child_modules, self.output_dir, self.project_root)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules)
        mock_enrich_resources_and_generate_makefile.assert_not_called()
        lambda_functions = dict(
            filter(
                lambda resource: resource[1].get("Type") == "AWS::Lambda::Function",
                translated_cfn_dict.get("Resources").items(),
            )
        )
        expected_arguments_in_call = [
            {mock_get_configuration_address(): conf_resource},
            {mock_get_configuration_address(): [val for _, val in lambda_functions.items()]},
            {},
        ]
        mock_link_lambda_functions_to_layers.assert_called_once_with(*expected_arguments_in_call)
        mock_get_configuration_address.assert_called()
        mock_check_dummy_remote_values.assert_called_once_with(translated_cfn_dict.get("Resources"))

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.build_cfn_logical_id")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._add_lambda_resource_code_path_to_code_map")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_root_module_with_sam_metadata_resource(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_add_lambda_resource_code_path_to_code_map,
        mock_build_cfn_logical_id,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resource_mock = Mock()
        resources_mock.__getitem__.return_value = resource_mock
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        mock_build_cfn_logical_id.side_effect = ["logical_id1", "logical_id2", "logical_id3"]
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_root_module_with_sam_metadata_resources, self.output_dir, self.project_root
        )

        expected_arguments_in_call = (
            [
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_lambda_function_resource_zip_sam_metadata,
                    config_resource=resource_mock,
                ),
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                    config_resource=resource_mock,
                ),
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                    config_resource=resource_mock,
                ),
            ],
            translated_cfn_dict["Resources"],
            self.output_dir,
            self.project_root,
            {},
        )

        mock_enrich_resources_and_generate_makefile.assert_called_once_with(*expected_arguments_in_call)
        mock_add_lambda_resource_code_path_to_code_map.assert_has_calls(
            [
                call(
                    resource_mock,
                    "zip",
                    {},
                    "logical_id1",
                    "file.zip",
                    "filename",
                    translated_cfn_dict["Resources"]["logical_id1"],
                ),
                call(
                    resource_mock,
                    "zip",
                    {},
                    "logical_id2",
                    "file2.zip",
                    "filename",
                    translated_cfn_dict["Resources"]["logical_id2"],
                ),
                call(
                    resource_mock,
                    "image",
                    {},
                    "logical_id3",
                    "image/uri:tag",
                    "image_uri",
                    translated_cfn_dict["Resources"]["logical_id3"],
                ),
            ]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._add_lambda_resource_code_path_to_code_map")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_child_modules_with_sam_metadata_resource(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_add_lambda_resource_code_path_to_code_map,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resource_mock = Mock()
        resources_mock.__getitem__.return_value = resource_mock
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_child_modules_with_sam_metadata_resource, self.output_dir, self.project_root
        )

        expected_arguments_in_call = (
            [
                SamMetadataResource(
                    current_module_address=None,
                    resource=self.tf_lambda_function_resource_zip_sam_metadata,
                    config_resource=resource_mock,
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1",
                    resource={
                        **self.tf_lambda_function_resource_zip_2_sam_metadata,
                        "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
                    },
                    config_resource=resource_mock,
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1.module.mymodule2",
                    resource={
                        **self.tf_lambda_function_resource_zip_3_sam_metadata,
                        "address": f"module.mymodule1.module.mymodule2.null_resource.sam_metadata_{self.zip_function_name_3}",
                    },
                    config_resource=resource_mock,
                ),
                SamMetadataResource(
                    current_module_address="module.mymodule1.module.mymodule3",
                    resource={
                        **self.tf_lambda_function_resource_zip_4_sam_metadata,
                        "address": f"module.mymodule1.module.mymodule3.null_resource.sam_metadata_{self.zip_function_name_4}",
                    },
                    config_resource=resource_mock,
                ),
            ],
            translated_cfn_dict["Resources"],
            self.output_dir,
            self.project_root,
            {},
        )

        mock_enrich_resources_and_generate_makefile.assert_called_once_with(*expected_arguments_in_call)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_unsupported_provider(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resources_mock.__getitem__.return_value = Mock()
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_unsupported_provider, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_provider)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_unsupported_resource_type(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resources_mock.__getitem__.return_value = Mock()
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_unsupported_resource_type, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_resource_type)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._add_lambda_resource_code_path_to_code_map")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_mapping_s3_source_to_function(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_add_lambda_resource_code_path_to_code_map,
    ):
        root_module = MagicMock()
        root_module.get.return_value = "module.m1"
        resources_mock = MagicMock()
        root_module.resources = resources_mock
        child_modules = MagicMock()
        child_modules.__getitem__.return_value = Mock()
        child_modules.__contains__.return_value = True
        child_modules.get.return_value = root_module
        root_module.child_modules = child_modules
        resources_mock.__getitem__.return_value = Mock()
        resources_mock.__contains__.return_value = True
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        translated_cfn_dict = _translate_to_cfn(
            self.tf_json_with_child_modules_and_s3_source_mapping, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules_and_s3_source_mapping)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

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

    def test_validate_referenced_layer_resource_matches_sam_metadata_type_valid_types(self):
        cfn_resource = self.expected_cfn_layer_resource_zip
        sam_metadata_attributes = self.tf_lambda_layer_resource_zip_sam_metadata.get("values").get("triggers")
        try:
            _validate_referenced_resource_layer_matches_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address"
            )
        except InvalidSamMetadataPropertiesException:
            self.fail("The testing sam metadata resource type should be valid.")

    @parameterized.expand(
        [
            (
                "expected_cfn_lambda_function_resource_zip",
                "tf_lambda_layer_resource_zip_sam_metadata",
            ),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_lambda_layer_resource_zip_sam_metadata",
            ),
        ]
    )
    def test_validate_referenced_resource_layer_matches_sam_metadata_type_invalid_types(
        self, cfn_resource_name, sam_metadata_attributes_name
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg=f"The sam metadata resource resource_address is referring to a resource that does not "
            f"match the resource type AWS::Lambda::LayerVersion.",
        ):
            _validate_referenced_resource_layer_matches_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address"
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
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
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
        sam_resource = {"values": {"triggers": sam_metadata_attributes}}
        path = _get_source_code_path(
            sam_resource,
            "resource_address",
            "/project/root/dir",
            "original_source_code",
            "source_code_property",
            "source code",
        )
        self.assertEqual(path, expected_path)

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
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
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
            _get_source_code_path(
                sam_metadata_attributes,
                "resource_address",
                "/project/root/dir",
                "original_source_code",
                "source_code_property",
                "source code",
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.build_cfn_logical_id")
    def test_get_relevant_cfn_resource(self, mock_build_cfn_logical_id):
        sam_metadata_resource = SamMetadataResource(
            current_module_address="module.mymodule1",
            resource={
                **self.tf_lambda_function_resource_zip_2_sam_metadata,
                "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
            },
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = ["ABCDEFG"]
        resources_list = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, {})
        self.assertEqual(len(resources_list), 1)
        relevant_resource, return_logical_id = resources_list[0]

        mock_build_cfn_logical_id.assert_called_once_with(
            f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}"
        )
        self.assertEqual(relevant_resource, self.expected_cfn_lambda_function_resource_zip_2)
        self.assertEqual(return_logical_id, "ABCDEFG")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._calculate_configuration_attribute_value_hash")
    def test_get_relevant_cfn_resource_for_metadata_does_not_contain_resource_name(
        self, mock_calculate_configuration_attribute_value_hash
    ):
        sam_metadata_resource = SamMetadataResource(
            current_module_address="module.mymodule1",
            resource={
                "type": "null_resource",
                "provider_name": NULL_RESOURCE_PROVIDER_NAME,
                "values": {
                    "triggers": {
                        "built_output_path": "builds/func2.zip",
                        "original_source_code": "./src/lambda_func2",
                        "resource_type": "ZIP_LAMBDA_FUNCTION",
                    }
                },
                "name": f"sam_metadata_{self.zip_function_name_2}",
                "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
            },
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_calculate_configuration_attribute_value_hash.side_effect = ["code_hash"]
        lambda_resources_code_map = {"zip_code_hash": [(self.expected_cfn_lambda_function_resource_zip_2, "ABCDEFG")]}
        resources_list = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, lambda_resources_code_map)
        self.assertEqual(len(resources_list), 1)
        relevant_resource, return_logical_id = resources_list[0]

        self.assertEqual(relevant_resource, self.expected_cfn_lambda_function_resource_zip_2)
        self.assertEqual(return_logical_id, "ABCDEFG")
        mock_calculate_configuration_attribute_value_hash.assert_has_calls([call("builds/func2.zip")])

    @parameterized.expand(
        [
            (
                None,
                "module.mymodule1",
                ["ABCDEFG"],
                "AWS SAM CLI expects the sam metadata resource null_resource.sam_metadata_func2 to contain a resource name "
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
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.build_cfn_logical_id")
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
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = build_logical_id_output
        with self.assertRaises(InvalidSamMetadataPropertiesException, msg=exception_message):
            _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, {})

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_zip_functions(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

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
            [(zip_function_1, "logical_id1")],
            [(zip_function_2, "logical_id2")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                config_resource=TFResource("", "", None, {}),
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

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(expected_cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_layer_matches_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_layers(
        self,
        mock_get_lambda_layer_source_code_path,
        mock_validate_referenced_resource_layer_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"
        mock_get_lambda_layer_source_code_path.side_effect = ["src/code/path1"]
        lambda_layer = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}", "SkipBuild": True},
        }
        cfn_resources = {
            "logical_id1": lambda_layer,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(lambda_layer, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_layer_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        expected_layer = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_layer,
        }

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(expected_cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_image_lambda_function")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_zip_lambda_function")
    def test_enrich_resources_and_generate_makefile_mock_enrich_zip_functions(
        self,
        mock_enrich_zip_lambda_function,
        mock_enrich_image_lambda_function,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

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
            [(zip_function_1, "logical_id1")],
            [(zip_function_2, "logical_id2")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        mock_enrich_zip_lambda_function.assert_has_calls(
            [
                call(
                    self.tf_lambda_function_resource_zip_sam_metadata,
                    zip_function_1,
                    "logical_id1",
                    "/terraform/project/root",
                    "/output/dir",
                ),
                call(
                    self.tf_lambda_function_resource_zip_2_sam_metadata,
                    zip_function_2,
                    "logical_id2",
                    "/terraform/project/root",
                    "/output/dir",
                ),
            ]
        )
        mock_enrich_image_lambda_function.assert_not_called()

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_mapped_resource_zip_function(
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
        mock_get_relevant_cfn_resource.side_effect = [
            (zip_function_1, "logical_id1"),
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

        _enrich_zip_lambda_function(
            self.tf_lambda_function_resource_zip_sam_metadata,
            zip_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(zip_function_1, expected_zip_function_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_mapped_resource_zip_layer(
        self,
        mock_get_lambda_layer_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_layer_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        lambda_layer_1 = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.lambda_layer", "SkipBuild": True},
        }
        mock_get_relevant_cfn_resource.side_effect = [
            (lambda_layer_1, "logical_id1"),
        ]

        expected_lambda_layer_1 = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_layer_version.lambda_layer",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        _enrich_lambda_layer(
            self.tf_lambda_layer_resource_zip_sam_metadata,
            lambda_layer_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(lambda_layer_1, expected_lambda_layer_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_image_functions(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
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
        mock_get_relevant_cfn_resource.side_effect = [
            [(image_function_1, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        expected_image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "DockerContext": "src/code/path1",
                "Dockerfile": "Dockerfile",
                "DockerTag": "2.0",
                "DockerBuildArgs": {"FOO": "bar"},
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_image_function_1,
        }

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_mapped_resource_image_function(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
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

        mock_get_relevant_cfn_resource.side_effect = [
            (image_function_1, "logical_id1"),
        ]

        expected_image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "DockerContext": "src/code/path1",
                "Dockerfile": "Dockerfile",
                "DockerTag": "2.0",
                "DockerBuildArgs": {"FOO": "bar"},
            },
        }

        _enrich_image_lambda_function(
            self.tf_image_package_type_lambda_function_resource_sam_metadata,
            image_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(image_function_1, expected_image_function_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_image_lambda_function")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._enrich_zip_lambda_function")
    def test_enrich_resources_and_generate_makefile_mock_enrich_image_functions(
        self,
        mock_enrich_zip_lambda_function,
        mock_enrich_image_lambda_function,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
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
        mock_get_relevant_cfn_resource.side_effect = [
            [(image_function_1, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        mock_enrich_image_lambda_function.assert_called_once_with(
            self.tf_image_package_type_lambda_function_resource_sam_metadata,
            image_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        mock_enrich_zip_lambda_function.assert_not_called()

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @parameterized.expand(
        [
            ("ABCDEFG",),
            ('"ABCDEFG"',),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_relevant_cfn_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._validate_referenced_resource_matches_sam_metadata_type")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_source_code_path")
    def test_enrich_mapped_resource_image_function_invalid_docker_args(
        self,
        docker_args_value,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
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

        mock_get_relevant_cfn_resource.side_effect = [
            (image_function_1, "logical_id1"),
        ]
        sam_metadata_resource = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": {
                "triggers": {
                    "resource_name": f"aws_lambda_function.{self.image_function_name}",
                    "docker_build_args": docker_args_value,
                    "docker_context": "context",
                    "docker_file": "Dockerfile",
                    "docker_tag": "2.0",
                    "resource_type": "IMAGE_LAMBDA_FUNCTION",
                },
            },
            "address": f"null_resource.sam_metadata_{self.image_function_name}",
            "name": f"sam_metadata_{self.image_function_name}",
        }

        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg="The sam metadata resource null_resource.sam_metadata_func1 should contain a valid json encoded "
            "string for the lambda function docker build arguments.",
        ):
            _enrich_image_lambda_function(
                sam_metadata_resource, image_function_1, "logical_id1", "/terraform/project/root", "/output/dir"
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_python_command_name")
    def test_enrich_resources_and_generate_makefile_invalid_source_type(
        self,
        mock_get_python_command_name,
    ):
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
                config_resource=TFResource("", "", None, {}),
            ),
        ]
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg="The resource type Invalid_resource_type found in the sam metadata resource "
            "null_resource.sam_metadata_func1 is not a correct resource type. The resource type should be one of "
            "these values [ZIP_LAMBDA_FUNCTION, IMAGE_LAMBDA_FUNCTION]",
        ):
            _enrich_resources_and_generate_makefile(
                sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
            )

    @parameterized.expand(
        [
            (False, False),
            (False, True),
            (True, False),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare(
        self,
        skip_option,
        path_exists,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_open,
        mock_translate_to_cfn,
        mock_update_resources_paths,
        mock_subprocess_loader,
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"{output_dir_path}/template.json"
        mock_cfn_dict = MagicMock()
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
        mock_os.path.exists.side_effect = [path_exists, True]
        mock_os.path.join.return_value = metadata_file_path
        mock_open.return_value.__enter__.return_value = mock_metadata_file

        self.prepare_params["SkipPrepareInfra"] = skip_option

        expected_prepare_output_dict = {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}
        iac_prepare_output = prepare(self.prepare_params)

        mock_subprocess_loader.assert_has_calls(
            [
                call(
                    command_args={
                        "args": ["terraform", "init", "-input=false"],
                        "cwd": "iac/project/path",
                    }
                ),
                call(
                    command_args={
                        "args": ["terraform", "plan", "-out", tf_plan_filename, "-input=false"],
                        "cwd": "iac/project/path",
                    }
                ),
            ]
        )
        mock_subprocess_run.assert_has_calls(
            [
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_relative_paths(
        self,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_open,
        mock_translate_to_cfn,
        mock_update_resources_paths,
        mock_subprocess_loader,
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"/current/dir/iac/project/path/{output_dir_path}/template.json"
        mock_cfn_dict = MagicMock()
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

        mock_subprocess_loader.assert_has_calls(
            [
                call(
                    command_args={
                        "args": ["terraform", "init", "-input=false"],
                        "cwd": "/current/dir/iac/project/path",
                    }
                ),
                call(
                    command_args={
                        "args": ["terraform", "plan", "-out", tf_plan_filename, "-input=false"],
                        "cwd": "/current/dir/iac/project/path",
                    }
                ),
            ]
        )
        mock_subprocess_run.assert_has_calls(
            [
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_called_process_error(self, mock_subprocess_run, mock_subprocess_loader):
        mock_subprocess_run.side_effect = CalledProcessError(-2, "terraform init")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_loader_error(self, mock_subprocess_run, mock_subprocess_loader):
        mock_subprocess_loader.side_effect = LoadingPatternError("Error occurred calling a subprocess")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._translate_to_cfn")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_os_error(
        self,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_translate_to_cfn,
        mock_subprocess_loader,
    ):
        mock_os.path.exists.return_value = False
        mock_os.makedirs.side_effect = OSError()
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    def test_prepare_with_no_output_dir_path(self):
        with self.assertRaises(PrepareHookException, msg="OutputDirPath was not supplied"):
            prepare({})

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.Path")
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
            "S3Layer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "LayerRelativePath": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": relative_path,
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
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
            "S3Layer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "LayerRelativePath": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": updated_relative_path,
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
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
        expected_message = f"AWS SAM CLI expects that the value of image_config of aws_lambda_function resource in "
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
        expected_message = f"AWS SAM CLI expects that there is only one item in the  image_config property of "
        f"aws_lambda_function resource in the terraform plan output, but there are {len(image_config)} items"
        with self.assertRaises(PrepareHookException, msg=expected_message):
            _check_image_config_value(image_config)

    @parameterized.expand([(True,), (False,)])
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.shutil")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    def test_generate_makefile(
        self,
        output_dir_exists,
        mock_os,
        mock_shutil,
        mock_open,
    ):
        mock_os.path.exists.return_value = output_dir_exists

        mock_copy_tf_backend_override_file_path = Mock()
        mock_copy_terraform_built_artifacts_script_path = Mock()
        mock_makefile_path = Mock()
        mock_os.path.dirname.return_value = ""
        mock_os.path.join.side_effect = [
            mock_copy_tf_backend_override_file_path,
            mock_copy_terraform_built_artifacts_script_path,
            mock_makefile_path,
        ]

        mock_makefile = Mock()
        mock_open.return_value.__enter__.return_value = mock_makefile

        mock_makefile_rules = Mock()
        mock_output_directory_path = Mock()

        _generate_makefile(mock_makefile_rules, mock_output_directory_path)

        if output_dir_exists:
            mock_os.makedirs.assert_not_called()
        else:
            mock_os.makedirs.assert_called_once_with(mock_output_directory_path, exist_ok=True)

        mock_shutil.copy.assert_called_once_with(
            mock_copy_terraform_built_artifacts_script_path, mock_output_directory_path
        )

        mock_makefile.writelines.assert_called_once_with(mock_makefile_rules)

    @parameterized.expand(
        [
            ([CalledProcessError(-2, "python3 --version"), Mock(stdout="Python 3.8.10")], "py3"),
            ([Mock(stdout="Python 3.7.12"), CalledProcessError(-2, "py3 --version")], "python3"),
            ([Mock(stdout="Python 3.7")], "python3"),
            ([Mock(stdout="Python 3.7.0")], "python3"),
            ([Mock(stdout="Python 3.7.12")], "python3"),
            ([Mock(stdout="Python 3.8")], "python3"),
            ([Mock(stdout="Python 3.8.0")], "python3"),
            ([Mock(stdout="Python 3.8.12")], "python3"),
            ([Mock(stdout="Python 3.9")], "python3"),
            ([Mock(stdout="Python 3.9.0")], "python3"),
            ([Mock(stdout="Python 3.9.12")], "python3"),
            ([Mock(stdout="Python 3.10")], "python3"),
            ([Mock(stdout="Python 3.10.0")], "python3"),
            ([Mock(stdout="Python 3.10.12")], "python3"),
            (
                [
                    Mock(stdout="Python 3.6.10"),
                    Mock(stdout="Python 3.0.10"),
                    Mock(stdout="Python 2.7.10"),
                    Mock(stdout="Python 3.7.12"),
                ],
                "py",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_get_python_command_name(self, mock_run_side_effect, expected_python_command, mock_subprocess_run):
        mock_subprocess_run.side_effect = mock_run_side_effect

        python_command = _get_python_command_name()
        self.assertEqual(python_command, expected_python_command)

    @parameterized.expand(
        [
            (
                [
                    CalledProcessError(-2, "python3 --version"),
                    CalledProcessError(-2, "py3 --version"),
                    CalledProcessError(-2, "python --version"),
                    CalledProcessError(-2, "py --version"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 3"),
                    Mock(stdout="Python 3.0"),
                    Mock(stdout="Python 3.0.10"),
                    Mock(stdout="Python 3.6"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 3.6.10"),
                    Mock(stdout="Python 2"),
                    Mock(stdout="Python 2.7"),
                    Mock(stdout="Python 2.7.10"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 4"),
                    Mock(stdout="Python 4.7"),
                    Mock(stdout="Python 4.7.10"),
                    Mock(stdout="Python 4.7.10"),
                ],
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_get_python_command_name_python_not_found(self, mock_run_side_effect, mock_subprocess_run):
        mock_subprocess_run.side_effect = mock_run_side_effect

        expected_error_msg = "Python not found. Please ensure that python 3.7 or above is installed."
        with self.assertRaises(PrepareHookException, msg=expected_error_msg):
            _get_python_command_name()

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_makefile_build_target")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._format_makefile_recipe")
    def test_generate_makefile_rule_for_lambda_resource(self, format_recipe_mock, get_build_target_mock):
        format_recipe_mock.side_effect = [
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py --expression "
            '"|values|root_module|resources|[?address=="null_resource.sam_metadata_aws_lambda_function"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            '--target "null_resource.sam_metadata_aws_lambda_function"\n',
        ]
        get_build_target_mock.return_value = "build-function_logical_id:\n"
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None,
            resource={"address": "null_resource.sam_metadata_aws_lambda_function"},
            config_resource=TFResource("", "", None, {}),
        )
        makefile_rule = _generate_makefile_rule_for_lambda_resource(
            python_command_name="python",
            output_dir="/some/dir/path/.aws-sam/output",
            sam_metadata_resource=sam_metadata_resource,
            terraform_application_dir="/some/dir/path",
            logical_id="function_logical_id",
        )
        expected_makefile_rule = (
            "build-function_logical_id:\n"
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py "
            '--expression "|values|root_module|resources|[?address=="null_resource.sam_metadata_aws_lambda_function"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            '--target "null_resource.sam_metadata_aws_lambda_function"\n'
        )
        self.assertEqual(makefile_rule, expected_makefile_rule)

    @parameterized.expand(
        [
            "null_resource.sam_metadata_aws_lambda_function",
            "null_resource.sam_metadata_aws_lambda_function[2]",
            'null_resource.sam_metadata_aws_lambda_layer_version_layers["layer3"]',
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._build_jpath_string")
    def test_build_makerule_python_command(self, resource, jpath_string_mock):
        jpath_string_mock.return_value = (
            "|values|root_module|resources|" f'[?address=="{resource}"]' "|values|triggers|built_output_path"
        )
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None, resource={}, config_resource=TFResource("", "", None, {})
        )
        show_command = _build_makerule_python_command(
            python_command_name="python",
            output_dir="/some/dir/path/.aws-sam/output",
            resource_address=resource,
            sam_metadata_resource=sam_metadata_resource,
            terraform_application_dir="/some/dir/path",
        )
        script_path = ".aws-sam/output/copy_terraform_built_artifacts.py"
        escaped_resource = resource.replace('"', '\\"')
        expected_show_command = (
            f'python "{script_path}" '
            '--expression "|values|root_module|resources|'
            f'[?address==\\"{escaped_resource}\\"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            f'--target "{escaped_resource}"'
        )
        self.assertEqual(show_command, expected_show_command)

    @parameterized.expand(
        [
            (
                None,
                '|values|root_module|resources|[?address=="null_resource'
                '.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
            (
                "module.level1_lambda",
                "|values|root_module|child_modules|[?address==module.level1_lambda]|resources|"
                '[?address=="null_resource.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
            (
                "module.level1_lambda.module.level2_lambda",
                "|values|root_module|child_modules|[?address==module.level1_lambda]|child_modules|"
                "[?address==module.level1_lambda.module.level2_lambda]|resources|[?address=="
                '"null_resource.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
        ]
    )
    def test_build_jpath_string(self, module_address, expected_jpath):
        sam_metadata_resource = SamMetadataResource(
            current_module_address=module_address, resource={}, config_resource=TFResource("", "", None, {})
        )
        self.assertEqual(
            _build_jpath_string(sam_metadata_resource, "null_resource.sam_metadata_aws_lambda_function"), expected_jpath
        )

    @parameterized.expand(
        [
            (None, []),
            (
                "module.level1_lambda",
                ["module.level1_lambda"],
            ),
            (
                "module.level1_lambda.module.level2_lambda",
                ["module.level1_lambda", "module.level1_lambda.module.level2_lambda"],
            ),
            (
                "module.level1_lambda.module.level2_lambda.module.level3_lambda",
                [
                    "module.level1_lambda",
                    "module.level1_lambda.module.level2_lambda",
                    "module.level1_lambda.module.level2_lambda.module.level3_lambda",
                ],
            ),
        ]
    )
    def test_get_parent_modules(self, module_address, expected_list):
        self.assertEqual(_get_parent_modules(module_address), expected_list)

    def test_get_makefile_build_target(self):
        output_string = _get_makefile_build_target("function_logical_id")
        self.assertRegex(output_string, r"^build-function_logical_id:(\n|\r\n)$")

    def test__format_makefile_recipe(self):
        output_string = _format_makefile_recipe("terraform show -json | python3")
        self.assertRegex(output_string, r"^\tterraform show -json \| python3(\n|\r\n)$")

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._link_lambda_function_to_layer")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._get_configuration_address")
    def test_link_lambda_functions_to_layers(self, mock_get_configuration_address, mock_link_lambda_function_to_layer):
        lambda_funcs_config_resources = {
            "aws_lambda_function.remote_lambda_code": [
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "s3_remote_lambda_function",
                        "Code": {"S3Bucket": "lambda_code_bucket", "S3Key": "remote_lambda_code_key"},
                        "Handler": "app.lambda_handler",
                        "PackageType": "Zip",
                        "Runtime": "python3.8",
                        "Timeout": 3,
                    },
                    "Metadata": {"SamResourceId": "aws_lambda_function.remote_lambda_code", "SkipBuild": True},
                }
            ],
            "aws_lambda_function.root_lambda": [
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "root_lambda",
                        "Code": "HelloWorldFunction.zip",
                        "Handler": "app.lambda_handler",
                        "PackageType": "Zip",
                        "Runtime": "python3.8",
                        "Timeout": 3,
                    },
                    "Metadata": {"SamResourceId": "aws_lambda_function.root_lambda", "SkipBuild": True},
                }
            ],
        }
        terraform_layers_resources = {
            "AwsLambdaLayerVersionLambdaLayer556B22D0": {
                "address": "aws_lambda_layer_version.lambda_layer",
                "mode": "managed",
                "type": "aws_lambda_layer_version",
                "name": "lambda_layer",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "schema_version": 0,
                "values": {
                    "compatible_architectures": ["arm64"],
                    "compatible_runtimes": ["nodejs14.x", "nodejs16.x"],
                    "description": None,
                    "filename": None,
                    "layer_name": "lambda_layer_name",
                    "license_info": None,
                    "s3_bucket": "layer_code_bucket",
                    "s3_key": "s3_lambda_layer_code_key",
                    "s3_object_version": "1",
                    "skip_destroy": False,
                },
                "sensitive_values": {"compatible_architectures": [False], "compatible_runtimes": [False, False]},
            }
        }
        resources = {
            "aws_lambda_function.remote_lambda_code": TFResource(
                "aws_lambda_function.remote_lambda_code", "", None, {}
            ),
            "aws_lambda_function.root_lambda": TFResource("aws_lambda_function.root_lambda", "", None, {}),
        }
        _link_lambda_functions_to_layers(resources, lambda_funcs_config_resources, terraform_layers_resources)
        mock_link_lambda_function_to_layer.assert_has_calls(
            [
                call(
                    resources["aws_lambda_function.remote_lambda_code"],
                    lambda_funcs_config_resources.get("aws_lambda_function.remote_lambda_code"),
                    terraform_layers_resources,
                ),
                call(
                    resources["aws_lambda_function.root_lambda"],
                    lambda_funcs_config_resources.get("aws_lambda_function.root_lambda"),
                    terraform_layers_resources,
                ),
            ]
        )

    def test_add_child_modules_to_queue(self):
        m20_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_3,
                    "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}",
                },
            ],
            "address": "module.m1.module.m2[0]",
        }
        m21_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_4,
                    "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                },
            ],
            "address": "module.m1.module.m2[1]",
        }
        m1_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_2,
                    "address": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                },
            ],
            "child_modules": [
                m20_planned_value_module,
                m21_planned_value_module,
            ],
            "address": "module.m1",
        }
        curr_module = {
            "resources": [
                self.tf_lambda_function_resource_zip,
            ],
            "child_modules": [m1_planned_value_module],
        }
        m2_config_module = TFModule(
            "module.m1.module.m2",
            None,
            {},
            {
                f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}": Mock(),
            },
            {},
            {},
        )
        m1_config_module = TFModule(
            "module.m1",
            None,
            {},
            {
                f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}": Mock(),
            },
            {"m2": m2_config_module},
            {},
        )
        m2_config_module.parent_module = m1_config_module
        curr_config_module = TFModule(
            None,
            None,
            {},
            {
                f"aws_lambda_function.{self.zip_function_name}": Mock(),
            },
            {"m1": m1_config_module},
            {},
        )
        m1_config_module.parent_module = curr_config_module
        modules_queue = []
        _add_child_modules_to_queue(curr_module, curr_config_module, modules_queue)
        self.assertEqual(modules_queue, [(m1_planned_value_module, m1_config_module)])
        modules_queue = []
        _add_child_modules_to_queue(m1_planned_value_module, m1_config_module, modules_queue)
        self.assertEqual(
            modules_queue, [(m20_planned_value_module, m2_config_module), (m21_planned_value_module, m2_config_module)]
        )

    def test_add_child_modules_to_queue_invalid_config(self):
        m20_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_3,
                    "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}",
                },
            ],
            "address": "module.m1.module.m2[0]",
        }
        m21_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_4,
                    "address": f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_4}",
                },
            ],
            "address": "module.m1.module.m2[1]",
        }
        m1_planned_value_module = {
            "resources": [
                {
                    **self.tf_lambda_function_resource_zip_2,
                    "address": f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}",
                },
            ],
            "child_modules": [
                m20_planned_value_module,
                m21_planned_value_module,
            ],
            "address": "module.m1",
        }
        m2_config_module = TFModule(
            "module.m1.module.m2",
            None,
            {},
            {
                f"module.mymodule1.module.mymodule2.aws_lambda_function.{self.zip_function_name_3}": Mock(),
            },
            {},
            {},
        )
        m1_config_module = TFModule(
            "module.m1",
            None,
            {},
            {
                f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}": Mock(),
            },
            {"m3": m2_config_module},
            {},
        )
        m2_config_module.parent_module = m1_config_module
        modules_queue = []
        with self.assertRaises(
            PrepareHookException,
            msg=f"Module module.m1.module.m2[0] exists in terraform planned_value, but does not exist in "
            "terraform configuration",
        ):
            _add_child_modules_to_queue(m1_planned_value_module, m1_config_module, modules_queue)

    def test_check_dummy_remote_values_no_exception(self):
        no_exception = True
        try:
            _check_dummy_remote_values(
                {
                    "func1": {
                        "Properties": {
                            "Code": {
                                "S3bucket": "bucket1",
                                "S3Key": "key1",
                                "S3ObjectVersion": "version",
                            }
                        }
                    },
                    "func2": {
                        "Properties": {
                            "Code": {
                                "ImageUri": "uri",
                            }
                        }
                    },
                }
            )
        except PrepareHookException as e:
            no_exception = False
        self.assertTrue(no_exception)

    def test_check_dummy_remote_values_s3_bucket_remote_issue(self):
        no_exception = True
        with self.assertRaises(
            PrepareHookException,
            msg=f"Lambda resource resource1 is referring to an S3 bucket that is not created yet"
            f", and there is no sam metadata resource set for it to build its code locally",
        ):
            _check_dummy_remote_values(
                {
                    "func1": {
                        "Type": AWS_LAMBDA_FUNCTION,
                        "Properties": {
                            "Code": {
                                "S3Bucket": REMOTE_DUMMY_VALUE,
                                "S3Key": "key1",
                                "S3ObjectVersion": "version",
                            }
                        },
                        "Metadata": {"SamResourceId": "resource1"},
                    },
                    "func2": {
                        "Type": AWS_LAMBDA_FUNCTION,
                        "Properties": {
                            "Code": {
                                "ImageUri": "uri",
                            }
                        },
                    },
                }
            )

    def test_check_dummy_remote_values_for_image_uri(self):
        no_exception = True

        with self.assertRaises(
            PrepareHookException,
            msg=f"Lambda resource resource1 is referring to an image uri "
            "that is not created yet, and there is no sam metadata resource set for it to build its image "
            "locally.",
        ):
            _check_dummy_remote_values(
                {
                    "func1": {
                        "Type": AWS_LAMBDA_FUNCTION,
                        "Properties": {
                            "Code": {
                                "S3Bucket": REMOTE_DUMMY_VALUE,
                                "S3Key": "key1",
                                "S3ObjectVersion": "version",
                            }
                        },
                        "Metadata": {"SamResourceId": "resource1"},
                    },
                    "func2": {
                        "Type": AWS_LAMBDA_FUNCTION,
                        "Properties": {
                            "Code": {
                                "ImageUri": "uri",
                            }
                        },
                    },
                }
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_skip_prepare_infra_with_metadata_file(self, run_mock, os_mock):
        os_path_join = Mock()
        os_mock.path.join = os_path_join
        os_mock.path.exists.return_value = True

        self.prepare_params["SkipPrepareInfra"] = True

        prepare(self.prepare_params)

        run_mock.assert_not_called()

    def test_add_metadata_resource_to_metadata_list(self):
        metadata_resource_mock1 = Mock()
        metadata_resource_mock2 = Mock()
        new_metadata_resource_mock = Mock()
        planned_Value_resource = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": {
                "triggers": {
                    "built_output_path": "builds/func2.zip",
                    "original_source_code": "./src/lambda_func2",
                    "resource_name": "aws_lambda_function.func1",
                    "resource_type": "ZIP_LAMBDA_FUNCTION",
                },
            },
            "address": "null_resource.sam_metadata_func2",
            "name": "sam_metadata_func2",
        }
        metadata_resources_list = [metadata_resource_mock1, metadata_resource_mock2]
        _add_metadata_resource_to_metadata_list(
            new_metadata_resource_mock, planned_Value_resource, metadata_resources_list
        )
        self.assertEqual(
            metadata_resources_list, [metadata_resource_mock1, metadata_resource_mock2, new_metadata_resource_mock]
        )

    def test_add_metadata_resource_without_resource_name_to_metadata_list(self):
        metadata_resource_mock1 = Mock()
        metadata_resource_mock2 = Mock()
        new_metadata_resource_mock = Mock()
        planned_Value_resource = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": {
                "triggers": {
                    "built_output_path": "builds/func2.zip",
                    "original_source_code": "./src/lambda_func2",
                    "resource_type": "ZIP_LAMBDA_FUNCTION",
                },
            },
            "address": "null_resource.sam_metadata_func2",
            "name": "sam_metadata_func2",
        }
        metadata_resources_list = [metadata_resource_mock1, metadata_resource_mock2]
        _add_metadata_resource_to_metadata_list(
            new_metadata_resource_mock, planned_Value_resource, metadata_resources_list
        )
        self.assertEqual(
            metadata_resources_list, [new_metadata_resource_mock, metadata_resource_mock1, metadata_resource_mock2]
        )
