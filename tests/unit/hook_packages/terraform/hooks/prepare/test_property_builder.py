"""Test Terraform property builder"""
from unittest.mock import patch, Mock, call
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    _build_code_property,
    REMOTE_DUMMY_VALUE,
    _get_property_extractor,
    _build_lambda_function_environment_property,
    _build_lambda_function_image_config_property,
    _check_image_config_value,
)

from samcli.lib.hook.exceptions import PrepareHookException
from tests.unit.hook_packages.terraform.hooks.prepare.prepare_base import PrepareHookUnitBase


class TestTerraformPropBuilder(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    def test_build_lambda_function_code_property_zip(self):
        resource_mock = Mock()
        expected_cfn_property = self.expected_cfn_zip_function_properties["Code"]
        translated_cfn_property = _build_code_property(self.tf_zip_function_properties, resource_mock)
        resource_mock.assert_not_called()
        self.assertEqual(translated_cfn_property, expected_cfn_property)

    @patch("samcli.hook_packages.terraform.hooks.prepare.property_builder._resolve_resource_attribute")
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

    @patch("samcli.hook_packages.terraform.hooks.prepare.property_builder._resolve_resource_attribute")
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
