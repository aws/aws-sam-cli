import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from samcli.lib.bootstrap.web_function_code_bucket import (
    CODE_BUCKET_OUTPUT_KEY,
    CODE_BUCKET_DELETED,
    CODE_BUCKET_NOT_FOUND,
    CODE_BUCKET_PROTECTED,
    WebFunctionCodeBucketStack,
    keep_web_function_code_bucket,
    delete_web_function_code_bucket,
    get_code_bucket_template,
    manage_web_function_code_bucket,
    retained_web_functions,
)
from samcli.lib.utils.managed_cloudformation_stack import StackOutput


class TestWebFunctionCodeBucketStack(TestCase):
    def test_stack_name_is_unique_and_within_the_limit(self):
        long_name = "a" * 128
        self.assertLessEqual(len(WebFunctionCodeBucketStack(long_name).stack_name), 128)
        self.assertNotEqual(
            WebFunctionCodeBucketStack("a" * 100 + "x").stack_name,
            WebFunctionCodeBucketStack("a" * 100 + "y").stack_name,
        )
        self.assertTrue(WebFunctionCodeBucketStack("my-app").stack_name.startswith("my-app-"))

    def test_template_bucket_meets_web_function_requirements(self):
        template = json.loads(get_code_bucket_template("my-app"))
        self.assertEqual(
            template["Outputs"][CODE_BUCKET_OUTPUT_KEY]["Export"],
            {"Name": WebFunctionCodeBucketStack("my-app").export_name},
        )
        resources = template["Resources"]
        bucket = resources["CodeBucket"]["Properties"]
        self.assertEqual(bucket["VersioningConfiguration"], {"Status": "Enabled"})
        encryption = bucket["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        self.assertEqual(encryption["ServerSideEncryptionByDefault"]["SSEAlgorithm"], "AES256")
        self.assertIn({"Key": "ManagedStackSource", "Value": "AwsSamCli"}, bucket["Tags"])

        statements = resources["CodeBucketPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        allow = next(s for s in statements if s["Effect"] == "Allow")
        self.assertEqual(allow["Principal"], {"Service": "lambda.amazonaws.com"})
        self.assertEqual(allow["Action"], ["s3:GetObject", "s3:GetObjectVersion"])
        self.assertEqual(allow["Condition"]["StringEquals"], {"aws:SourceAccount": {"Ref": "AWS::AccountId"}})
        self.assertIn("web-function/*/revision/*", allow["Condition"]["ArnLike"]["aws:SourceArn"]["Fn::Sub"])


@patch("samcli.lib.bootstrap.web_function_code_bucket.click")
class TestManageWebFunctionCodeBucket(TestCase):
    @patch("samcli.lib.bootstrap.web_function_code_bucket.manage_stack")
    def test_returns_the_bucket_name(self, manage_stack_mock, click_mock):
        manage_stack_mock.return_value = StackOutput([{"OutputKey": CODE_BUCKET_OUTPUT_KEY, "OutputValue": "bkt"}])
        self.assertEqual(
            manage_web_function_code_bucket("my-app", "us-east-1", "profile"),
            ("bkt", WebFunctionCodeBucketStack("my-app").export_name),
        )
        kwargs = manage_stack_mock.call_args.kwargs
        self.assertEqual(kwargs["stack_name"], WebFunctionCodeBucketStack("my-app").stack_name)
        self.assertEqual(kwargs["region"], "us-east-1")
        self.assertEqual(kwargs["profile"], "profile")

    @patch("samcli.lib.bootstrap.web_function_code_bucket.manage_stack")
    def test_missing_output_raises(self, manage_stack_mock, click_mock):
        click_mock.ClickException = Exception
        manage_stack_mock.return_value = StackOutput([])
        with self.assertRaises(Exception):
            manage_web_function_code_bucket("my-app", "us-east-1", None)


@patch("samcli.lib.bootstrap.web_function_code_bucket.click")
class TestDeleteWebFunctionCodeBucket(TestCase):
    def _cfn(self, tags=None, outputs=None):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Tags": tags if tags is not None else [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
                    "Outputs": (
                        outputs
                        if outputs is not None
                        else [{"OutputKey": CODE_BUCKET_OUTPUT_KEY, "OutputValue": "bkt"}]
                    ),
                }
            ]
        }
        return cfn

    def test_no_code_bucket_stack(self, click_mock):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack with id my-app-WebFunctionCode does not exist"}},
            "DescribeStacks",
        )
        self.assertEqual(delete_web_function_code_bucket("my-app", cfn, MagicMock()), CODE_BUCKET_NOT_FOUND)
        cfn.delete_stack.assert_not_called()

    def test_other_describe_errors_are_raised(self, click_mock):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "not authorized"}}, "DescribeStacks"
        )
        with self.assertRaises(ClientError):
            delete_web_function_code_bucket("my-app", cfn, MagicMock())
        cfn.delete_stack.assert_not_called()

    def test_skips_stacks_not_created_by_sam_cli(self, click_mock):
        cfn = self._cfn(tags=[])
        self.assertEqual(delete_web_function_code_bucket("my-app", cfn, MagicMock()), CODE_BUCKET_NOT_FOUND)
        cfn.delete_stack.assert_not_called()

    def test_empties_the_bucket_then_deletes_the_stack(self, click_mock):
        cfn = self._cfn()
        s3 = MagicMock()
        s3.get_paginator.return_value.paginate.return_value = [
            {
                "Versions": [{"Key": "a", "VersionId": "1"}, {"Key": "a", "VersionId": "2"}],
                "DeleteMarkers": [{"Key": "b", "VersionId": "3"}],
            },
            {},
        ]
        self.assertEqual(delete_web_function_code_bucket("my-app", cfn, s3), CODE_BUCKET_DELETED)
        s3.delete_objects.assert_called_once_with(
            Bucket="bkt",
            Delete={
                "Objects": [
                    {"Key": "a", "VersionId": "1"},
                    {"Key": "a", "VersionId": "2"},
                    {"Key": "b", "VersionId": "3"},
                ],
                "Quiet": True,
            },
        )
        stack_name = WebFunctionCodeBucketStack("my-app").stack_name
        cfn.delete_stack.assert_called_once_with(StackName=stack_name)
        cfn.get_waiter.return_value.wait.assert_called_once()

    def test_already_deleted_bucket_is_ignored(self, click_mock):
        cfn = self._cfn()
        s3 = MagicMock()
        s3.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "ListObjectVersions"
        )
        self.assertEqual(delete_web_function_code_bucket("my-app", cfn, s3), CODE_BUCKET_DELETED)
        cfn.delete_stack.assert_called_once()

    def test_other_errors_while_emptying_are_raised(self, click_mock):
        cfn = self._cfn()
        s3 = MagicMock()
        s3.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListObjectVersions"
        )
        with self.assertRaises(ClientError):
            delete_web_function_code_bucket("my-app", cfn, s3)
        cfn.delete_stack.assert_not_called()


