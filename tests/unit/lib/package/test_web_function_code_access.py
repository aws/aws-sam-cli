import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.package.web_function_code_access import (
    stacks_have_web_functions,
    warn_if_bucket_cannot_serve_web_function_code,
)
from samcli.lib.providers.provider import Stack

LAMBDA_READ_STATEMENT = {
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
    "Resource": "arn:aws:s3:::bucket/*",
}


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": code}}, "Operation")


def _s3_client(policy_statements=None, versioning="Enabled", policy_error=None):
    s3_client = MagicMock()
    s3_client.get_bucket_versioning.return_value = {"Status": versioning} if versioning else {}
    if policy_error:
        s3_client.get_bucket_policy.side_effect = _client_error(policy_error)
    else:
        s3_client.get_bucket_policy.return_value = {"Policy": json.dumps({"Statement": policy_statements or []})}
    return s3_client


def _stack(resources, stack_path=""):
    return Stack("", stack_path, "template.yaml", {}, {"Resources": resources})


@patch("samcli.lib.package.web_function_code_access.click")
class TestBucketChecks(TestCase):
    def test_no_warnings_for_a_compliant_bucket(self, click_mock):
        warnings = warn_if_bucket_cannot_serve_web_function_code(_s3_client([LAMBDA_READ_STATEMENT]), "bucket")
        self.assertEqual(warnings, [])
        click_mock.secho.assert_not_called()

    @parameterized.expand(
        [
            ("wildcard actions", {**LAMBDA_READ_STATEMENT, "Action": "s3:Get*"}),
            ("prefix resource", {**LAMBDA_READ_STATEMENT, "Resource": "arn:aws:s3:::bucket/app/*"}),
            ("other partition", {**LAMBDA_READ_STATEMENT, "Resource": "arn:aws-cn:s3:::bucket/*"}),
            ("public principal", {**LAMBDA_READ_STATEMENT, "Principal": "*"}),
        ]
    )
    def test_accepts_equivalent_statements(self, click_mock, _, statement):
        warnings = warn_if_bucket_cannot_serve_web_function_code(_s3_client([statement]), "bucket", prefix="app")
        self.assertEqual(warnings, [])

    @parameterized.expand(
        [
            (
                "no lambda principal",
                {**LAMBDA_READ_STATEMENT, "Principal": {"Service": "serverlessrepo.amazonaws.com"}},
            ),
            ("missing GetObjectVersion", {**LAMBDA_READ_STATEMENT, "Action": "s3:GetObject"}),
            ("other bucket", {**LAMBDA_READ_STATEMENT, "Resource": "arn:aws:s3:::other/*"}),
            ("other prefix", {**LAMBDA_READ_STATEMENT, "Resource": "arn:aws:s3:::bucket/other/*"}),
            ("deny", {**LAMBDA_READ_STATEMENT, "Effect": "Deny"}),
        ]
    )
    def test_warns_when_policy_does_not_allow_lambda_reads(self, click_mock, _, statement):
        warnings = warn_if_bucket_cannot_serve_web_function_code(_s3_client([statement]), "bucket", prefix="app")
        self.assertEqual(len(warnings), 1)
        self.assertIn("doesn't allow lambda.amazonaws.com", warnings[0])

    def test_warns_when_bucket_has_no_policy(self, click_mock):
        warnings = warn_if_bucket_cannot_serve_web_function_code(
            _s3_client(policy_error="NoSuchBucketPolicy"), "bucket"
        )
        self.assertIn("doesn't allow lambda.amazonaws.com", warnings[0])

    def test_warns_when_policy_cannot_be_read(self, click_mock):
        warnings = warn_if_bucket_cannot_serve_web_function_code(_s3_client(policy_error="AccessDenied"), "bucket")
        self.assertIn("Couldn't read the policy", warnings[0])

    @parameterized.expand([("Suspended",), (None,)])
    def test_warns_when_versioning_is_not_enabled(self, click_mock, status):
        warnings = warn_if_bucket_cannot_serve_web_function_code(
            _s3_client([LAMBDA_READ_STATEMENT], versioning=status), "bucket"
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("versioning", warnings[0])
        click_mock.secho.assert_called_once()

    def test_warns_when_versioning_cannot_be_read(self, click_mock):
        s3_client = _s3_client([LAMBDA_READ_STATEMENT])
        s3_client.get_bucket_versioning.side_effect = _client_error("AccessDenied")
        warnings = warn_if_bucket_cannot_serve_web_function_code(s3_client, "bucket")
        self.assertIn("Couldn't check", warnings[0])


@patch("samcli.lib.package.web_function_code_access.click")
class TestKmsKeyChecks(TestCase):
    def _kms_client(self, key_manager="CUSTOMER", statements=None):
        kms_client = MagicMock()
        kms_client.describe_key.return_value = {"KeyMetadata": {"KeyId": "key-id", "KeyManager": key_manager}}
        kms_client.get_key_policy.return_value = {"Policy": json.dumps({"Statement": statements or []})}
        return kms_client

    def _run(self, kms_client):
        return warn_if_bucket_cannot_serve_web_function_code(
            _s3_client([LAMBDA_READ_STATEMENT]), "bucket", kms_key_id="key-id", kms_client=kms_client
        )

    def test_customer_managed_key_that_grants_decrypt(self, click_mock):
        statement = {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "kms:Decrypt"}
        self.assertEqual(self._run(self._kms_client(statements=[statement])), [])

    def test_aws_managed_key(self, click_mock):
        warnings = self._run(self._kms_client(key_manager="AWS"))
        self.assertIn("AWS managed key", warnings[0])

    def test_customer_managed_key_without_decrypt_grant(self, click_mock):
        root = {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789012:root"}, "Action": "kms:*"}
        warnings = self._run(self._kms_client(statements=[root]))
        self.assertIn("doesn't allow lambda.amazonaws.com to call kms:Decrypt", warnings[0])

    def test_key_cannot_be_described(self, click_mock):
        kms_client = self._kms_client()
        kms_client.describe_key.side_effect = _client_error("AccessDenied")
        self.assertIn("Couldn't check KMS key", self._run(kms_client)[0])


class TestStacksHaveWebFunctions(TestCase):
    def test_finds_web_functions_in_nested_stacks(self):
        root = _stack({"App": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "child.yaml"}}})
        child = _stack(
            {"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}}, stack_path="App"
        )
        self.assertFalse(stacks_have_web_functions([root]))
        self.assertTrue(stacks_have_web_functions([root, child], local_code_only=True))

    @parameterized.expand([("s3://bucket/key.zip",), ({"Bucket": "bucket", "Key": "key.zip"},)])
    def test_local_code_only_skips_s3_code(self, code_uri):
        stack = _stack({"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": code_uri}}})
        self.assertTrue(stacks_have_web_functions([stack]))
        self.assertFalse(stacks_have_web_functions([stack], local_code_only=True))
