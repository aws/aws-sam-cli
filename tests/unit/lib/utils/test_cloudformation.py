from unittest import TestCase
from unittest.mock import patch, Mock, ANY, call

from botocore.exceptions import ClientError

from samcli.lib.utils.cloudformation import (
    CloudFormationResourceSummary,
    get_resource_summaries,
    get_resource_summary,
    list_active_stack_names,
)
from samcli.lib.utils.resources import AWS_CLOUDFORMATION_STACK


class TestCloudFormationResourceSummary(TestCase):
    def test_cfn_resource_summary(self):
        given_type = "type"
        given_logical_id = "logical_id"
        given_physical_id = "physical_id"

        resource_summary = CloudFormationResourceSummary(
            given_type,
            given_logical_id,
            given_physical_id,
        )

        self.assertEqual(given_type, resource_summary.resource_type)
        self.assertEqual(given_logical_id, resource_summary.logical_resource_id)
        self.assertEqual(given_physical_id, resource_summary.physical_resource_id)


class TestCloudformationUtils(TestCase):
    def test_get_resource_summaries(self):
        resource_provider_mock = Mock()
        client_provider_mock = Mock()
        given_stack_name = "stack_name"
        given_resource_types = {"ResourceType0"}

        given_stack_resource_array = [
            Mock(
                physical_resource_id="physical_id_1", logical_resource_id="logical_id_1", resource_type="ResourceType0"
            ),
            Mock(
                physical_resource_id="physical_id_2", logical_resource_id="logical_id_2", resource_type="ResourceType0"
            ),
            Mock(
                physical_resource_id="physical_id_3", logical_resource_id="logical_id_3", resource_type="ResourceType1"
            ),
            Mock(
                physical_resource_id="physical_id_4",
                logical_resource_id="logical_id_4",
                resource_type=AWS_CLOUDFORMATION_STACK,
            ),
        ]

        given_nested_stack_resource_array = [
            Mock(
                physical_resource_id="physical_id_5", logical_resource_id="logical_id_5", resource_type="ResourceType0"
            ),
            Mock(
                physical_resource_id="physical_id_6", logical_resource_id="logical_id_6", resource_type="ResourceType0"
            ),
            Mock(
                physical_resource_id="physical_id_7", logical_resource_id="logical_id_7", resource_type="ResourceType1"
            ),
        ]

        resource_provider_mock(ANY).Stack(ANY).resource_summaries.all.side_effect = [
            given_stack_resource_array,
            given_nested_stack_resource_array,
        ]

        resource_summaries = get_resource_summaries(
            resource_provider_mock, client_provider_mock, given_stack_name, given_resource_types
        )

        self.assertEqual(len(resource_summaries), 4)
        self.assertEqual(
            resource_summaries,
            {
                "logical_id_1": CloudFormationResourceSummary("ResourceType0", "logical_id_1", "physical_id_1"),
                "logical_id_2": CloudFormationResourceSummary("ResourceType0", "logical_id_2", "physical_id_2"),
                "logical_id_4/logical_id_5": CloudFormationResourceSummary(
                    "ResourceType0", "logical_id_5", "physical_id_5"
                ),
                "logical_id_4/logical_id_6": CloudFormationResourceSummary(
                    "ResourceType0", "logical_id_6", "physical_id_6"
                ),
            },
        )

        resource_provider_mock.assert_called_with("cloudformation")
        resource_provider_mock(ANY).Stack.assert_has_calls(
            [
                call(given_stack_name),
                call().resource_summaries.all(),
                call("physical_id_4"),
                call().resource_summaries.all(),
            ]
        )

    def test_get_resource_summary(self):
        resource_provider_mock = Mock()
        given_stack_name = "stack_name"
        given_resource_logical_id = "logical_id_1"

        given_resource_type = "ResourceType0"
        given_physical_id = "physical_id_1"
        resource_provider_mock(ANY).StackResource.return_value = Mock(
            physical_resource_id=given_physical_id,
            logical_resource_id=given_resource_logical_id,
            resource_type=given_resource_type,
        )

        resource_summary = get_resource_summary(resource_provider_mock, given_stack_name, given_resource_logical_id)

        self.assertEqual(resource_summary.resource_type, given_resource_type)
        self.assertEqual(resource_summary.logical_resource_id, given_resource_logical_id)
        self.assertEqual(resource_summary.physical_resource_id, given_physical_id)

        resource_provider_mock.assert_called_with("cloudformation")
        resource_provider_mock(ANY).StackResource.assert_called_with(given_stack_name, given_resource_logical_id)

    def test_get_resource_summary_fail(self):
        resource_provider_mock = Mock()
        given_stack_name = "stack_name"
        given_resource_logical_id = "logical_id_1"

        resource_provider_mock(ANY).StackResource.side_effect = ClientError({}, "operation")

        resource_summary = get_resource_summary(resource_provider_mock, given_stack_name, given_resource_logical_id)

        self.assertIsNone(resource_summary)

    @patch("samcli.lib.utils.cloudformation.LOG")
    @patch("samcli.lib.utils.cloudformation.list_active_stack_names")
    def test_get_resource_summaries_invalid_stack(self, patched_list_active_stack_names, patched_log):
        resource_provider_mock = Mock()
        client_provider_mock = Mock()
        patched_log.isEnabledFor.return_value = True
        patched_list_active_stack_names.return_value = []

        resource_provider_mock.side_effect = ClientError({"Error": {"Code": "ValidationError"}}, "operation")

        with self.assertRaises(ClientError):
            get_resource_summaries(resource_provider_mock, client_provider_mock, "invalid-stack")
            patched_log.debug.assert_called_with(
                "Invalid stack name (%s). Available stack names: %s", "invalid-stack", ", ".join([])
            )

    def test_list_active_stack_names(self):
        cfn_client_mock = Mock()
        cfn_client_mock.list_stacks.side_effect = [
            {
                "StackSummaries": [{"StackName": "A"}, {"StackName": "B"}, {"StackName": "C", "RootId": "A"}],
                "NextToken": "X",
            },
            {"StackSummaries": [{"StackName": "D"}, {"StackName": "E"}, {"StackName": "F", "RootId": "A"}]},
        ]
        client_provider_mock = Mock()
        client_provider_mock.return_value = cfn_client_mock

        self.assertEqual(["A", "B", "D", "E"], list(list_active_stack_names(client_provider_mock)))

    def test_list_active_stack_names_with_nested_stacks(self):
        cfn_client_mock = Mock()
        cfn_client_mock.list_stacks.side_effect = [
            {
                "StackSummaries": [{"StackName": "A"}, {"StackName": "B"}, {"StackName": "C", "RootId": "A"}],
                "NextToken": "X",
            },
            {"StackSummaries": [{"StackName": "D"}, {"StackName": "E"}, {"StackName": "F", "RootId": "A"}]},
        ]
        client_provider_mock = Mock()
        client_provider_mock.return_value = cfn_client_mock

        self.assertEqual(["A", "B", "C", "D", "E", "F"], list(list_active_stack_names(client_provider_mock, True)))