class TestRetainedWebFunctions(TestCase):
    def test_finds_retained_web_functions(self):
        template = {
            "Resources": {
                "Retained": {"Type": "AWS::Serverless::WebFunction", "DeletionPolicy": "Retain"},
                "RetainedOnCreate": {"Type": "AWS::Serverless::WebFunction", "DeletionPolicy": "RetainExceptOnCreate"},
                "Kept": {"Type": "AWS::Serverless::WebFunction"},
                "Deleted": {"Type": "AWS::Serverless::WebFunction", "DeletionPolicy": "Delete"},
                "Fn": {"Type": "AWS::Serverless::Function", "DeletionPolicy": "Retain"},
            }
        }
        self.assertEqual(retained_web_functions(template, ["KeptRevision"]), ["Retained", "RetainedOnCreate", "Kept"])
        self.assertEqual(retained_web_functions(template), ["Retained", "RetainedOnCreate"])

    def test_unreadable_templates(self):
        self.assertEqual(retained_web_functions("Hello World"), [])
        self.assertEqual(retained_web_functions(None), [])
        self.assertEqual(retained_web_functions({"Resources": "x"}), [])


@patch("samcli.lib.bootstrap.web_function_code_bucket.click")
class TestKeepWebFunctionCodeBucket(TestCase):
    def test_turns_on_termination_protection(self, click_mock):
        cfn = MagicMock()
        keep_web_function_code_bucket("my-app", ["WebFn"], cfn)
        cfn.update_termination_protection.assert_called_once_with(
            EnableTerminationProtection=True, StackName=WebFunctionCodeBucketStack("my-app").stack_name
        )
        self.assertIn("Turned on termination protection", click_mock.secho.call_args.args[0])
        self.assertIn("WebFn", click_mock.secho.call_args.args[0])

    def test_missing_code_bucket_stack_is_ignored(self, click_mock):
        cfn = MagicMock()
        cfn.update_termination_protection.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack x does not exist"}}, "UpdateTerminationProtection"
        )
        keep_web_function_code_bucket("my-app", ["WebFn"], cfn)
        click_mock.secho.assert_not_called()

    def test_protection_failure_still_keeps_and_warns(self, click_mock):
        cfn = MagicMock()
        cfn.update_termination_protection.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "UpdateTerminationProtection"
        )
        keep_web_function_code_bucket("my-app", ["WebFn"], cfn)
        self.assertIn("Couldn't turn on termination protection", click_mock.secho.call_args.args[0])

    def test_protected_code_bucket_stack_is_not_deleted(self, click_mock):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
                    "Outputs": [{"OutputKey": CODE_BUCKET_OUTPUT_KEY, "OutputValue": "bkt"}],
                    "EnableTerminationProtection": True,
                }
            ]
        }
        s3 = MagicMock()
        self.assertEqual(delete_web_function_code_bucket("my-app", cfn, s3), CODE_BUCKET_PROTECTED)
        s3.delete_objects.assert_not_called()
        cfn.delete_stack.assert_not_called()
