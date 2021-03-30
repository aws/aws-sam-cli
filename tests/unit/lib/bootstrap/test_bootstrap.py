from unittest import TestCase
from unittest.mock import patch

from samcli.commands.exceptions import UserException
from samcli.lib.bootstrap.bootstrap import manage_stack


class TestBootstrapManagedStack(TestCase):
    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_stack_missing_bucket(self, manage_cfn_stack_mock):
        manage_cfn_stack_mock.return_value = []
        with self.assertRaises(UserException):
            manage_stack("testProfile", "fakeRegion")
        manage_cfn_stack_mock.return_value = [{"OutputKey": "NotSourceBucket", "OutputValue": "AnyValue"}]
        with self.assertRaises(UserException):
            manage_stack("testProfile", "fakeRegion")

    @patch("samcli.lib.bootstrap.bootstrap.manage_cloudformation_stack")
    def test_manage_stack_happy_case(self, manage_cfn_stack_mock):
        expected_bucket_name = "BucketName"
        manage_cfn_stack_mock.return_value = [{"OutputKey": "SourceBucket", "OutputValue": expected_bucket_name}]
        actual_bucket_name = manage_stack("testProfile", "fakeRegion")
        self.assertEqual(actual_bucket_name, expected_bucket_name)
