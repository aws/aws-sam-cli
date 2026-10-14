from unittest import TestCase
from unittest.mock import patch, MagicMock

from samcli.commands.exceptions import UserException, AWSServiceClientError
import json

from botocore.exceptions import ClientError

from samcli.lib.bootstrap.bootstrap import (
    WEB_FUNCTION_CODE_ACCESS_SID,
    _get_stack_template,
    manage_stack,
    StackOutput,
    get_current_account_id,
    stacks_need_web_function_code_access,
    template_file_has_web_functions,
    template_has_web_functions,
)


class TestBootstrapManagedStack(TestCase):
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_stack_missing_bucket(self, manage_cfn_stack_mock):
        manage_cfn_stack_mock.return_value = StackOutput(stack_output=[])
        with self.assertRaises(UserException):
            manage_stack("testProfile", "fakeRegion")
        manage_cfn_stack_mock.return_value = StackOutput(
            stack_output=[{"OutputKey": "NotSourceBucket", "OutputValue": "AnyValue"}]
        )
        with self.assertRaises(UserException):
            manage_stack("testProfile", "fakeRegion")

    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_manage_stack_happy_case(self, manage_cfn_stack_mock):
        expected_bucket_name = "BucketName"
        manage_cfn_stack_mock.return_value = StackOutput(
            stack_output=[{"OutputKey": "SourceBucket", "OutputValue": expected_bucket_name}]
        )
        actual_bucket_name = manage_stack("testProfile", "fakeRegion")
        self.assertEqual(actual_bucket_name, expected_bucket_name)

    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    def test_get_current_account_id(self, boto3_mock):
        session_mock = boto3_mock.Session.return_value = MagicMock()
        sts_mock = MagicMock()
        sts_mock.get_caller_identity.return_value = {"Account": 1234567890}
        session_mock.client.return_value = sts_mock
        account_id = get_current_account_id()
        self.assertEqual(account_id, 1234567890)

    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    def test_get_current_account_id_missing_id(self, boto3_mock):
        session_mock = boto3_mock.Session.return_value = MagicMock()
        sts_mock = MagicMock()
        sts_mock.get_caller_identity.return_value = {}
        session_mock.client.return_value = sts_mock
        with self.assertRaises(AWSServiceClientError):
            get_current_account_id()


class TestBootstrapWebFunctionCodeAccess(TestCase):
    def test_stack_template_allows_lambda_to_read_web_function_code(self):
        statements = json.loads(_get_stack_template())["Resources"]["SamCliSourceBucketBucketPolicy"]["Properties"][
            "PolicyDocument"
        ]["Statement"]
        statement = next(s for s in statements if s.get("Sid") == WEB_FUNCTION_CODE_ACCESS_SID)
        self.assertEqual(statement["Principal"], {"Service": "lambda.amazonaws.com"})
        self.assertEqual(statement["Action"], ["s3:GetObject", "s3:GetObjectVersion"])
        self.assertEqual(statement["Condition"]["StringEquals"], {"aws:SourceAccount": {"Ref": "AWS::AccountId"}})
        self.assertIn("web-function/*/revision/*", statement["Condition"]["ArnLike"]["aws:SourceArn"]["Fn::Sub"])

    def test_template_has_web_functions(self):
        self.assertTrue(template_has_web_functions({"Resources": {"Fn": {"Type": "AWS::Serverless::WebFunction"}}}))
        self.assertFalse(template_has_web_functions({"Resources": {"Fn": {"Type": "AWS::Serverless::Function"}}}))
        self.assertFalse(template_has_web_functions({}))
        self.assertFalse(template_has_web_functions(None))

    @patch("samcli.lib.providers.sam_stack_provider.SamLocalStackProvider.get_stacks")
    def test_template_file_has_web_functions(self, get_stacks_mock):
        root = MagicMock(resources={"App": {"Type": "AWS::Serverless::Application"}})
        child = MagicMock(resources={"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}})
        get_stacks_mock.return_value = ([root, child], [])
        self.assertTrue(template_file_has_web_functions("template.yaml"))
        get_stacks_mock.return_value = ([root], [])
        self.assertFalse(template_file_has_web_functions("template.yaml"))
        get_stacks_mock.side_effect = Exception("unreadable")
        self.assertFalse(template_file_has_web_functions("template.yaml"))
        self.assertFalse(template_file_has_web_functions(None))

    @patch("samcli.lib.bootstrap.bootstrap.update_cloudformation_stack")
    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_updates_managed_stack_without_web_function_code_access(self, manage_mock, boto3_mock, update_mock):
        manage_mock.return_value = StackOutput(stack_output=[{"OutputKey": "SourceBucket", "OutputValue": "bucket"}])
        boto3_mock.client.return_value.get_template.return_value = {"TemplateBody": '{"Resources": {}}'}
        self.assertEqual(manage_stack("profile", "us-east-1", web_function_code_access=True), "bucket")
        update_mock.assert_called_once()
        self.assertIn(WEB_FUNCTION_CODE_ACCESS_SID, update_mock.call_args.kwargs["template_body"])

    @patch("samcli.lib.bootstrap.bootstrap.update_cloudformation_stack")
    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_skips_update_when_managed_stack_has_web_function_code_access(self, manage_mock, boto3_mock, update_mock):
        manage_mock.return_value = StackOutput(stack_output=[{"OutputKey": "SourceBucket", "OutputValue": "bucket"}])
        boto3_mock.client.return_value.get_template.return_value = {"TemplateBody": _get_stack_template()}
        manage_stack("profile", "us-east-1", web_function_code_access=True)
        update_mock.assert_not_called()

    @patch("samcli.lib.bootstrap.bootstrap.update_cloudformation_stack")
    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_skips_check_without_web_functions(self, manage_mock, boto3_mock, update_mock):
        manage_mock.return_value = StackOutput(stack_output=[{"OutputKey": "SourceBucket", "OutputValue": "bucket"}])
        manage_stack("profile", "us-east-1")
        boto3_mock.client.assert_not_called()
        update_mock.assert_not_called()

    @patch("samcli.lib.bootstrap.bootstrap.update_cloudformation_stack")
    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_update_failure_raises_user_exception(self, manage_mock, boto3_mock, update_mock):
        manage_mock.return_value = StackOutput(stack_output=[{"OutputKey": "SourceBucket", "OutputValue": "bucket"}])
        boto3_mock.client.return_value.get_template.return_value = {"TemplateBody": '{"Resources": {}}'}
        update_mock.side_effect = Exception("AccessDenied")
        with self.assertRaises(UserException):
            manage_stack("profile", "us-east-1", web_function_code_access=True)

    @patch("samcli.lib.bootstrap.bootstrap.boto3")
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_get_template_failure_raises(self, manage_mock, boto3_mock):
        manage_mock.return_value = StackOutput(stack_output=[{"OutputKey": "SourceBucket", "OutputValue": "bucket"}])
        boto3_mock.client.return_value.get_template.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetTemplate"
        )
        with self.assertRaises(AWSServiceClientError):
            manage_stack("profile", "us-east-1", web_function_code_access=True)

    def test_stacks_need_web_function_code_access(self):
        stack = MagicMock(resources={"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}})
        self.assertTrue(stacks_need_web_function_code_access([stack]))
        self.assertFalse(stacks_need_web_function_code_access(MagicMock(__iter__=None)))
