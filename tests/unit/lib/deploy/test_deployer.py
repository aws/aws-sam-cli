from logging import captureWarnings
import uuid
import time
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch, MagicMock, ANY, call

from botocore.exceptions import ClientError, WaiterError, BotoCoreError

from samcli.commands.deploy.exceptions import (
    DeployFailedError,
    ChangeSetError,
    DeployStackOutPutFailedError,
    DeployBucketInDifferentRegionError,
)
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.time import utc_to_timestamp, to_datetime


class MockPaginator:
    def __init__(self, resp):
        self.resp = resp

    def paginate(self, ChangeSetName=None, StackName=None):
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
        self.assertEqual(self.deployer.changeset_prefix, "samcli-deploy")

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
        self.deployer._client.describe_stacks = MagicMock(side_effect=Exception())
        with self.assertRaises(Exception):
            self.deployer.has_stack("test")

    def test_deployer_has_stack_exception_botocore(self):
        self.deployer._client.describe_stacks = MagicMock(side_effect=BotoCoreError())
        with self.assertRaises(DeployFailedError):
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

    def test_create_changeset_ClientErrorException(self):
        error_message = (
            "An error occurred (ValidationError) when calling the CreateChangeSet "
            "operation: S3 error: The bucket you are attempting to access must be "
            "addressed using the specified endpoint. "
            "Please send all future requests to this "
            "endpoint.\nFor more information "
            "check http://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html"
        )
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer._client.create_change_set = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": error_message}}, operation_name="create_changeset"
            )
        )
        with self.assertRaises(DeployBucketInDifferentRegionError):
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

    def test_create_changeset_ClientErrorException_generic(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer._client.create_change_set = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Message": "Message"}}, operation_name="create_changeset")
        )
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

    def test_create_changeset_pass_through_optional_arguments_only_if_having_values(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        # assert that the arguments; Capabilities, RoleARN & NotificationARNs are passed through if having values
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
        self.deployer._client.create_change_set.assert_called_with(
            Capabilities=["CAPABILITY_IAM"],
            RoleARN="role-arn",
            NotificationARNs=[],
            ChangeSetName=ANY,
            ChangeSetType="CREATE",
            Description=ANY,
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )
        # assert that the arguments; Capabilities, RoleARN & NotificationARNs are not passed through if no values
        self.deployer.create_changeset(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
                {"ParameterKey": "c", "UsePreviousValue": True},
            ],
            capabilities=None,
            role_arn=None,
            notification_arns=None,
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )
        self.deployer._client.create_change_set.assert_called_with(
            ChangeSetName=ANY,
            ChangeSetType="CREATE",
            Description=ANY,
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )

    def test_describe_changeset_with_changes(self):
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
                    {"LogicalResourceId": "resource_id1", "ResourceType": "s3", "Replacement": "N/A"},
                    {"LogicalResourceId": "resource_id2", "ResourceType": "kms", "Replacement": "N/A"},
                    {"LogicalResourceId": "resource_id3", "ResourceType": "lambda", "Replacement": "N/A"},
                ],
                "Modify": [],
                "Remove": [],
            },
        )

    def test_describe_changeset_with_no_changes(self):
        response = [{"Changes": []}]
        self.deployer._client.get_paginator = MagicMock(return_value=MockPaginator(resp=response))
        changes = self.deployer.describe_changeset("change_id", "test")
        self.assertEqual(changes, {"Add": [], "Modify": [], "Remove": []})

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
        self.deployer.execute_changeset("id", "test", True)
        self.deployer._client.execute_change_set.assert_called_with(
            ChangeSetName="id", StackName="test", DisableRollback=True
        )

    def test_execute_changeset_exception(self):
        self.deployer._client.execute_change_set = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Message": "Error"}}, operation_name="execute_changeset")
        )
        with self.assertRaises(DeployFailedError):
            self.deployer.execute_changeset("id", "test", True)

    def test_get_last_event_time(self):
        timestamp = datetime.utcnow()
        self.deployer._client.describe_stack_events = MagicMock(
            return_value={"StackEvents": [{"Timestamp": timestamp}]}
        )
        self.assertEqual(self.deployer.get_last_event_time("test"), utc_to_timestamp(timestamp))

    def test_get_last_event_time_unknown_last_time(self):
        current_timestamp = datetime.utcnow()
        self.deployer._client.describe_stack_events = MagicMock(side_effect=KeyError)
        # Convert to milliseconds from seconds
        last_stack_event_timestamp = to_datetime(self.deployer.get_last_event_time("test") * 1000)
        self.assertEqual(last_stack_event_timestamp.year, current_timestamp.year)
        self.assertEqual(last_stack_event_timestamp.month, current_timestamp.month)
        self.assertEqual(last_stack_event_timestamp.day, current_timestamp.day)
        self.assertEqual(last_stack_event_timestamp.hour, current_timestamp.hour)
        self.assertEqual(last_stack_event_timestamp.minute, current_timestamp.minute)
        self.assertEqual(last_stack_event_timestamp.second, current_timestamp.second)

    @patch("time.sleep")
    def test_describe_stack_events(self, patched_time):
        current_timestamp = datetime.utcnow()

        self.deployer._client.describe_stacks = MagicMock(
            side_effect=[
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE_CLEANUP_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            ]
        )
        self.deployer._client.get_paginator = MagicMock(
            return_value=MockPaginator(
                [
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
        )

        self.deployer.describe_stack_events("test", time.time() - 1)

    @patch("time.sleep")
    @patch("samcli.lib.deploy.deployer.pprint_columns")
    def test_describe_stack_events_skip_old_event(self, patched_pprint_columns, patched_time):
        current_timestamp = datetime.utcnow()

        self.deployer._client.describe_stacks = MagicMock(
            side_effect=[
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE_CLEANUP_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            ]
        )
        sample_events = [
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
                        "Timestamp": current_timestamp + timedelta(seconds=10),
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
                        "Timestamp": current_timestamp + timedelta(seconds=20),
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
                        "Timestamp": current_timestamp + timedelta(seconds=30),
                        "ResourceStatus": "CREATE_COMPLETE",
                        "ResourceType": "kms",
                        "LogicalResourceId": "mykms",
                    }
                ]
            },
        ]
        invalid_event = {"StackEvents": [{}]}  # if deployer() loop read this, KeyError would raise
        self.deployer._client.get_paginator = MagicMock(
            side_effect=[
                MockPaginator([sample_events[0]]),
                MockPaginator([sample_events[1], sample_events[0], invalid_event]),
                MockPaginator([sample_events[2], sample_events[1], invalid_event]),
                MockPaginator([sample_events[3], sample_events[2], invalid_event]),
            ]
        )

        self.deployer.describe_stack_events("test", time.time() - 1)
        self.assertEqual(patched_pprint_columns.call_count, 4)

    @patch("samcli.lib.deploy.deployer.math")
    @patch("time.sleep")
    def test_describe_stack_events_exceptions(self, patched_time, patched_math):

        self.deployer._client.describe_stacks = MagicMock(
            side_effect=[
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
            ]
        )
        # No exception raised, we return with a log message, this is because,
        # the changeset is still getting executed, but displaying them is getting throttled.
        self.deployer.describe_stack_events("test", time.time())
        self.assertEqual(patched_math.pow.call_count, 3)
        self.assertEqual(patched_math.pow.call_args_list, [call(2, 1), call(2, 2), call(2, 3)])

    @patch("samcli.lib.deploy.deployer.math")
    @patch("time.sleep")
    def test_describe_stack_events_resume_after_exceptions(self, patched_time, patched_math):
        current_timestamp = datetime.utcnow()

        self.deployer._client.describe_stacks = MagicMock(
            side_effect=[
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                ClientError(
                    error_response={"Error": {"Message": "Rate Exceeded"}}, operation_name="describe_stack_events"
                ),
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE_CLEANUP_IN_PROGRESS"}]},
                {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            ]
        )

        self.deployer._client.get_paginator = MagicMock(
            return_value=MockPaginator(
                [
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
        )

        self.deployer.describe_stack_events("test", time.time())
        self.assertEqual(patched_math.pow.call_count, 3)
        self.assertEqual(patched_math.pow.call_args_list, [call(2, 1), call(2, 2), call(2, 3)])

    def test_check_stack_status(self):
        self.assertEqual(self.deployer._check_stack_not_in_progress("CREATE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("CREATE_FAILED"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("CREATE_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_not_in_progress("DELETE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("DELETE_FAILED"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("DELETE_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_not_in_progress("REVIEW_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_not_in_progress("ROLLBACK_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("ROLLBACK_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_not_in_progress("UPDATE_COMPLETE"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("UPDATE_COMPLETE_CLEANUP_IN_PROGRESS"), False)
        self.assertEqual(self.deployer._check_stack_not_in_progress("UPDATE_IN_PROGRESS"), False)
        self.assertEqual(
            self.deployer._check_stack_not_in_progress("UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS"), False
        )
        self.assertEqual(self.deployer._check_stack_not_in_progress("UPDATE_ROLLBACK_FAILED"), True)
        self.assertEqual(self.deployer._check_stack_not_in_progress("UPDATE_ROLLBACK_IN_PROGRESS"), False)

    @patch("time.sleep")
    def test_wait_for_execute(self, patched_time):
        self.deployer.describe_stack_events = MagicMock()
        self.deployer._client.get_waiter = MagicMock(return_value=MockCreateUpdateWaiter())
        self.deployer.wait_for_execute("test", "CREATE", False)
        self.deployer.wait_for_execute("test", "UPDATE", True)
        with self.assertRaises(RuntimeError):
            self.deployer.wait_for_execute("test", "DESTRUCT", False)

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
            self.deployer.wait_for_execute("test", "CREATE", False)

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

    def test_get_stack_outputs(self):
        outputs = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "Key1", "OutputValue": "Value1", "Description": "output for s3"},
                        {"OutputKey": "Key2", "OutputValue": "Value2", "Description": "output for kms"},
                    ]
                }
            ]
        }
        self.deployer._client.describe_stacks = MagicMock(return_value=outputs)

        self.assertEqual(outputs["Stacks"][0]["Outputs"], self.deployer.get_stack_outputs(stack_name="test"))
        self.deployer._client.describe_stacks.assert_called_with(StackName="test")

    @patch("samcli.lib.deploy.deployer.pprint_columns")
    def test_get_stack_outputs_no_echo(self, mock_pprint_columns):
        outputs = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "Key1", "OutputValue": "Value1", "Description": "output for s3"},
                        {"OutputKey": "Key2", "OutputValue": "Value2", "Description": "output for kms"},
                    ]
                }
            ]
        }
        self.deployer._client.describe_stacks = MagicMock(return_value=outputs)

        self.assertEqual(
            outputs["Stacks"][0]["Outputs"], self.deployer.get_stack_outputs(stack_name="test", echo=False)
        )
        self.deployer._client.describe_stacks.assert_called_with(StackName="test")
        self.assertEqual(mock_pprint_columns.call_count, 0)

    def test_get_stack_outputs_no_outputs_no_exception(self):
        outputs = {"Stacks": [{"SomeOtherKey": "Value"}]}
        self.deployer._client.describe_stacks = MagicMock(return_value=outputs)

        self.assertEqual(None, self.deployer.get_stack_outputs(stack_name="test"))
        self.deployer._client.describe_stacks.assert_called_with(StackName="test")

    def test_get_stack_outputs_exception(self):
        self.deployer._client.describe_stacks = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Message": "Error"}}, operation_name="describe_stacks")
        )

        with self.assertRaises(DeployStackOutPutFailedError):
            self.deployer.get_stack_outputs(stack_name="test")

    @patch("time.sleep")
    def test_wait_for_execute_no_outputs(self, patched_time):
        self.deployer.describe_stack_events = MagicMock()
        self.deployer._client.get_waiter = MagicMock(return_value=MockCreateUpdateWaiter())
        self.deployer._display_stack_outputs = MagicMock()
        self.deployer.get_stack_outputs = MagicMock(return_value=None)
        self.deployer.wait_for_execute("test", "CREATE", False)
        self.assertEqual(self.deployer._display_stack_outputs.call_count, 0)

    @patch("time.sleep")
    def test_wait_for_execute_with_outputs(self, patched_time):
        self.deployer.describe_stack_events = MagicMock()
        outputs = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "Key1", "OutputValue": "Value1", "Description": "output for s3"},
                        {"OutputKey": "Key2", "OutputValue": "Value2", "Description": "output for kms"},
                    ]
                }
            ]
        }
        self.deployer._client.get_waiter = MagicMock(return_value=MockCreateUpdateWaiter())
        self.deployer._display_stack_outputs = MagicMock()
        self.deployer.get_stack_outputs = MagicMock(return_value=outputs["Stacks"][0]["Outputs"])
        self.deployer.wait_for_execute("test", "CREATE", False)
        self.assertEqual(self.deployer._display_stack_outputs.call_count, 1)

    def test_sync_update_stack(self):
        self.deployer.has_stack = MagicMock(return_value=True)
        self.deployer.wait_for_execute = MagicMock()
        self.deployer.sync(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
            ],
            capabilities=["CAPABILITY_IAM"],
            role_arn="role-arn",
            notification_arns=[],
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )

        self.assertEqual(self.deployer._client.update_stack.call_count, 1)
        self.deployer._client.update_stack.assert_called_with(
            Capabilities=["CAPABILITY_IAM"],
            NotificationARNs=[],
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            RoleARN="role-arn",
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )

    def test_sync_update_stack_exception(self):
        self.deployer.has_stack = MagicMock(return_value=True)
        self.deployer.wait_for_execute = MagicMock()
        self.deployer._client.update_stack = MagicMock(side_effect=Exception)
        with self.assertRaises(DeployFailedError):
            self.deployer.sync(
                stack_name="test",
                cfn_template=" ",
                parameter_values=[
                    {"ParameterKey": "a", "ParameterValue": "b"},
                ],
                capabilities=["CAPABILITY_IAM"],
                role_arn="role-arn",
                notification_arns=[],
                s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
                tags={"unit": "true"},
            )

    def test_sync_create_stack(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer.wait_for_execute = MagicMock()
        self.deployer.sync(
            stack_name="test",
            cfn_template=" ",
            parameter_values=[
                {"ParameterKey": "a", "ParameterValue": "b"},
            ],
            capabilities=["CAPABILITY_IAM"],
            role_arn="role-arn",
            notification_arns=[],
            s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
            tags={"unit": "true"},
        )

        self.assertEqual(self.deployer._client.create_stack.call_count, 1)
        self.deployer._client.create_stack.assert_called_with(
            Capabilities=["CAPABILITY_IAM"],
            NotificationARNs=[],
            Parameters=[{"ParameterKey": "a", "ParameterValue": "b"}],
            RoleARN="role-arn",
            StackName="test",
            Tags={"unit": "true"},
            TemplateURL=ANY,
        )

    def test_sync_create_stack_exception(self):
        self.deployer.has_stack = MagicMock(return_value=False)
        self.deployer.wait_for_execute = MagicMock()
        self.deployer._client.create_stack = MagicMock(side_effect=Exception)
        with self.assertRaises(DeployFailedError):
            self.deployer.sync(
                stack_name="test",
                cfn_template=" ",
                parameter_values=[
                    {"ParameterKey": "a", "ParameterValue": "b"},
                ],
                capabilities=["CAPABILITY_IAM"],
                role_arn="role-arn",
                notification_arns=[],
                s3_uploader=S3Uploader(s3_client=self.s3_client, bucket_name="test_bucket"),
                tags={"unit": "true"},
            )

    def test_process_kwargs(self):
        kwargs = {"Capabilities": []}
        capabilities = ["CAPABILITY_IAM"]
        role_arn = "role-arn"
        notification_arns = ["arn"]

        expected = {
            "Capabilities": ["CAPABILITY_IAM"],
            "RoleARN": "role-arn",
            "NotificationARNs": ["arn"],
        }
        result = self.deployer._process_kwargs(kwargs, None, capabilities, role_arn, notification_arns)
        self.assertEqual(expected, result)
