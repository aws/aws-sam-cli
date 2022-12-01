"""Test Terraform utilities"""
from unittest import TestCase
from unittest.mock import patch, Mock, call
from parameterized import parameterized
from subprocess import CalledProcessError

from samcli.hook_packages.terraform.hooks.prepare.types import ConstantValue, ResolvedReference
from samcli.hook_packages.terraform.lib.utils import (
    build_cfn_logical_id,
    _calculate_configuration_attribute_value_hash,
    _get_python_command_name,
    _get_s3_object_hash,
)

from samcli.lib.hook.exceptions import PrepareHookException


class TestTerraformUtils(TestCase):
    def setUp(self) -> None:
        self.mock_logical_id_hash = "12AB34CD"
        self.s3_bucket = "bucket"
        self.s3_bucket_2 = "not a bucket"
        self.s3_key = "key"
        self.s3_key_2 = "not a key"

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
    @patch("samcli.hook_packages.terraform.lib.utils.run")
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
    @patch("samcli.hook_packages.terraform.lib.utils.run")
    def test_get_python_command_name_python_not_found(self, mock_run_side_effect, mock_subprocess_run):
        mock_subprocess_run.side_effect = mock_run_side_effect

        expected_error_msg = "Python not found. Please ensure that python 3.7 or above is installed."
        with self.assertRaises(PrepareHookException, msg=expected_error_msg):
            _get_python_command_name()

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
