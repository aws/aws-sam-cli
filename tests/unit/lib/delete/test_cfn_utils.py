from unittest.mock import patch, MagicMock, ANY, call
from unittest import TestCase


from samcli.commands.delete.exceptions import DeleteFailedError, FetchTemplateFailedError, CfDeleteFailedStatusError
from botocore.exceptions import ClientError, BotoCoreError, WaiterError

from samcli.lib.delete.cfn_utils import CfnUtils


class MockDeleteWaiter:
    def __init__(self, ex=None):
        self.ex = ex

    def wait(self, StackName, WaiterConfig):
        if self.ex:
            raise self.ex
        return


class TestCfUtils(TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.cloudformation_client = self.session.client("cloudformation")
        self.s3_client = self.session.client("s3")
        self.cf_utils = CfnUtils(self.cloudformation_client)
        self.waiter_config = {"Delay": 30}

    def test_cf_utils_init(self):
        self.assertEqual(self.cf_utils._client, self.cloudformation_client)

    def test_cf_utils_has_no_stack(self):
        self.cf_utils._client.describe_stacks = MagicMock(return_value={"Stacks": []})
        self.assertEqual(self.cf_utils.has_stack("test"), False)

    def test_cf_utils_has_stack_exception_non_existent(self):
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

    def test_cf_utils_has_stack_termination_protection_enabled(self):
        self.cf_utils._client.describe_stacks = MagicMock(
            return_value={"Stacks": [{"StackStatus": "CREATE_COMPLETE", "EnableTerminationProtection": True}]}
        )
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.has_stack("test")

    def test_cf_utils_has_stack_in_review(self):
        self.cf_utils._client.describe_stacks = MagicMock(
            return_value={"Stacks": [{"StackStatus": "REVIEW_IN_PROGRESS", "EnableTerminationProtection": False}]}
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

    def test_cf_utils_get_stack_template_success(self):
        self.cf_utils._client.get_template = MagicMock(return_value=({"TemplateBody": "Hello World"}))

        response = self.cf_utils.get_stack_template("test", "Original")
        self.assertEqual(response, {"TemplateBody": "Hello World"})

    def test_cf_utils_delete_stack_exception_botocore(self):
        self.cf_utils._client.delete_stack = MagicMock(side_effect=BotoCoreError())
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.delete_stack("test")

    def test_cf_utils_delete_stack_exception(self):
        self.cf_utils._client.delete_stack = MagicMock(side_effect=Exception())
        with self.assertRaises(Exception):
            self.cf_utils.delete_stack("test", ["retain_logical_id"])

    def test_cf_utils_wait_for_delete_check_waiter_config(self):
        exception = WaiterError(
            name="wait_for_delete",
            reason="unit-test",
            last_response={"Stacks": [{"Status": "Failed", "StackStatusReason": "It's a unit test stack failure"}]},
        )
        # Patch MockDeleteWaiter's wait to be Mock to get access to call_args for assertion
        with patch.object(MockDeleteWaiter, "wait", side_effect=exception):
            self.cf_utils._client.get_waiter = MagicMock(return_value=MockDeleteWaiter())
            with self.assertRaises(DeleteFailedError):
                self.cf_utils.wait_for_delete("test")
            # Assert waiter config.
            self.cf_utils._client.get_waiter.return_value.wait.assert_called_with(
                StackName="test", WaiterConfig=self.waiter_config
            )

    def test_cf_utils_wait_for_delete_exception_stack_status(self):
        self.cf_utils._client.get_waiter = MagicMock(
            return_value=MockDeleteWaiter(
                ex=WaiterError(
                    name="wait_for_delete",
                    reason="unit-test",
                    last_response={
                        "Stacks": [{"Status": "Failed", "StackStatusReason": "It's a unit test stack failure"}]
                    },
                )
            )
        )
        with self.assertRaises(DeleteFailedError) as ex:
            self.cf_utils.wait_for_delete("test")

        self.assertEqual(
            ex.exception.message,
            "Failed to delete the stack: test, "
            "msg: ex: Waiter wait_for_delete failed: unit-test, "
            "status: It's a unit test stack failure",
        )

    def test_cf_utils_wait_for_delete_exception_empty_last_response(self):
        self.cf_utils._client.get_waiter = MagicMock(
            return_value=MockDeleteWaiter(
                ex=WaiterError(
                    name="wait_for_delete",
                    reason="unit-test",
                    last_response={},
                )
            )
        )
        with self.assertRaises(DeleteFailedError) as ex:
            self.cf_utils.wait_for_delete("test")

        self.assertEqual(
            ex.exception.message,
            "Failed to delete the stack: test, msg: ex: Waiter wait_for_delete failed: unit-test",
        )

    def test_cf_utils_wait_for_delete_exception(self):
        self.cf_utils._client.get_waiter = MagicMock(
            return_value=MockDeleteWaiter(
                ex=WaiterError(
                    name="wait_for_delete",
                    reason="unit-test",
                    last_response={"Status": "Failed", "StatusReason": "It's a unit test"},
                )
            )
        )
        with self.assertRaises(DeleteFailedError):
            self.cf_utils.wait_for_delete("test")

    def test_cf_utils_wait_for_delete_failed_status(self):
        self.cf_utils._client.get_waiter = MagicMock(
            return_value=MockDeleteWaiter(
                ex=WaiterError(
                    name="wait_for_delete",
                    reason="DELETE_FAILED ",
                    last_response={"Status": "Failed", "StatusReason": "It's a unit test"},
                )
            )
        )
        with self.assertRaises(CfDeleteFailedStatusError):
            self.cf_utils.wait_for_delete("test")
