"""Test Terraform prepare translate"""
import copy
from unittest.mock import Mock, call, patch, MagicMock, ANY

from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.exceptions import (
    OneLambdaLayerLinkingLimitationException,
    FunctionLayerLocalVariablesLinkingLimitationException,
    OneRestApiToApiGatewayMethodLinkingLimitationException,
    RestApiToApiGatewayMethodLocalVariablesLinkingLimitationException,
    InvalidResourceLinkingException,
    OneGatewayResourceToRestApiLinkingLimitationException,
    GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
    OneRestApiToApiGatewayStageLinkingLimitationException,
    RestApiToApiGatewayStageLocalVariablesLinkingLimitationException,
    OneGatewayResourceToApiGatewayMethodLinkingLimitationException,
    GatewayResourceToApiGatewayMethodLocalVariablesLinkingLimitationException,
)
from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX,
    ExistingResourceReference,
    LogicalIdReference,
    API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
    API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX,
)
from tests.unit.hook_packages.terraform.hooks.prepare.prepare_base import PrepareHookUnitBase
from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING,
    REMOTE_DUMMY_VALUE,
    AWS_API_GATEWAY_RESOURCE_PROPERTY_BUILDER_MAPPING,
    AWS_API_GATEWAY_REST_API_PROPERTY_BUILDER_MAPPING,
    AWS_API_GATEWAY_STAGE_PROPERTY_BUILDER_MAPPING,
    TF_AWS_API_GATEWAY_REST_API,
    AWS_API_GATEWAY_METHOD_PROPERTY_BUILDER_MAPPING,
    TF_AWS_LAMBDA_FUNCTION,
    TF_AWS_LAMBDA_LAYER_VERSION,
    TF_AWS_API_GATEWAY_METHOD,
    TF_AWS_API_GATEWAY_RESOURCE,
    TF_AWS_API_GATEWAY_STAGE,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    SamMetadataResource,
)
from samcli.hook_packages.terraform.hooks.prepare.translate import (
    translate_to_cfn,
    _add_child_modules_to_queue,
    _add_metadata_resource_to_metadata_list,
    _translate_properties,
    _link_lambda_functions_to_layers,
    _map_s3_sources_to_functions,
    _check_dummy_remote_values,
    _get_s3_object_hash,
    _link_lambda_functions_to_layers_call_back,
    _link_gateway_methods_to_gateway_rest_apis,
    _link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back,
    _link_gateway_resources_to_gateway_rest_apis,
    _link_gateway_stage_to_rest_api,
    _link_gateway_method_to_gateway_resource,
    _link_gateway_method_to_gateway_resource_call_back,
)
from samcli.hook_packages.terraform.hooks.prepare.translate import AWS_PROVIDER_NAME
from samcli.hook_packages.terraform.hooks.prepare.types import TFModule, TFResource, ConstantValue, ResolvedReference
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION


