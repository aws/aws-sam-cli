from unittest import TestCase
from unittest.mock import patch, MagicMock

from samcli.commands.exceptions import UserException, CredentialsError
from samcli.lib.bootstrap.bootstrap import manage_stack, StackOutput, get_current_account_id


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
        with self.assertRaises(CredentialsError):
            get_current_account_id()
