"""
Unit test base class for Terraform prepare hook
"""
from unittest import TestCase

from samcli.hook_packages.terraform.hooks.prepare.translate import AWS_PROVIDER_NAME, NULL_RESOURCE_PROVIDER_NAME
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_APIGATEWAY_RESOURCE,
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_STAGE,
    AWS_APIGATEWAY_METHOD,
    AWS_APIGATEWAY_AUTHORIZER,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.internal import (
    INTERNAL_API_GATEWAY_INTEGRATION,
    INTERNAL_API_GATEWAY_INTEGRATION_RESPONSE,
)


class PrepareHookUnitBase(TestCase):
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

        self.apigw_resource_name = "my_resource"
        self.apigw_stage_name = "my_stage"
        self.apigw_rest_api_name = "my_rest_api"
        self.apigw_method_name = "my_method"
        self.apigw_method_with_auth_name = "my_method_auth"
        self.apigw_integration_name = "my_integration"
        self.apigw_authorizer_name = "my_authorizer"
        self.apigw_integration_response_name = "my_integration_response"

        self.tf_function_common_properties: dict = {
            "function_name": self.zip_function_name,
            "architectures": ["x86_64"],
            "environment": [{"variables": {"foo": "bar", "hello": "world"}}],
            "handler": "index.handler",
            "package_type": "Zip",
            "runtime": "python3.7",
            "layers": ["layer_arn1", "layer_arn2"],
            "timeout": 3,
            "memory_size": 128,
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
            "MemorySize": 128,
        }

        self.tf_image_package_type_function_common_properties: dict = {
            "function_name": self.image_function_name,
            "architectures": ["x86_64"],
            "environment": [{"variables": {"foo": "bar", "hello": "world"}}],
            "package_type": "Image",
            "timeout": 3,
            "memory_size": 128,
        }
        self.expected_cfn_image_package_type_function_common_properties: dict = {
            "FunctionName": self.image_function_name,
            "Architectures": ["x86_64"],
            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
            "PackageType": "Image",
            "Timeout": 3,
            "MemorySize": 128,
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

        self.tf_apigw_resource_common_attributes: dict = {
            "type": "aws_api_gateway_resource",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_stage_common_attributes: dict = {
            "type": "aws_api_gateway_stage",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_rest_api_common_attributes: dict = {
            "type": "aws_api_gateway_rest_api",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_integration_common_attributes: dict = {
            "type": "aws_api_gateway_integration",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_integration_response_common_attributes: dict = {
            "type": "aws_api_gateway_integration_response",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_method_common_attributes: dict = {
            "type": "aws_api_gateway_method",
            "provider_name": AWS_PROVIDER_NAME,
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

        self.tf_apigw_resource_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "parent_id": "aws_api_gateway_rest_api.MyDemoAPI.root_resource_id",
            "path_part": "mydemoresource",
        }

        self.expected_cfn_apigw_resource_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "ParentId": "aws_api_gateway_rest_api.MyDemoAPI.root_resource_id",
            "PathPart": "mydemoresource",
        }

        self.tf_apigw_resource_resource: dict = {
            **self.tf_apigw_resource_common_attributes,
            "values": self.tf_apigw_resource_properties,
            "address": f"aws_api_gateway_resource.{self.apigw_resource_name}",
            "name": self.apigw_resource_name,
        }

        self.expected_cfn_apigw_resource: dict = {
            "Type": AWS_APIGATEWAY_RESOURCE,
            "Properties": self.expected_cfn_apigw_resource_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_resource.{self.apigw_resource_name}"},
        }

        self.tf_apigw_integration_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "resource_id": "aws_api_gateway_resource.MyResource.id",
            "http_method": "POST",
            "type": "AWS_PROXY",
            "uri": "https://www.google.com",
            "content_handling": "CONVERT_TO_TEXT",
            "connection_type": "INTERNET",
        }

        self.expected_internal_apigw_integration_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "ResourceId": "aws_api_gateway_resource.MyResource.id",
            "HttpMethod": "POST",
            "Type": "AWS_PROXY",
            "Uri": "https://www.google.com",
            "ContentHandling": "CONVERT_TO_TEXT",
            "ConnectionType": "INTERNET",
        }

        self.tf_apigw_integration_resource: dict = {
            **self.tf_apigw_integration_common_attributes,
            "values": self.tf_apigw_integration_properties,
            "address": f"aws_api_gateway_integration.{self.apigw_integration_name}",
            "name": self.apigw_integration_name,
        }

        self.expected_internal_apigw_integration: dict = {
            "Type": INTERNAL_API_GATEWAY_INTEGRATION,
            "Properties": self.expected_internal_apigw_integration_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_integration.{self.apigw_integration_name}"},
        }

        self.tf_apigw_authorizer_common_attributes: dict = {
            "type": "aws_api_gateway_authorizer",
            "provider_name": AWS_PROVIDER_NAME,
        }

        self.tf_apigw_authorizer_properties: dict = {
            "name": self.apigw_authorizer_name,
            "rest_api_id": "aws_api_gateway_rest_api.demo.id",
            "authorizer_uri": "aws_lambda_function.authorizer.invoke_arn",
            "identity_source": "method.request.header.Authorization",
            "type": "TOKEN",
            "identity_validation_expression": "^123$",
        }

        self.expected_cfn_apigw_authorizer_properties: dict = {
            "Name": self.apigw_authorizer_name,
            "RestApiId": "aws_api_gateway_rest_api.demo.id",
            "AuthorizerUri": "aws_lambda_function.authorizer.invoke_arn",
            "IdentitySource": "method.request.header.Authorization",
            "Type": "TOKEN",
            "IdentityValidationExpression": "^123$",
        }

        self.tf_apigw_authorizer_resource: dict = {
            **self.tf_apigw_authorizer_common_attributes,
            "values": self.tf_apigw_authorizer_properties,
            "address": f"aws_api_gateway_authorizer.{self.apigw_authorizer_name}",
            "name": self.apigw_authorizer_name,
        }

        self.expected_cfn_apigw_authorizer: dict = {
            "Type": AWS_APIGATEWAY_AUTHORIZER,
            "Properties": self.expected_cfn_apigw_authorizer_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_authorizer.{self.apigw_authorizer_name}"},
        }

        self.tf_apigw_integration_response_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "resource_id": "aws_api_gateway_resource.MyResource.id",
            "http_method": "POST",
            "status_code": 200,
            "response_parameters": {
                "method.response.header.X-Some-Header": "integration.response.header.X-Some-Other-Header",
                "method.response.body.x-body": "integration.response.body.X-Some-Other-Body",
            },
        }

        self.expected_internal_apigw_integration_response_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "ResourceId": "aws_api_gateway_resource.MyResource.id",
            "HttpMethod": "POST",
            "ResponseParameters": {
                "method.response.header.X-Some-Header": "integration.response.header.X-Some-Other-Header",
                "method.response.body.x-body": "integration.response.body.X-Some-Other-Body",
            },
        }

        self.tf_apigw_integration_response_resource: dict = {
            **self.tf_apigw_integration_response_common_attributes,
            "values": self.tf_apigw_integration_response_properties,
            "address": f"aws_api_gateway_integration.{self.apigw_integration_response_name}",
            "name": self.apigw_integration_response_name,
        }

        self.expected_internal_apigw_integration_response: dict = {
            "Type": INTERNAL_API_GATEWAY_INTEGRATION_RESPONSE,
            "Properties": self.expected_internal_apigw_integration_response_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_integration.{self.apigw_integration_response_name}"},
        }

        self.tf_apigw_method_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "resource_id": "aws_api_gateway_resource.MyDemoResource.id",
            "http_method": "ANY",
            "operation_name": "AnyOperation",
        }

        self.expected_cfn_apigw_method_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "ResourceId": "aws_api_gateway_resource.MyDemoResource.id",
            "HttpMethod": "ANY",
            "OperationName": "AnyOperation",
        }

        self.tf_apigw_method_resource: dict = {
            **self.tf_apigw_method_common_attributes,
            "values": self.tf_apigw_method_properties,
            "address": f"aws_api_gateway_method.{self.apigw_method_name}",
            "name": self.apigw_method_name,
        }

        self.expected_cfn_apigw_method: dict = {
            "Type": AWS_APIGATEWAY_METHOD,
            "Properties": self.expected_cfn_apigw_method_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_method.{self.apigw_method_name}"},
        }

        self.tf_apigw_method_with_auth_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "resource_id": "aws_api_gateway_resource.MyDemoResource.id",
            "http_method": "ANY",
            "operation_name": "AnyOperation",
        }

        self.expected_cfn_apigw_method_with_auth_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "ResourceId": "aws_api_gateway_resource.MyDemoResource.id",
            "HttpMethod": "ANY",
            "OperationName": "AnyOperation",
        }

        self.tf_apigw_method_with_auth_resource: dict = {
            **self.tf_apigw_method_common_attributes,
            "values": self.tf_apigw_method_with_auth_properties,
            "address": f"aws_api_gateway_method.{self.apigw_method_with_auth_name}",
            "name": self.apigw_method_with_auth_name,
        }

        self.expected_cfn_apigw_method_with_auth: dict = {
            "Type": AWS_APIGATEWAY_METHOD,
            "Properties": self.expected_cfn_apigw_method_with_auth_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_method.{self.apigw_method_with_auth_name}"},
        }

        self.tf_apigw_stage_properties: dict = {
            "rest_api_id": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "stage_name": "test",
            "variables": {"key1": "value1"},
        }

        self.expected_cfn_apigw_stage_properties: dict = {
            "RestApiId": "aws_api_gateway_rest_api.MyDemoAPI.id",
            "StageName": "test",
            "Variables": {"key1": "value1"},
        }

        self.tf_apigw_stage_resource: dict = {
            **self.tf_apigw_stage_common_attributes,
            "values": self.tf_apigw_stage_properties,
            "address": f"aws_api_gateway_stage.{self.apigw_stage_name}",
            "name": self.apigw_stage_name,
        }

        self.expected_cfn_apigw_stage_resource: dict = {
            "Type": AWS_APIGATEWAY_STAGE,
            "Properties": self.expected_cfn_apigw_stage_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_stage.{self.apigw_stage_name}"},
        }

        self.tf_apigw_rest_api_properties: dict = {
            "name": self.apigw_rest_api_name,
            "body": {
                "openapi": "3.0.1",
                "info": {
                    "title": "example",
                    "version": "1.0",
                },
            },
            "parameters": {"param_a": "value_a"},
            "binary_media_types": ["utf-8"],
        }

        self.expected_cfn_apigw_rest_api_properties: dict = {
            "Name": self.apigw_rest_api_name,
            "Body": {
                "openapi": "3.0.1",
                "info": {
                    "title": "example",
                    "version": "1.0",
                },
            },
            "Parameters": {"param_a": "value_a"},
            "BinaryMediaTypes": ["utf-8"],
        }

        self.tf_apigw_rest_api_resource: dict = {
            **self.tf_apigw_rest_api_common_attributes,
            "values": self.tf_apigw_rest_api_properties,
            "address": f"aws_api_gateway_rest_api.{self.apigw_rest_api_name}",
            "name": self.apigw_rest_api_name,
        }

        self.expected_cfn_apigw_rest_api: dict = {
            "Type": AWS_APIGATEWAY_RESTAPI,
            "Properties": self.expected_cfn_apigw_rest_api_properties,
            "Metadata": {"SamResourceId": f"aws_api_gateway_rest_api.{self.apigw_rest_api_name}"},
        }

        self.tf_json_with_root_module_only: dict = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        self.tf_lambda_function_resource_zip,
                        self.tf_lambda_function_resource_zip_2,
                        self.tf_image_package_type_lambda_function_resource,
                        self.tf_apigw_resource_resource,
                        self.tf_apigw_rest_api_resource,
                        self.tf_apigw_stage_resource,
                        self.tf_apigw_method_resource,
                        self.tf_apigw_method_with_auth_resource,
                        self.tf_apigw_integration_resource,
                        self.tf_apigw_authorizer_resource,
                        self.tf_apigw_integration_response_resource,
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
                f"AwsApiGatewayResourceMyResource{self.mock_logical_id_hash}": self.expected_cfn_apigw_resource,
                f"AwsApiGatewayRestApiMyRestApi{self.mock_logical_id_hash}": self.expected_cfn_apigw_rest_api,
                f"AwsApiGatewayStageMyStage{self.mock_logical_id_hash}": self.expected_cfn_apigw_stage_resource,
                f"AwsApiGatewayMethodMyMethod{self.mock_logical_id_hash}": self.expected_cfn_apigw_method,
                f"AwsApiGatewayMethodMyMethodAuth{self.mock_logical_id_hash}": self.expected_cfn_apigw_method_with_auth,
                f"AwsApiGatewayAuthorizerMyAuthorizer{self.mock_logical_id_hash}": self.expected_cfn_apigw_authorizer,
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
