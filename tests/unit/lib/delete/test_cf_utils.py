from unittest.mock import patch, MagicMock, ANY, call
from unittest import TestCase

from samcli.commands.delete.exceptions import DeleteFailedError, FetchTemplateFailedError
from botocore.exceptions import ClientError, BotoCoreError
from samcli.lib.delete.cf_utils import CfUtils


class TestCfUtils(TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.cloudformation_client = self.session.client("cloudformation")
        self.s3_client = self.session.client("s3")
        self.cf_utils = CfUtils(self.cloudformation_client)

    def test_cf_utils_init(self):
        self.assertEqual(self.cf_utils._client, self.cloudformation_client)

    def test_cf_utils_has_no_stack(self):
        self.cf_utils._client.describe_stacks = MagicMock(return_value={"Stacks": []})
        self.assertEqual(self.cf_utils.has_stack("test"), False)

    def test_cf_utils_has_stack_exception_non_exsistent(self):
        self.cf_utils._client.describe_stacks = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "Stack with id test does not exist"}},
                operation_name="stack_status",
            )
        )
        self.assertEqual(self.cf_utils.has_stack("test"), False)

    def test_cf_utils_has_stack_exception_client_error(self):
        self.cf_utils._client.describe_stacks = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "Error: The security token included in the request is expired"}},
                operation_name="stack_status",
            )
        )
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.has_stack("test")

    def test_cf_utils_has_stack_exception(self):
        self.cf_utils._client.describe_stacks = MagicMock(side_effect=Exception())
        with self.assertRaises(Exception):
            self.cf_utils.has_stack("test")

    def test_cf_utils_has_stack_in_review(self):
        self.cf_utils._client.describe_stacks = MagicMock(
            return_value={"Stacks": [{"StackStatus": "REVIEW_IN_PROGRESS"}]}
        )
        self.assertEqual(self.cf_utils.has_stack("test"), False)

    def test_cf_utils_has_stack_exception_botocore(self):
        self.cf_utils._client.describe_stacks = MagicMock(side_effect=BotoCoreError())
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.has_stack("test")

    def test_cf_utils_get_stack_template_exception_client_error(self):
        self.cf_utils._client.get_template = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "Stack with id test does not exist"}},
                operation_name="stack_status",
            )
        )
        with self.assertRaises(FetchTemplateFailedError):
            self.cf_utils.get_stack_template("test", "Original")

    def test_cf_utils_get_stack_template_exception_botocore(self):
        self.cf_utils._client.get_template = MagicMock(side_effect=BotoCoreError())
        with self.assertRaises(FetchTemplateFailedError):
            self.cf_utils.get_stack_template("test", "Original")

    def test_cf_utils_get_stack_template_exception(self):
        self.cf_utils._client.get_template = MagicMock(side_effect=Exception())
        with self.assertRaises(Exception):
            self.cf_utils.get_stack_template("test", "Original")

    def test_cf_utils_delete_stack_exception_botocore(self):
        self.cf_utils._client.delete_stack = MagicMock(side_effect=BotoCoreError())
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.delete_stack("test")

    def test_cf_utils_delete_stack_exception(self):
        self.cf_utils._client.delete_stack = MagicMock(side_effect=Exception())
        with self.assertRaises(Exception):
            self.cf_utils.delete_stack("test")
