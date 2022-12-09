"""Test Terraform utilities"""
from unittest import TestCase
from unittest.mock import patch, Mock, call
from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.types import ConstantValue, ResolvedReference
from samcli.hook_packages.terraform.lib.utils import (
    build_cfn_logical_id,
    _calculate_configuration_attribute_value_hash,
)


class TestTerraformUtils(TestCase):
    def setUp(self) -> None:
        self.mock_logical_id_hash = "12AB34CD"

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
    @patch("samcli.hook_packages.terraform.lib.utils.str_checksum")
    def test_build_cfn_logical_id(self, tf_address, expected_logical_id_human_part, checksum_mock):
        checksum_mock.return_value = self.mock_logical_id_hash

        logical_id = build_cfn_logical_id(tf_address)
        checksum_mock.assert_called_once_with(tf_address)
        self.assertEqual(logical_id, expected_logical_id_human_part + self.mock_logical_id_hash)

    def test_build_cfn_logical_id_hash(self):
        # these two addresses should end up with the same human part of the logical id but should
        # have different logical IDs overall because of the hash
        tf_address1 = "aws_lambda_function.s3_lambda"
        tf_address2 = "aws_lambda_function.S3-Lambda"

        logical_id1 = build_cfn_logical_id(tf_address1)
        logical_id2 = build_cfn_logical_id(tf_address2)
        self.assertNotEqual(logical_id1, logical_id2)

    @patch("samcli.hook_packages.terraform.lib.utils.hashlib")
    def test_calculate_configuration_attribute_value_hash_with_string_attribute_value(self, mock_hashlib):
        md5_mock = Mock()
        hash_value = Mock()
        md5_mock.hexdigest.return_value = hash_value
        mock_hashlib.md5.return_value = md5_mock
        attribute_value = "fixed string"
        res = _calculate_configuration_attribute_value_hash(attribute_value)
        self.assertEqual(res, hash_value)
        md5_mock.update.assert_called_with(attribute_value.encode())

    @patch("samcli.hook_packages.terraform.lib.utils.hashlib")
    def test_calculate_configuration_attribute_value_hash_with_reference_attribute_value(self, mock_hashlib):
        md5_mock = Mock()
        hash_value = Mock()
        md5_mock.hexdigest.return_value = hash_value
        mock_hashlib.md5.return_value = md5_mock
        attribute_value = [
            ConstantValue("C"),
            ResolvedReference("aws_lambda_function.arn", "module.m1"),
            ConstantValue("A"),
        ]
        res = _calculate_configuration_attribute_value_hash(attribute_value)
        self.assertEqual(res, hash_value)
        md5_mock.update.assert_has_calls(
            [
                call(
                    "A".encode(),
                ),
                call(
                    "C".encode(),
                ),
                call(
                    "module.m1.aws_lambda_function.arn".encode(),
                ),
            ]
        )
