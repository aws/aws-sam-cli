from unittest import TestCase
from unittest.mock import patch, Mock, call

from botocore.exceptions import NoCredentialsError, NoRegionError, ProfileNotFound, ClientError
from parameterized import parameterized

from samcli.commands.exceptions import UserException, CredentialsError, RegionError
from samcli.lib.bootstrap.bootstrap import _get_stack_template, SAM_CLI_STACK_NAME
from samcli.lib.utils.managed_cloudformation_stack import (
    manage_stack,
    update_stack,
    _create_or_get_stack,
    ManagedStackError,
)


class TestManagedCloudFormationStack(TestCase):
    cf = None

    def setUp(self) -> None:
        self.cf = Mock()

    @patch("boto3.Session")
    def test_session_missing_profile(self, boto_mock):
        boto_mock.side_effect = ProfileNotFound(profile="test-profile")
        with self.assertRaises(CredentialsError):
            manage_stack(
                profile="test-profile",
                region="fake-region",
                stack_name=SAM_CLI_STACK_NAME,
                template_body=_get_stack_template(),
            )

    @patch("boto3.Session")
    def test_session_missing_profile_update(self, boto_mock):
        boto_mock.side_effect = ProfileNotFound(profile="test-profile")
        with self.assertRaises(CredentialsError):
            update_stack(
                profile="test-profile",
                region="fake-region",
                stack_name=SAM_CLI_STACK_NAME,
                template_body=_get_stack_template(),
            )

    @patch("boto3.client")
    def test_client_missing_credentials(self, boto_mock):
        boto_mock.side_effect = NoCredentialsError()
        with self.assertRaises(CredentialsError):
            manage_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    @patch("boto3.client")
    def test_client_missing_credentials_update(self, boto_mock):
        boto_mock.side_effect = NoCredentialsError()
        with self.assertRaises(CredentialsError):
            update_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    @patch("boto3.client")
    def test_client_missing_region(self, boto_mock):
        boto_mock.side_effect = NoRegionError()
        with self.assertRaises(RegionError):
            manage_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    @patch("boto3.client")
    def test_client_missing_region_update(self, boto_mock):
        boto_mock.side_effect = NoRegionError()
        with self.assertRaises(RegionError):
            update_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    def test_new_stack(self):
        # first describe_stacks call will fail
        # two describe_stacks calls will succeed - one for waiter, one direct
        post_create_ds_resp = {
            "Stacks": [
                {
                    "StackName": SAM_CLI_STACK_NAME,
                    "CreationTime": "2019-11-13",
                    "StackStatus": "CREATE_COMPLETE",
                    "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
                    "Outputs": [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}],
                }
            ]
        }
        self.cf.describe_stacks.side_effect = [
            ClientError({}, "describe_stacks"), post_create_ds_resp
        ]

        # creating change set
        ccs_resp = {"Id": "id", "StackId": "aws-sam-cli-managed-default"}
        self.cf.create_change_set.return_value = ccs_resp
        # describe change set creation status for waiter
        dcs_resp = {"Status": "CREATE_COMPLETE"}
        self.cf.describe_change_set.return_value = dcs_resp
        # executing change set
        ecs_resp = {}
        self.cf.execute_change_set.return_value = ecs_resp

        _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())

        self.cf.describe_stacks.assert_has_calls([
            call(StackName=SAM_CLI_STACK_NAME) for _ in range(2)
        ])
        self.cf.create_change_set.assert_called_with(
            StackName=SAM_CLI_STACK_NAME,
            TemplateBody=_get_stack_template(),
            Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            ChangeSetType="CREATE",
            ChangeSetName="InitialCreation",
            Capabilities=["CAPABILITY_IAM"],
            Parameters=[],
        )
        self.cf.execute_change_set.assert_called_with(ChangeSetName="InitialCreation", StackName=SAM_CLI_STACK_NAME)

    def test_stack_exists(self):
        ds_resp = {
            "Stacks": [
                {
                    "StackName": SAM_CLI_STACK_NAME,
                    "CreationTime": "2019-11-13",
                    "StackStatus": "CREATE_COMPLETE",
                    "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
                    "Outputs": [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}],
                }
            ]
        }
        self.cf.describe_stacks.return_value = ds_resp
        _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())
        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)

    def test_stack_missing_tag(self):
        ds_resp = {
            "Stacks": [
                {
                    "StackName": SAM_CLI_STACK_NAME,
                    "CreationTime": "2019-11-13",
                    "StackStatus": "CREATE_COMPLETE",
                    "Tags": [],
                    "Outputs": [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}],
                }
            ]
        }
        self.cf.describe_stacks.return_value = ds_resp
        with self.assertRaises(UserException):
            _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())
        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)

    def test_stack_wrong_tag(self):
        ds_resp = {
            "Stacks": [
                {
                    "StackName": SAM_CLI_STACK_NAME,
                    "CreationTime": "2019-11-13",
                    "StackStatus": "CREATE_COMPLETE",
                    "Tags": [{"Key": "ManagedStackSource", "Value": "WHY WOULD YOU EVEN DO THIS"}],
                    "Outputs": [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}],
                }
            ]
        }
        self.cf.describe_stacks.return_value = ds_resp
        with self.assertRaises(UserException):
            _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())
        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)

    def test_change_set_creation_fails(self):
        # first describe_stacks call will fail
        self.cf.describe_stacks.side_effect = [
            ClientError({}, "describe_stacks")
        ]

        # creating change set - fails
        self.cf.create_change_set.side_effect = [
            ClientError({}, "create_change_set")
        ]
        with self.assertRaises(ManagedStackError):
            _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())

        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)
        self.cf.create_change_set.assert_called_with(
            StackName=SAM_CLI_STACK_NAME,
            TemplateBody=_get_stack_template(),
            Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            ChangeSetType="CREATE",
            ChangeSetName="InitialCreation",
            Capabilities=["CAPABILITY_IAM"],
            Parameters=[],
        )

    def test_change_set_execution_fails(self):
        # first describe_stacks call will fail
        self.cf.describe_stacks.side_effect = [ClientError({}, "describe_stacks")]
        # creating change set
        ccs_resp = {"Id": "id", "StackId": "aws-sam-cli-managed-default"}
        self.cf.create_change_set.return_value = ccs_resp
        # executing change set - fails
        self.cf.execute_change_set.side_effect = [ClientError({}, "execute_change_set")]
        with self.assertRaises(ManagedStackError):
            _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())

        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)
        self.cf.create_change_set.assert_called_with(
            StackName=SAM_CLI_STACK_NAME,
            TemplateBody=_get_stack_template(),
            Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            ChangeSetType="CREATE",
            ChangeSetName="InitialCreation",
            Capabilities=["CAPABILITY_IAM"],
            Parameters=[],
        )
        self.cf.execute_change_set.assert_called_with(ChangeSetName="InitialCreation", StackName=SAM_CLI_STACK_NAME)

    @parameterized.expand(
        [
            ([{"Key": "ManagedStackSource", "Value": "WHY WOULD YOU EVEN DO THIS"}], None),
            (None, [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}]),
            (None, None),
        ]
    )
    def test_stack_is_invalid_state(self, tags, outputs):
        ds_resp = {
            "Stacks": [
                {"StackName": SAM_CLI_STACK_NAME, "CreationTime": "2019-11-13", "StackStatus": "CREATE_FAILED"}
            ]
        }

        # add Tags or Outputs information if it exists
        # Boto client is missing this information if stack is in invalid state
        if tags:
            ds_resp["Stacks"][0]["Tags"] = tags

        if outputs:
            ds_resp["Stacks"][0]["Outputs"] = outputs

        self.cf.describe_stacks.return_value = ds_resp
        with self.assertRaises(UserException):
            _create_or_get_stack(self.cf, SAM_CLI_STACK_NAME, _get_stack_template())
        self.cf.describe_stacks.assert_called_with(StackName=SAM_CLI_STACK_NAME)
