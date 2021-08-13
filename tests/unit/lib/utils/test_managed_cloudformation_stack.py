from unittest import TestCase
from unittest.mock import patch, Mock

import botocore.session

from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError, ProfileNotFound
from botocore.stub import Stubber
from parameterized import parameterized

from samcli.commands.exceptions import UserException, CredentialsError, RegionError
from samcli.lib.bootstrap.bootstrap import _get_stack_template, SAM_CLI_STACK_NAME
from samcli.lib.utils.managed_cloudformation_stack import manage_stack, _create_or_get_stack, ManagedStackError


class TestManagedCloudFormationStack(TestCase):
    def _stubbed_cf_client(self):
        cf = botocore.session.get_session().create_client("cloudformation", region_name="us-west-2")
        return [cf, Stubber(cf)]

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

    @patch("boto3.client")
    def test_client_missing_credentials(self, boto_mock):
        boto_mock.side_effect = NoCredentialsError()
        with self.assertRaises(CredentialsError):
            manage_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    @patch("boto3.client")
    def test_client_missing_region(self, boto_mock):
        boto_mock.side_effect = NoRegionError()
        with self.assertRaises(RegionError):
            manage_stack(
                profile=None, region="fake-region", stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
            )

    def test_new_stack(self):
        stub_cf, stubber = self._stubbed_cf_client()
        # first describe_stacks call will fail
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_client_error("describe_stacks", service_error_code="ClientError", expected_params=ds_params)
        # creating change set
        ccs_params = {
            "StackName": SAM_CLI_STACK_NAME,
            "TemplateBody": _get_stack_template(),
            "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            "ChangeSetType": "CREATE",
            "ChangeSetName": "InitialCreation",
            "Capabilities": ["CAPABILITY_IAM"],
            "Parameters": [],
        }
        ccs_resp = {"Id": "id", "StackId": "aws-sam-cli-managed-default"}
        stubber.add_response("create_change_set", ccs_resp, ccs_params)
        # describe change set creation status for waiter
        dcs_params = {"ChangeSetName": "InitialCreation", "StackName": SAM_CLI_STACK_NAME}
        dcs_resp = {"Status": "CREATE_COMPLETE"}
        stubber.add_response("describe_change_set", dcs_resp, dcs_params)
        # executing change set
        ecs_params = {"ChangeSetName": "InitialCreation", "StackName": SAM_CLI_STACK_NAME}
        ecs_resp = {}
        stubber.add_response("execute_change_set", ecs_resp, ecs_params)
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
        stubber.add_response("describe_stacks", post_create_ds_resp, ds_params)
        stubber.add_response("describe_stacks", post_create_ds_resp, ds_params)
        stubber.activate()
        _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    def test_stack_exists(self):
        stub_cf, stubber = self._stubbed_cf_client()
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
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_response("describe_stacks", ds_resp, ds_params)
        stubber.activate()
        _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    def test_stack_missing_tag(self):
        stub_cf, stubber = self._stubbed_cf_client()
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
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_response("describe_stacks", ds_resp, ds_params)
        stubber.activate()
        with self.assertRaises(UserException):
            _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    def test_stack_wrong_tag(self):
        stub_cf, stubber = self._stubbed_cf_client()
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
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_response("describe_stacks", ds_resp, ds_params)
        stubber.activate()
        with self.assertRaises(UserException):
            _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    def test_change_set_creation_fails(self):
        stub_cf, stubber = self._stubbed_cf_client()
        # first describe_stacks call will fail
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_client_error("describe_stacks", service_error_code="ClientError", expected_params=ds_params)
        # creating change set - fails
        ccs_params = {
            "StackName": SAM_CLI_STACK_NAME,
            "TemplateBody": _get_stack_template(),
            "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            "ChangeSetType": "CREATE",
            "ChangeSetName": "InitialCreation",
            "Capabilities": ["CAPABILITY_IAM"],
            "Parameters": [],
        }
        stubber.add_client_error("create_change_set", service_error_code="ClientError", expected_params=ccs_params)
        stubber.activate()
        with self.assertRaises(ManagedStackError):
            _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    def test_change_set_execution_fails(self):
        stub_cf, stubber = self._stubbed_cf_client()
        # first describe_stacks call will fail
        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_client_error("describe_stacks", service_error_code="ClientError", expected_params=ds_params)
        # creating change set
        ccs_params = {
            "StackName": SAM_CLI_STACK_NAME,
            "TemplateBody": _get_stack_template(),
            "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
            "ChangeSetType": "CREATE",
            "ChangeSetName": "InitialCreation",
            "Capabilities": ["CAPABILITY_IAM"],
            "Parameters": [],
        }
        ccs_resp = {"Id": "id", "StackId": "aws-sam-cli-managed-default"}
        stubber.add_response("create_change_set", ccs_resp, ccs_params)
        # describe change set creation status for waiter
        dcs_params = {"ChangeSetName": "InitialCreation", "StackName": SAM_CLI_STACK_NAME}
        dcs_resp = {"Status": "CREATE_COMPLETE"}
        stubber.add_response("describe_change_set", dcs_resp, dcs_params)
        # executing change set - fails
        ecs_params = {"ChangeSetName": "InitialCreation", "StackName": SAM_CLI_STACK_NAME}
        stubber.add_client_error(
            "execute_change_set", service_error_code="InsufficientCapabilities", expected_params=ecs_params
        )
        stubber.activate()
        with self.assertRaises(ManagedStackError):
            _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()

    @parameterized.expand(
        [
            ([{"Key": "ManagedStackSource", "Value": "WHY WOULD YOU EVEN DO THIS"}], None),
            (None, [{"OutputKey": "SourceBucket", "OutputValue": "generated-src-bucket"}]),
            (None, None),
        ]
    )
    def test_stack_is_invalid_state(self, tags, outputs):
        stub_cf, stubber = self._stubbed_cf_client()
        ds_resp = {
            "Stacks": [{"StackName": SAM_CLI_STACK_NAME, "CreationTime": "2019-11-13", "StackStatus": "CREATE_FAILED"}]
        }

        # add Tags or Outputs information if it exists
        # Boto client is missing this information if stack is in invalid state
        if tags:
            ds_resp["Stacks"][0]["Tags"] = tags

        if outputs:
            ds_resp["Stacks"][0]["Outputs"] = outputs

        ds_params = {"StackName": SAM_CLI_STACK_NAME}
        stubber.add_response("describe_stacks", ds_resp, ds_params)
        stubber.activate()
        with self.assertRaises(UserException):
            _create_or_get_stack(stub_cf, SAM_CLI_STACK_NAME, _get_stack_template())
        stubber.assert_no_pending_responses()
        stubber.deactivate()
