import uuid
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch, MagicMock, ANY

import pytz
from botocore.exceptions import ClientError, WaiterError

from samcli.commands.deploy.exceptions import DeployFailedError, ChangeSetError
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.package.s3_uploader import S3Uploader


class MockPaginator:
    def __init__(self, resp):
        self.resp = resp

    def paginate(self, ChangeSetName, StackName):
        return self.resp


class MockChangesetWaiter:
    def __init__(self, ex=None):
        self.ex = ex

    def wait(self, ChangeSetName, StackName, WaiterConfig):
        if self.ex:
            raise self.ex
        return


class MockCreateUpdateWaiter:
    def __init__(self, ex=None):
        self.ex = ex

    def wait(self, StackName, WaiterConfig):
        if self.ex:
            raise self.ex
        return


class TestDeployer(TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.cloudformation_client = self.session.client("cloudformation")
        self.s3_client = self.session.client("s3")
        self.deployer = Deployer(self.cloudformation_client)

    def test_deployer_init(self):
        self.assertEqual(self.deployer._client, self.cloudformation_client)
        self.assertEqual(self.deployer.changeset_prefix, "samcli-cloudformation-package-deploy-")

    def test_deployer_has_no_stack(self):
        self.deployer._client.describe_stacks = MagicMock(return_value={"Stacks": []})
        self.assertEqual(self.deployer.has_stack("test"), False)

    def test_deployer_has_stack_in_review(self):
        self.deployer._client.describe_stacks = MagicMock(
            return_value={"Stacks": [{"StackStatus": "REVIEW_IN_PROGRESS"}]}
        )
        self.assertEqual(self.deployer.has_stack("test"), False)

    def test_deployer_has_stack_exception_non_exsistent(self):
        self.deployer._client.describe_stacks = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "Stack with id test does not exist"}},
                operation_name="stack_status",
            )
        )
        self.assertEqual(self.deployer.has_stack("test"), False)

    def test_deployer_has_stack_exception(self):
        self.deployer._client.describe_stacks = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Message": "Error"}}, operation_name="stack_status")
        )
        with self.assertRaises(ClientError):
            self.deployer.has_stack("test")

    def test_create_changeset(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer.create_changeset(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
                {"ParameterKey": "c", "UsePreviousValue": True},
            ],
            capabilities=["CAPABILITY_IAM"],
            role_arn="role-arn",
            notification_arns=[],
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )

        self.assertEqual(self.deployer._client.create_change_set.call_count, 1)
        self.deployer._client.create_change_set.assert_called_with(
            Capabilities=["CAPABILITY_IAM"],
            ChangeSetName=ANY,
            ChangeSetType="CREATE",
            Description=ANY,
            NotificationARNs=[],
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            RoleARN="role-arn",
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )

    def test_update_changeset(self):
        self.deployer.has_stack = MagicMock(return_value=True)
        self.deployer.create_changeset(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
                {"ParameterKey": "c", "UsePreviousValue": True},
            ],
            capabilities=["CAPABILITY_IAM"],
            role_arn="role-arn",
            notification_arns=[],
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )

        self.assertEqual(self.deployer._client.create_change_set.call_count, 1)
        self.deployer._client.create_change_set.assert_called_with(
            Capabilities=["CAPABILITY_IAM"],
            ChangeSetName=ANY,
            ChangeSetType="UPDATE",
            Description=ANY,
            NotificationARNs=[],
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            RoleARN="role-arn",
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )

    def test_create_changeset_exception(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer._client.create_change_set = MagicMock(side_effect=Exception)
        with self.assertRaises(ChangeSetError):
            self.deployer.create_changeset(
                stack_name="test",
                cfn_template=" ",
                parameter_values=[
                    {"ParameterKey": "a", "ParameterValue": "b"},
                    {"ParameterKey": "c", "UsePreviousValue": True},
                ],
                capabilities=["CAPABILITY_IAM"],
                role_arn="role-arn",
                notification_arns=[],
                s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
                tags={"unit": "true"},
            )

    def test_describe_changeset(self):
        response = [
            {
                "Changes": [
                    {"ResourceChange": {"LogicalResourceId": "resource_id1", "ResourceType": "s3", "Action": "Add"}}
                ]
            },
            {
                "Changes": [
                    {"ResourceChange": {"LogicalResourceId": "resource_id2", "ResourceType": "kms", "Action": "Add"}}
                ]
            },
            {
                "Changes": [
                    {"ResourceChange": {"LogicalResourceId": "resource_id3", "ResourceType": "lambda", "Action": "Add"}}
                ]
            },
        ]
        self.deployer._client.get_paginator = MagicMock(return_value=MockPaginator(resp=response))
        changes = self.deployer.describe_changeset("change_id", "test")
        self.assertEqual(
            changes,
            {
                "Add": [
                    {"LogicalResourceId": "resource_id1", "ResourceType": "s3"},
                    {"LogicalResourceId": "resource_id2", "ResourceType": "kms"},
                    {"LogicalResourceId": "resource_id3", "ResourceType": "lambda"},
                ],
                "Modify": [],
                "Remove": [],
            },
        )

    def test_wait_for_changeset(self):
        self.deployer._client.get_waiter = MagicMock(return_value=MockChangesetWaiter())
        self.deployer.wait_for_changeset("test-id", "test-stack")

    def test_wait_for_changeset_exception_ChangeEmpty(self):
        self.deployer._client.get_waiter = MagicMock(
            return_value=MockChangesetWaiter(
                ex=WaiterError(
                    name="wait_for_changeset",
                    reason="unit-test",
                    last_response={"Status": "Failed", "StatusReason": "It's a unit test"},
                )
            )
        )
        with self.assertRaises(ChangeSetError):
            self.deployer.wait_for_changeset("test-id", "test-stack")

    def test_execute_changeset(self):
        self.deployer.execute_changeset("id", "test")
        self.deployer._client.execute_change_set.assert_called_with(ChangeSetName="id", StackName="test")

    def test_get_last_event_time(self):
        timestamp = pytz.utc.localize(datetime.utcnow())
        self.deployer._client.describe_stack_events = MagicMock(
            return_value={"StackEvents": [{"Timestamp": timestamp}]}
        )
        self.assertEqual(self.deployer.get_last_event_time("test"), timestamp)

    def test_get_last_event_time_unknown_last_time(self):
        current_timestamp = pytz.utc.localize(datetime.utcnow())
        self.deployer._client.describe_stack_events = MagicMock(side_effect=KeyError)
        last_stack_event_timestamp = self.deployer.get_last_event_time("test")
        self.assertEqual(last_stack_event_timestamp.year, current_timestamp.year)
        self.assertEqual(last_stack_event_timestamp.month, current_timestamp.month)
        self.assertEqual(last_stack_event_timestamp.day, current_timestamp.day)
        self.assertEqual(last_stack_event_timestamp.hour, current_timestamp.hour)
        self.assertEqual(last_stack_event_timestamp.minute, current_timestamp.minute)
        self.assertEqual(last_stack_event_timestamp.second, current_timestamp.second)

    @patch("time.sleep")
    def test_describe_stack_events(self, patched_time):
        current_timestamp = pytz.utc.localize(datetime.utcnow())

        self.deployer._client.describe_stacks = MagicMock(
            side_effect=[
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE_CLEANUP_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            ]
        )

        self.deployer._client.describe_stack_events = MagicMock(
            side_effect=[
                {
                    "StackEvents": [
                        {
                            "EventId": str(uuid.uuid4()),
                            "Timestamp": current_timestamp,
                            "ResourceStatus": "CREATE_IN_PROGRESS",
                            "ResourceType": "s3",
                            "LogicalResourceId": "mybucket",
                        }
                    ]
                },
                {
                    "StackEvents": [
                        {
                            "EventId": str(uuid.uuid4()),
                            "Timestamp": current_timestamp,
                            "ResourceStatus": "CREATE_IN_PROGRESS",
                            "ResourceType": "kms",
                            "LogicalResourceId": "mykms",
                        }
                    ]
                },
                {
                    "StackEvents": [
                        {
                            "EventId": str(uuid.uuid4()),
                            "Timestamp": current_timestamp,
                            "ResourceStatus": "CREATE_COMPLETE",
                            "ResourceType": "s3",
                            "LogicalResourceId": "mybucket",
                        }
                    ]
                },
                {
                    "StackEvents": [
                        {
                            "EventId": str(uuid.uuid4()),
                            "Timestamp": current_timestamp,
                            "ResourceStatus": "CREATE_COMPLETE",
                            "ResourceType": "kms",
                            "LogicalResourceId": "mykms",
                        }
                    ]
                },
            ]
        )

        self.deployer.describe_stack_events("test", current_timestamp - timedelta(seconds=1))

    def test_check_stack_status(self):
        self.assertEqual(self.deployer._check_stack_complete("CREATE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_complete("CREATE_FAILED"), False)
        self.assertEqual(self.deployer._check_stack_complete("CREATE_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("DELETE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_complete("DELETE_FAILED"), False)
        self.assertEqual(self.deployer._check_stack_complete("DELETE_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("REVIEW_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("ROLLBACK_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_complete("ROLLBACK_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_COMPLETE_CLEANUP_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_ROLLBACK_FAILED"), False)
        self.assertEqual(self.deployer._check_stack_complete("UPDATE_ROLLBACK_IN_PROGRESS"), False)

    @patch("time.sleep")
    def test_wait_for_execute(self, patched_time):
        self.deployer.describe_stack_events = MagicMock()
        self.deployer._client.get_waiter = MagicMock(return_value=MockCreateUpdateWaiter())
        self.deployer.wait_for_execute("test", "CREATE")
        self.deployer.wait_for_execute("test", "UPDATE")
        with self.assertRaises(RuntimeError):
            self.deployer.wait_for_execute("test", "DESTRUCT")

        self.deployer._client.get_waiter = MagicMock(
            return_value=MockCreateUpdateWaiter(
                ex=WaiterError(
                    name="create_changeset",
                    reason="unit-test",
                    last_response={"Status": "Failed", "StatusReason": "It's a unit test"},
                )
            )
        )
        with self.assertRaises(DeployFailedError):
            self.deployer.wait_for_execute("test", "CREATE")

    def test_create_and_wait_for_changeset(self):
        self.deployer.create_changeset = MagicMock(return_value=({"Id": "test"}, "create"))
        self.deployer.wait_for_changeset = MagicMock()
        self.deployer.describe_changeset = MagicMock()

        result = self.deployer.create_and_wait_for_changeset(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
                {"ParameterKey": "c", "UsePreviousValue": True},
            ],
            capabilities=["CAPABILITY_IAM"],
            role_arn="role-arn",
            notification_arns=[],
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )

        self.assertEqual(result, ({"Id": "test"}, "create"))

    def test_create_and_wait_for_changeset_exception(self):
        self.deployer.create_changeset = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "Something Wrong"}}, operation_name="create_changeset"
            )
        )
        with self.assertRaises(DeployFailedError):
            self.deployer.create_and_wait_for_changeset(
                stack_name="test",
                cfn_template=" ",
                parameter_values=[
                    {"ParameterKey": "a", "ParameterValue": "b"},
                    {"ParameterKey": "c", "UsePreviousValue": True},
                ],
                capabilities=["CAPABILITY_IAM"],
                role_arn="role-arn",
                notification_arns=[],
                s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
                tags={"unit": "true"},
            )
