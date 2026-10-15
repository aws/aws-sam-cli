import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from samcli.lib.bootstrap.web_function_code_bucket import (
    CODE_BUCKET_OUTPUT_KEY,
    WebFunctionCodeBucketStack,
    delete_web_function_code_bucket,
    get_code_bucket_template,
    manage_web_function_code_bucket,
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
        resources = json.loads(get_code_bucket_template("my-app"))["Resources"]
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
        self.assertEqual(manage_web_function_code_bucket("my-app", "us-east-1", "profile"), "bkt")
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
        cfn.describe_stacks.side_effect = ClientError({"Error": {"Code": "ValidationError"}}, "DescribeStacks")
        self.assertFalse(delete_web_function_code_bucket("my-app", cfn, MagicMock()))
        cfn.delete_stack.assert_not_called()

    def test_skips_stacks_not_created_by_sam_cli(self, click_mock):
        cfn = self._cfn(tags=[])
        self.assertFalse(delete_web_function_code_bucket("my-app", cfn, MagicMock()))
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
        self.assertTrue(delete_web_function_code_bucket("my-app", cfn, s3))
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
        self.assertTrue(delete_web_function_code_bucket("my-app", cfn, s3))
        cfn.delete_stack.assert_called_once()