class TestPrepareHookTranslate(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    def test_translate_to_cfn_empty(
        self,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
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
            translated_cfn_dict = translate_to_cfn(tf_json, self.output_dir, self.project_root)
            self.assertEqual(translated_cfn_dict, expected_empty_cfn_dict)
            mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_stage_to_rest_api")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_method_to_gateway_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resources_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_root_module_only(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_link_gateway_resources_to_gateway_rest_apis,
        mock_link_gateway_method_to_gateway_resource,
        mock_link_gateway_stage_to_rest_api,
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
        mock_validator = Mock()
        mock_build_module.return_value = root_module
        checksum_mock.return_value = self.mock_logical_id_hash
        with patch(
            "samcli.hook_packages.terraform.hooks.prepare.translate.TRANSLATION_VALIDATORS",
            {TF_AWS_API_GATEWAY_REST_API: mock_validator},
        ):
            translated_cfn_dict = translate_to_cfn(
                self.tf_json_with_root_module_only, self.output_dir, self.project_root
            )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_root_module_only)
        mock_enrich_resources_and_generate_makefile.assert_not_called()
        expected_arguments_in_call = [
            ANY,
            {
                "aws_lambda_function.myfunc": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
                            "Code": "file.zip",
                            "Handler": "index.handler",
                            "PackageType": "Zip",
                            "Runtime": "python3.7",
                            "Layers": ["layer_arn1", "layer_arn2"],
                            "Timeout": 3,
                            "MemorySize": 128,
                        },
                        "Metadata": {"SamResourceId": "aws_lambda_function.myfunc", "SkipBuild": True},
                    }
                ],
                "aws_lambda_function.myfunc2": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc2",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"hi": "there"}},
                            "Code": "file2.zip",
                            "Handler": "index.handler2",
                            "PackageType": "Zip",
                            "Runtime": "python3.8",
                            "Layers": ["layer_arn"],
                        },
                        "Metadata": {"SamResourceId": "aws_lambda_function.myfunc2", "SkipBuild": True},
                    }
                ],
                "aws_lambda_function.image_func": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "image_func",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
                            "Code": {"ImageUri": "image/uri:tag"},
                            "PackageType": "Image",
                            "Timeout": 3,
                            "MemorySize": 128,
                            "ImageConfig": {
                                "Command": ["cmd1", "cmd2"],
                                "EntryPoint": ["entry1", "entry2"],
                                "WorkingDirectory": "/working/dir/path",
                            },
                        },
                        "Metadata": {"SamResourceId": "aws_lambda_function.image_func", "SkipBuild": True},
                    }
                ],
            },
            {},
        ]
        mock_link_lambda_functions_to_layers.assert_called_once_with(*expected_arguments_in_call)

        expected_arguments_in_call = [
            ANY,
            {
                f"aws_api_gateway_method.my_method": [self.expected_cfn_apigw_method],
            },
            {
                f"AwsApiGatewayRestApiMyRestApi{self.mock_logical_id_hash}": self.tf_apigw_rest_api_resource,
            },
        ]
        mock_link_gateway_methods_to_gateway_rest_apis.assert_called_once_with(*expected_arguments_in_call)

        expected_arguments_in_call = [
            ANY,
            {
                f"aws_api_gateway_resource.my_resource": [self.expected_cfn_apigw_resource],
            },
            {
                f"AwsApiGatewayRestApiMyRestApi{self.mock_logical_id_hash}": self.tf_apigw_rest_api_resource,
            },
        ]
        mock_link_gateway_resources_to_gateway_rest_apis.assert_called_once_with(*expected_arguments_in_call)

        expected_arguments_in_call = [
            ANY,
            {
                f"aws_api_gateway_stage.my_stage": [self.expected_cfn_apigw_stage_resource],
            },
            {
                f"AwsApiGatewayRestApiMyRestApi{self.mock_logical_id_hash}": self.tf_apigw_rest_api_resource,
            },
        ]
        mock_link_gateway_stage_to_rest_api.assert_called_once_with(*expected_arguments_in_call)

        expected_arguments_in_call = [
            ANY,
            {
                f"aws_api_gateway_method.my_method": [self.expected_cfn_apigw_method],
            },
            {
                f"AwsApiGatewayResourceMyResource{self.mock_logical_id_hash}": self.tf_apigw_resource_resource,
            },
        ]
        mock_link_gateway_method_to_gateway_resource.assert_called_once_with(*expected_arguments_in_call)

        mock_validator.assert_called_once_with(
            resource=self.tf_apigw_rest_api_resource, config_resource=config_resource
        )
        mock_validator.return_value.validate.assert_called_once()

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._resolve_resource_attribute")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_s3_object_which_linked_to_uncreated_bucket(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
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

        translate_to_cfn(tf_json_with_root_module_contains_s3_object, self.output_dir, self.project_root)
        mock_resolve_resource_attribute.assert_has_calls([call(resource_mock, "bucket"), call(resource_mock, "key")])

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_child_modules(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
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
        translated_cfn_dict = translate_to_cfn(self.tf_json_with_child_modules, self.output_dir, self.project_root)
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules)
        mock_enrich_resources_and_generate_makefile.assert_not_called()
        expected_arguments_in_call = [
            {
                "aws_lambda_function.myfunc": conf_resource,
                "module.mymodule1.aws_lambda_function.myfunc2": conf_resource,
                "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc3": conf_resource,
                "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4": conf_resource,
            },
            {
                "aws_lambda_function.myfunc": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
                            "Code": "file.zip",
                            "Handler": "index.handler",
                            "PackageType": "Zip",
                            "Runtime": "python3.7",
                            "Layers": ["layer_arn1", "layer_arn2"],
                            "Timeout": 3,
                            "MemorySize": 128,
                        },
                        "Metadata": {"SamResourceId": "aws_lambda_function.myfunc", "SkipBuild": True},
                    }
                ],
                "module.mymodule1.aws_lambda_function.myfunc2": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc2",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"hi": "there"}},
                            "Code": "file2.zip",
                            "Handler": "index.handler2",
                            "PackageType": "Zip",
                            "Runtime": "python3.8",
                            "Layers": ["layer_arn"],
                        },
                        "Metadata": {
                            "SamResourceId": "module.mymodule1.aws_lambda_function.myfunc2",
                            "SkipBuild": True,
                        },
                    }
                ],
                "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc3": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc3",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"hi": "there"}},
                            "Code": "file2.zip",
                            "Handler": "index.handler2",
                            "PackageType": "Zip",
                            "Runtime": "python3.8",
                            "Layers": ["layer_arn"],
                        },
                        "Metadata": {
                            "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc3",
                            "SkipBuild": True,
                        },
                    }
                ],
                "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4": [
                    {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "FunctionName": "myfunc4",
                            "Architectures": ["x86_64"],
                            "Environment": {"Variables": {"hi": "there"}},
                            "Code": "file2.zip",
                            "Handler": "index.handler2",
                            "PackageType": "Zip",
                            "Runtime": "python3.8",
                            "Layers": ["layer_arn"],
                        },
                        "Metadata": {
                            "SamResourceId": "module.mymodule1.module.mymodule2.aws_lambda_function.myfunc4",
                            "SkipBuild": True,
                        },
                    }
                ],
            },
            {},
        ]
        mock_link_lambda_functions_to_layers.assert_called_once_with(*expected_arguments_in_call)
        mock_link_gateway_methods_to_gateway_rest_apis.assert_called_once_with({}, {}, {})
        mock_check_dummy_remote_values.assert_called_once_with(translated_cfn_dict.get("Resources"))

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_resource_property_mapping")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.isinstance")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceTranslationProperties")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.build_cfn_logical_id")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resources_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_stage_to_rest_api")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_method_to_gateway_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_root_module_with_sam_metadata_resource(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_gateway_method_to_gateway_resource,
        mock_link_gateway_stage_to_rest_api,
        mock_link_gateway_resources_to_gateway_rest_apis,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_link_lambda_functions_to_layers,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_build_cfn_logical_id,
        mock_resource_translation_properties,
        mock_isinstance,
        mock_resource_property_mapping,
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

        mock_isinstance.return_value = True
        lambda_properties_mock = Mock()
        lambda_layer_properties_mock = Mock()
        rest_api_properties_mock = Mock()
        gateway_method_properties_mock = Mock()
        gateway_resource_properties_mock = Mock()
        gateway_stage_properties_mock = Mock()
        mock_resource_property_mapping.return_value = {
            TF_AWS_LAMBDA_FUNCTION: lambda_properties_mock,
            TF_AWS_LAMBDA_LAYER_VERSION: lambda_layer_properties_mock,
            TF_AWS_API_GATEWAY_REST_API: rest_api_properties_mock,
            TF_AWS_API_GATEWAY_METHOD: gateway_method_properties_mock,
            TF_AWS_API_GATEWAY_RESOURCE: gateway_resource_properties_mock,
            TF_AWS_API_GATEWAY_STAGE: gateway_stage_properties_mock,
        }

        translated_cfn_dict = translate_to_cfn(
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
        self.assertEqual(len(lambda_properties_mock.method_calls), 6)
        lambda_properties_mock.add_lambda_resources_to_code_map.assert_has_calls(
            [
                call(
                    ANY,
                    {
                        "FunctionName": "myfunc",
                        "Architectures": ["x86_64"],
                        "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
                        "Code": "file.zip",
                        "Handler": "index.handler",
                        "PackageType": "Zip",
                        "Runtime": "python3.7",
                        "Layers": ["layer_arn1", "layer_arn2"],
                        "Timeout": 3,
                        "MemorySize": 128,
                    },
                    {},
                ),
                call(
                    ANY,
                    {
                        "FunctionName": "myfunc2",
                        "Architectures": ["x86_64"],
                        "Environment": {"Variables": {"hi": "there"}},
                        "Code": "file2.zip",
                        "Handler": "index.handler2",
                        "PackageType": "Zip",
                        "Runtime": "python3.8",
                        "Layers": ["layer_arn"],
                    },
                    {},
                ),
                call(
                    ANY,
                    {
                        "FunctionName": "image_func",
                        "Architectures": ["x86_64"],
                        "Environment": {"Variables": {"foo": "bar", "hello": "world"}},
                        "Code": {"ImageUri": "image/uri:tag"},
                        "PackageType": "Image",
                        "Timeout": 3,
                        "MemorySize": 128,
                        "ImageConfig": {
                            "Command": ["cmd1", "cmd2"],
                            "EntryPoint": ["entry1", "entry2"],
                            "WorkingDirectory": "/working/dir/path",
                        },
                    },
                    {},
                ),
            ]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_resource_property_mapping")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_child_modules_with_sam_metadata_resource(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_resource_property_collector,
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
        translated_cfn_dict = translate_to_cfn(
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_resource_property_mapping")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_unsupported_provider(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_get_resource_property_mapping,
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
        translated_cfn_dict = translate_to_cfn(
            self.tf_json_with_unsupported_provider, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_provider)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_resource_property_mapping")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_unsupported_resource_type(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_get_resource_property_mapping,
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
        translated_cfn_dict = translate_to_cfn(
            self.tf_json_with_unsupported_resource_type, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_unsupported_resource_type)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_resource_property_mapping")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._check_dummy_remote_values")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._build_module")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_methods_to_gateway_rest_apis")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.enrich_resources_and_generate_makefile")
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_translate_to_cfn_with_mapping_s3_source_to_function(
        self,
        checksum_mock,
        mock_enrich_resources_and_generate_makefile,
        mock_link_lambda_functions_to_layers,
        mock_link_gateway_methods_to_gateway_rest_apis,
        mock_get_configuration_address,
        mock_build_module,
        mock_check_dummy_remote_values,
        mock_resource_property_collector,
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
        translated_cfn_dict = translate_to_cfn(
            self.tf_json_with_child_modules_and_s3_source_mapping, self.output_dir, self.project_root
        )
        self.assertEqual(translated_cfn_dict, self.expected_cfn_with_child_modules_and_s3_source_mapping)
        mock_enrich_resources_and_generate_makefile.assert_not_called()

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

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_lambda_functions_to_layers_call_back")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinker")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinkingPair")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourcePairExceptions")
    def test_link_lambda_functions_to_layers(
        self,
        mock_resource_linking_exceptions,
        mock_resource_linking_pair,
        mock_resource_linker,
        mock_link_lambda_functions_to_layers_call_back,
    ):
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
        mock_resource_linking_exceptions.assert_called_once_with(
            multiple_resource_linking_exception=OneLambdaLayerLinkingLimitationException,
            local_variable_linking_exception=FunctionLayerLocalVariablesLinkingLimitationException,
        )
        mock_resource_linking_pair.assert_called_once_with(
            source_resource_cfn_resource=lambda_funcs_config_resources,
            source_resource_tf_config=resources,
            destination_resource_tf=terraform_layers_resources,
            tf_destination_attribute_name="arn",
            terraform_link_field_name="layers",
            cfn_link_field_name="Layers",
            terraform_resource_type_prefix=LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=mock_link_lambda_functions_to_layers_call_back,
            linking_exceptions=mock_resource_linking_exceptions(),
        )
        mock_resource_linker.assert_called_once_with(mock_resource_linking_pair())

    @parameterized.expand(
        [
            (
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"FunctionName": "func", "Layers": ["existing_layer1.arn", "applied_layer1.arn"]},
                    "Metadata": {"SamResourceId": "aws_lambda_function.remote_lambda_code", "SkipBuild": True},
                },
                [ExistingResourceReference("existing_layer1.arn"), LogicalIdReference("Layer1LogicaId")],
                ["existing_layer1.arn", {"Ref": "Layer1LogicaId"}],
            ),
            (
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"FunctionName": "func", "Layers": ["existing_layer1.arn", "existing_layer2.arn"]},
                    "Metadata": {"SamResourceId": "aws_lambda_function.remote_lambda_code", "SkipBuild": True},
                },
                [ExistingResourceReference("existing_layer1.arn"), ExistingResourceReference("existing_layer2.arn")],
                ["existing_layer1.arn", "existing_layer2.arn"],
            ),
            (
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "func",
                    },
                    "Metadata": {"SamResourceId": "aws_lambda_function.remote_lambda_code", "SkipBuild": True},
                },
                [LogicalIdReference("Layer1LogicaId")],
                [{"Ref": "Layer1LogicaId"}],
            ),
        ]
    )
    def test_link_lambda_functions_to_layers_call_back(self, input_function, logical_ids, expected_layers):
        lambda_function = input_function.copy()
        _link_lambda_functions_to_layers_call_back(lambda_function, logical_ids)
        input_function["Properties"]["Layers"] = expected_layers
        self.assertEqual(lambda_function, input_function)

    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinker")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinkingPair")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourcePairExceptions")
    def test_link_gateway_methods_to_gateway_rest_apis(
        self,
        mock_resource_linking_exceptions,
        mock_resource_linking_pair,
        mock_resource_linker,
        mock_link_gateway_methods_to_gateway_rest_apis_call_back,
    ):
        gateway_method_config_resources = Mock()
        terraform_rest_apis_resources = Mock()
        resources = Mock()
        _link_gateway_methods_to_gateway_rest_apis(
            resources, gateway_method_config_resources, terraform_rest_apis_resources
        )
        mock_resource_linking_exceptions.assert_called_once_with(
            multiple_resource_linking_exception=OneRestApiToApiGatewayMethodLinkingLimitationException,
            local_variable_linking_exception=RestApiToApiGatewayMethodLocalVariablesLinkingLimitationException,
        )
        mock_resource_linking_pair.assert_called_once_with(
            source_resource_cfn_resource=gateway_method_config_resources,
            source_resource_tf_config=resources,
            destination_resource_tf=terraform_rest_apis_resources,
            tf_destination_attribute_name="id",
            terraform_link_field_name="rest_api_id",
            cfn_link_field_name="RestApiId",
            terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=mock_link_gateway_methods_to_gateway_rest_apis_call_back,
            linking_exceptions=mock_resource_linking_exceptions(),
        )
        mock_resource_linker.assert_called_once_with(mock_resource_linking_pair())

    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back"
    )
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resource_to_gateway_rest_apis_parent_id_call_back"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinker")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinkingPair")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourcePairExceptions")
    def test_link_gateway_resources_to_gateway_rest_apis(
        self,
        mock_resource_linking_exceptions,
        mock_resource_linking_pair,
        mock_resource_linker,
        mock_link_gateway_methods_to_gateway_rest_apis_parent_id_call_back,
        mock_link_gateway_methods_to_gateway_rest_apis_rest_api_id_call_back,
    ):
        gateway_resource_config_resources = Mock()
        terraform_rest_apis_resources = Mock()
        resources = Mock()
        _link_gateway_resources_to_gateway_rest_apis(
            resources, gateway_resource_config_resources, terraform_rest_apis_resources
        )
        mock_resource_linking_exceptions.assert_has_calls(
            [
                call(
                    multiple_resource_linking_exception=OneGatewayResourceToRestApiLinkingLimitationException,
                    local_variable_linking_exception=GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
                ),
                call(
                    multiple_resource_linking_exception=OneGatewayResourceToRestApiLinkingLimitationException,
                    local_variable_linking_exception=GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException,
                ),
            ]
        )

        mock_resource_linking_pair.assert_has_calls(
            [
                call(
                    source_resource_cfn_resource=gateway_resource_config_resources,
                    source_resource_tf_config=resources,
                    destination_resource_tf=terraform_rest_apis_resources,
                    tf_destination_attribute_name="id",
                    terraform_link_field_name="rest_api_id",
                    cfn_link_field_name="RestApiId",
                    terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
                    cfn_resource_update_call_back_function=mock_link_gateway_methods_to_gateway_rest_apis_rest_api_id_call_back,
                    linking_exceptions=mock_resource_linking_exceptions(),
                ),
                call(
                    source_resource_cfn_resource=gateway_resource_config_resources,
                    source_resource_tf_config=resources,
                    destination_resource_tf=terraform_rest_apis_resources,
                    tf_destination_attribute_name="root_resource_id",
                    terraform_link_field_name="parent_id",
                    cfn_link_field_name="ResourceId",
                    terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
                    cfn_resource_update_call_back_function=mock_link_gateway_methods_to_gateway_rest_apis_parent_id_call_back,
                    linking_exceptions=mock_resource_linking_exceptions(),
                ),
            ]
        )
        mock_resource_linker.assert_has_calls(
            [
                call(mock_resource_linking_pair()),
                call().link_resources(),
                call(mock_resource_linking_pair()),
                call().link_resources(),
            ]
        )

    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinker")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinkingPair")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourcePairExceptions")
    def test_link_gateway_stage_to_gateway_rest_apis(
        self,
        mock_resource_linking_exceptions,
        mock_resource_linking_pair,
        mock_resource_linker,
        mock_link_gateway_resource_to_gateway_rest_apis_call_back,
    ):
        gateway_stage_config_resources = Mock()
        terraform_rest_apis_resources = Mock()
        resources = Mock()
        _link_gateway_stage_to_rest_api(resources, gateway_stage_config_resources, terraform_rest_apis_resources)
        mock_resource_linking_exceptions.assert_called_once_with(
            multiple_resource_linking_exception=OneRestApiToApiGatewayStageLinkingLimitationException,
            local_variable_linking_exception=RestApiToApiGatewayStageLocalVariablesLinkingLimitationException,
        )
        mock_resource_linking_pair.assert_called_once_with(
            source_resource_cfn_resource=gateway_stage_config_resources,
            source_resource_tf_config=resources,
            destination_resource_tf=terraform_rest_apis_resources,
            tf_destination_attribute_name="id",
            terraform_link_field_name="rest_api_id",
            cfn_link_field_name="RestApiId",
            terraform_resource_type_prefix=API_GATEWAY_REST_API_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=mock_link_gateway_resource_to_gateway_rest_apis_call_back,
            linking_exceptions=mock_resource_linking_exceptions(),
        )
        mock_resource_linker.assert_called_once_with(mock_resource_linking_pair())

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._link_gateway_method_to_gateway_resource_call_back")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinker")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourceLinkingPair")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate.ResourcePairExceptions")
    def test_link_gateway_methods_to_gateway_resources(
        self,
        mock_resource_linking_exceptions,
        mock_resource_linking_pair,
        mock_resource_linker,
        mock_link_gateway_method_to_gateway_resource_call_back,
    ):
        gateway_method_config_resources = Mock()
        terraform_resources_resources = Mock()
        resources = Mock()
        _link_gateway_method_to_gateway_resource(
            resources, gateway_method_config_resources, terraform_resources_resources
        )
        mock_resource_linking_exceptions.assert_called_once_with(
            multiple_resource_linking_exception=OneGatewayResourceToApiGatewayMethodLinkingLimitationException,
            local_variable_linking_exception=GatewayResourceToApiGatewayMethodLocalVariablesLinkingLimitationException,
        )
        mock_resource_linking_pair.assert_called_once_with(
            source_resource_cfn_resource=gateway_method_config_resources,
            source_resource_tf_config=resources,
            destination_resource_tf=terraform_resources_resources,
            tf_destination_attribute_name="id",
            terraform_link_field_name="resource_id",
            cfn_link_field_name="ResourceId",
            terraform_resource_type_prefix=API_GATEWAY_RESOURCE_RESOURCE_ADDRESS_PREFIX,
            cfn_resource_update_call_back_function=mock_link_gateway_method_to_gateway_resource_call_back,
            linking_exceptions=mock_resource_linking_exceptions(),
        )
        mock_resource_linker.assert_called_once_with(mock_resource_linking_pair())

    @parameterized.expand(
        [
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post", "RestApiId": "restapi.id"},
                },
                [LogicalIdReference("RestApi1")],
                {"Ref": "RestApi1"},
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post", "RestApiId": "restapi.id"},
                },
                [ExistingResourceReference("restapi.id")],
                "restapi.id",
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post"},
                },
                [LogicalIdReference("RestApi1")],
                {"Ref": "RestApi1"},
            ),
        ]
    )
    def test_link_gateway_methods_to_gateway_rest_apis_call_back(
        self, input_gateway_method, logical_ids, expected_rest_api
    ):
        gateway_method = input_gateway_method.copy()
        _link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back(gateway_method, logical_ids)
        input_gateway_method["Properties"]["RestApiId"] = expected_rest_api
        self.assertEqual(gateway_method, input_gateway_method)

    def test_link_gateway_methods_to_gateway_rest_apis_call_back_multiple_destinations(self):
        gateway_method = Mock()
        logical_ids = [Mock(), Mock()]
        with self.assertRaises(
            InvalidResourceLinkingException,
            msg="Could not link multiple Rest APIs to one Gateway method resource",
        ):
            _link_gateway_resource_to_gateway_rest_apis_rest_api_id_call_back(gateway_method, logical_ids)

    @parameterized.expand(
        [
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post", "ResourceId": "resource.id"},
                },
                [LogicalIdReference("Resource1")],
                {"Ref": "Resource1"},
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post", "ResourceId": "resource.id"},
                },
                [ExistingResourceReference("resource.id")],
                "resource.id",
            ),
            (
                {
                    "Type": "AWS::ApiGateway::Method",
                    "Properties": {"HttpMethod": "post"},
                },
                [LogicalIdReference("Resource1")],
                {"Ref": "Resource1"},
            ),
        ]
    )
    def test_link_gateway_method_to_gateway_resource_call_back(
        self, input_gateway_method, logical_ids, expected_resource
    ):
        gateway_method = input_gateway_method.copy()
        _link_gateway_method_to_gateway_resource_call_back(gateway_method, logical_ids)
        input_gateway_method["Properties"]["ResourceId"] = expected_resource
        self.assertEqual(gateway_method, input_gateway_method)

    def test_link_gateway_method_to_gateway_resource_call_back_multiple_destinations(self):
        gateway_method = Mock()
        logical_ids = [Mock(), Mock()]
        with self.assertRaises(
            InvalidResourceLinkingException,
            msg="Could not link multiple Gateway Resources to one Gateway method resource",
        ):
            _link_gateway_method_to_gateway_resource_call_back(gateway_method, logical_ids)

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._get_s3_object_hash")
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._get_s3_object_hash")
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._calculate_configuration_attribute_value_hash")
    @patch("samcli.hook_packages.terraform.hooks.prepare.translate._get_s3_object_hash")
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

    def test_translating_apigw_resource(self):
        translated_cfn_properties = _translate_properties(
            self.tf_apigw_resource_properties, AWS_API_GATEWAY_RESOURCE_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_apigw_resource_properties)

    def test_translating_apigw_stage_resource(self):
        translated_cfn_properties = _translate_properties(
            self.tf_apigw_stage_properties, AWS_API_GATEWAY_STAGE_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_apigw_stage_properties)

    def test_translating_apigw_rest_api(self):
        translated_cfn_properties = _translate_properties(
            self.tf_apigw_rest_api_properties, AWS_API_GATEWAY_REST_API_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_apigw_rest_api_properties)

    def test_translating_apigw_rest_method(self):
        translated_cfn_properties = _translate_properties(
            self.tf_apigw_method_properties, AWS_API_GATEWAY_METHOD_PROPERTY_BUILDER_MAPPING, Mock()
        )
        self.assertEqual(translated_cfn_properties, self.expected_cfn_apigw_method_properties)
