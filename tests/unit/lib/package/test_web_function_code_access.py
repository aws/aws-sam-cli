import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.package.web_function_code_access import (
    WebFunctionCodeBucketError,
    stacks_have_web_functions,
    check_web_function_code_bucket,
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
        warnings = check_web_function_code_bucket(_s3_client([LAMBDA_READ_STATEMENT]), "bucket")
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
        warnings = check_web_function_code_bucket(_s3_client([statement]), "bucket", prefix="app")
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
        warnings = check_web_function_code_bucket(_s3_client([statement]), "bucket", prefix="app")
        self.assertEqual(len(warnings), 1)
        self.assertIn("doesn't allow lambda.amazonaws.com", warnings[0])

    def test_warns_when_bucket_has_no_policy(self, click_mock):
        warnings = check_web_function_code_bucket(_s3_client(policy_error="NoSuchBucketPolicy"), "bucket")
        self.assertIn("doesn't allow lambda.amazonaws.com", warnings[0])

    def test_warns_when_policy_cannot_be_read(self, click_mock):
        warnings = check_web_function_code_bucket(_s3_client(policy_error="AccessDenied"), "bucket")
        self.assertIn("Couldn't read the policy", warnings[0])

    @parameterized.expand([("Suspended",), (None,)])
    def test_fails_when_versioning_is_not_enabled(self, click_mock, status):
        with self.assertRaises(WebFunctionCodeBucketError) as ctx:
            check_web_function_code_bucket(_s3_client([LAMBDA_READ_STATEMENT], versioning=status), "bucket")
        self.assertIn("doesn't have versioning enabled", ctx.exception.message)

    def test_failure_still_prints_warnings_first(self, click_mock):
        with self.assertRaises(WebFunctionCodeBucketError):
            check_web_function_code_bucket(_s3_client(policy_error="NoSuchBucketPolicy", versioning=None), "bucket")
        click_mock.secho.assert_called_once()
        self.assertIn("doesn't allow lambda.amazonaws.com", click_mock.secho.call_args.args[0])
        self.assertTrue(click_mock.secho.call_args.kwargs["err"])

    def test_warns_when_versioning_cannot_be_read(self, click_mock):
        s3_client = _s3_client([LAMBDA_READ_STATEMENT])
        s3_client.get_bucket_versioning.side_effect = _client_error("AccessDenied")
        warnings = check_web_function_code_bucket(s3_client, "bucket")
        self.assertIn("Couldn't check", warnings[0])


@patch("samcli.lib.package.web_function_code_access.click")
class TestKmsKeyChecks(TestCase):
    def _kms_client(self, key_manager="CUSTOMER", statements=None):
        kms_client = MagicMock()
        kms_client.describe_key.return_value = {"KeyMetadata": {"KeyId": "key-id", "KeyManager": key_manager}}
        kms_client.get_key_policy.return_value = {"Policy": json.dumps({"Statement": statements or []})}
        return kms_client

    def _run(self, kms_client):
        return check_web_function_code_bucket(
            _s3_client([LAMBDA_READ_STATEMENT]), "bucket", kms_key_id="key-id", kms_client=kms_client
        )

    def test_customer_managed_key_that_grants_decrypt(self, click_mock):
        statement = {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "kms:Decrypt"}
        self.assertEqual(self._run(self._kms_client(statements=[statement])), [])

    def test_aws_managed_key_fails(self, click_mock):
        with self.assertRaises(WebFunctionCodeBucketError) as ctx:
            self._run(self._kms_client(key_manager="AWS"))
        self.assertIn("AWS managed key", ctx.exception.message)

    def test_unversioned_bucket_and_aws_managed_key_are_both_reported(self, click_mock):
        with self.assertRaises(WebFunctionCodeBucketError) as ctx:
            check_web_function_code_bucket(
                _s3_client([LAMBDA_READ_STATEMENT], versioning=None),
                "bucket",
                kms_key_id="key-id",
                kms_client=self._kms_client(key_manager="AWS"),
            )
        self.assertIn("versioning", ctx.exception.message)
        self.assertIn("AWS managed key", ctx.exception.message)

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


class TestWebFunctionUploaderRouting(TestCase):
    def test_web_function_code_uses_its_own_uploader(self):
        from samcli.lib.package.packageable_resources import ServerlessWebFunctionResource
        from samcli.lib.package.uploaders import Destination, Uploaders

        s3_uploader, ecr_uploader, web_uploader = MagicMock(), MagicMock(), MagicMock()
        self.assertIs(Uploaders(s3_uploader, ecr_uploader, web_uploader).get(Destination.WEB_FUNCTION_S3), web_uploader)
        self.assertIs(Uploaders(s3_uploader, ecr_uploader).get(Destination.WEB_FUNCTION_S3), s3_uploader)
        self.assertEqual(ServerlessWebFunctionResource.EXPORT_DESTINATION, Destination.WEB_FUNCTION_S3)

    def test_web_function_code_is_not_deleted_ahead_of_the_stack(self):
        from samcli.lib.package.packageable_resources import ServerlessWebFunctionResource
        from samcli.lib.package.uploaders import Uploaders

        s3_uploader = MagicMock()
        resource = ServerlessWebFunctionResource(Uploaders(s3_uploader, MagicMock()), None)
        resource.delete("Fn", {"CodeUri": "s3://bucket/key"})
        s3_uploader.delete_artifact.assert_not_called()


class TestWebFunctionCodeUriImport(TestCase):
    def _resource(self, export_name):
        from samcli.lib.package.packageable_resources import ServerlessWebFunctionResource
        from samcli.lib.package.uploaders import Uploaders

        code_signer = MagicMock()
        code_signer.should_sign_package.return_value = False
        return ServerlessWebFunctionResource(
            Uploaders(MagicMock(), MagicMock(), MagicMock(), web_function_bucket_export=export_name), code_signer
        )

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_code_uri_imports_the_code_bucket(self, upload_mock):
        upload_mock.return_value = "s3://code-bucket/abc123"
        resource_dict = {"CodeUri": "web/"}
        self._resource("my-app-export").do_export("Fn", resource_dict, "/dir")
        self.assertEqual(resource_dict["CodeUri"], {"Bucket": {"Fn::ImportValue": "my-app-export"}, "Key": "abc123"})

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_code_uri_keeps_the_object_version(self, upload_mock):
        upload_mock.return_value = "s3://code-bucket/abc123?versionId=v1"
        resource_dict = {"CodeUri": "web/"}
        self._resource("my-app-export").do_export("Fn", resource_dict, "/dir")
        self.assertEqual(resource_dict["CodeUri"]["Version"], "v1")

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_code_uri_is_a_url_without_a_code_bucket(self, upload_mock):
        upload_mock.return_value = "s3://my-bucket/abc123"
        resource_dict = {"CodeUri": "web/"}
        self._resource(None).do_export("Fn", resource_dict, "/dir")
        self.assertEqual(resource_dict["CodeUri"], "s3://my-bucket/abc123")


class TestTemplateFileHasLocalWebFunctions(TestCase):
    @patch("samcli.lib.providers.sam_stack_provider.SamLocalStackProvider.get_stacks")
    def test_detects_local_web_functions_in_nested_stacks(self, get_stacks_mock):
        from samcli.lib.package.web_function_code_access import template_file_has_local_web_functions

        root = MagicMock(resources={"App": {"Type": "AWS::Serverless::Application"}})
        child = MagicMock(resources={"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}})
        get_stacks_mock.return_value = ([root, child], [])
        self.assertTrue(template_file_has_local_web_functions("template.yaml"))
        get_stacks_mock.return_value = ([root], [])
        self.assertFalse(template_file_has_local_web_functions("template.yaml"))
        get_stacks_mock.side_effect = Exception("unreadable")
        self.assertFalse(template_file_has_local_web_functions("template.yaml"))
