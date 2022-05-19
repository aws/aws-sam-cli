from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from botocore.exceptions import ClientError

from samcli.lib.utils.cloudformation import (
    CloudFormationResourceSummary,
    get_resource_summaries,
    get_resource_summary,
)


class TestCloudFormationResourceSummary(TestCase):
    def test_cfn_resource_summary(self):
        given_type = "type"
        given_logical_id = "logical_id"
        given_physical_id = "physical_id"

        resource_summary = CloudFormationResourceSummary(given_type, given_logical_id, given_physical_id)

        self.assertEqual(given_type, resource_summary.resource_type)
        self.assertEqual(given_logical_id, resource_summary.logical_resource_id)
        self.assertEqual(given_physical_id, resource_summary.physical_resource_id)

    def test_get_resource_summaries(self):
        resource_provider_mock = Mock()
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
        ]

        resource_provider_mock(ANY).Stack(ANY).resource_summaries.all.return_value = given_stack_resource_array

        resource_summaries = get_resource_summaries(resource_provider_mock, given_stack_name, given_resource_types)

        self.assertEqual(len(resource_summaries), 2)
        self.assertEqual(
            resource_summaries,
            [
                CloudFormationResourceSummary("ResourceType0", "logical_id_1", "physical_id_1"),
                CloudFormationResourceSummary("ResourceType0", "logical_id_2", "physical_id_2"),
            ],
        )

        resource_provider_mock.assert_called_with("cloudformation")
        resource_provider_mock(ANY).Stack.assert_called_with(given_stack_name)
        resource_provider_mock(ANY).Stack(ANY).resource_summaries.all.assert_called_once()

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
