from unittest import TestCase, mock
from unittest.mock import Mock, patch

from samcli.commands.exceptions import UserException
from samcli.commands.logs.logs_context import parse_time, ResourcePhysicalIdResolver
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary

AWS_SOME_RESOURCE = "AWS::Some::Resource"
AWS_LAMBDA_FUNCTION = "AWS::Lambda::Function"
AWS_APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
AWS_APIGATEWAY_HTTPAPI = "AWS::ApiGatewayV2::Api"


class TestLogsCommandContext(TestCase):
    def setUp(self):
        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"
        self.output_file = "somefile"

    @patch("samcli.commands.logs.logs_context.parse_date")
    @patch("samcli.commands.logs.logs_context.to_utc")
    def test_parse_time(self, to_utc_mock, parse_date_mock):
        given_input = "some time"
        parsed_result = "parsed"
        expected = "bar"
        parse_date_mock.return_value = parsed_result
        to_utc_mock.return_value = expected

        actual = parse_time(given_input, "some prop")
        self.assertEqual(actual, expected)

        parse_date_mock.assert_called_with(given_input)
        to_utc_mock.assert_called_with(parsed_result)

    @patch("samcli.commands.logs.logs_context.parse_date")
    def test_parse_time_raises_exception(self, parse_date_mock):
        given_input = "some time"
        parsed_result = None
        parse_date_mock.return_value = parsed_result

        with self.assertRaises(UserException) as ctx:
            parse_time(given_input, "some prop")

        self.assertEqual(str(ctx.exception), "Unable to parse the time provided by 'some prop'")

    def test_parse_time_empty_time(self):
        result = parse_time(None, "some prop")
        self.assertIsNone(result)


class TestResourcePhysicalIdResolver(TestCase):
    def test_get_resource_information_with_resources(self):
        resource_physical_id_resolver = ResourcePhysicalIdResolver(Mock(), "stack_name", ["resource_name"])
        with mock.patch(
            "samcli.commands.logs.logs_context.ResourcePhysicalIdResolver._fetch_resources_from_stack"
        ) as mocked_fetch:
            expected_return = Mock()
            mocked_fetch.return_value = expected_return

            actual_return = resource_physical_id_resolver.get_resource_information(False)

            mocked_fetch.assert_called_once()
            self.assertEqual(actual_return, expected_return)

    def test_get_resource_information_of_all_stack(self):
        resource_physical_id_resolver = ResourcePhysicalIdResolver(Mock(), "stack_name", [])
        with mock.patch(
            "samcli.commands.logs.logs_context.ResourcePhysicalIdResolver._fetch_resources_from_stack"
        ) as mocked_fetch:
            expected_return = Mock()
            mocked_fetch.return_value = expected_return

            actual_return = resource_physical_id_resolver.get_resource_information(True)

            mocked_fetch.assert_called_once()
            self.assertEqual(actual_return, expected_return)

    def test_get_no_resource_information(self):
        resource_physical_id_resolver = ResourcePhysicalIdResolver(Mock(), "stack_name", None)
        actual_return = resource_physical_id_resolver.get_resource_information(False)
        self.assertEqual(actual_return, [])

    @patch("samcli.commands.logs.logs_context.get_resource_summaries")
    def test_fetch_all_resources(self, patched_get_resources):
        resource_physical_id_resolver = ResourcePhysicalIdResolver(Mock(), "stack_name", [])
        mocked_return_value = [
            CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, "logical_id_1", "physical_id_1"),
            CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, "logical_id_2", "physical_id_2"),
            CloudFormationResourceSummary(AWS_APIGATEWAY_RESTAPI, "logical_id_3", "physical_id_3"),
            CloudFormationResourceSummary(AWS_APIGATEWAY_HTTPAPI, "logical_id_4", "physical_id_4"),
        ]
        patched_get_resources.return_value = mocked_return_value

        actual_result = resource_physical_id_resolver._fetch_resources_from_stack()
        self.assertEqual(len(actual_result), 4)

        expected_results = [
            item
            for item in mocked_return_value
            if item.resource_type in ResourcePhysicalIdResolver.DEFAULT_SUPPORTED_RESOURCES
        ]
        self.assertEqual(expected_results, actual_result)

    @patch("samcli.commands.logs.logs_context.get_resource_summaries")
    def test_fetch_given_resources(self, patched_get_resources):
        given_resources = ["logical_id_1", "logical_id_2", "logical_id_3", "logical_id_5", "logical_id_6"]
        resource_physical_id_resolver = ResourcePhysicalIdResolver(Mock(), "stack_name", given_resources)
        mocked_return_value = [
            CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, "logical_id_1", "physical_id_1"),
            CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, "logical_id_2", "physical_id_2"),
            CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, "logical_id_3", "physical_id_3"),
            CloudFormationResourceSummary(AWS_APIGATEWAY_RESTAPI, "logical_id_4", "physical_id_4"),
            CloudFormationResourceSummary(AWS_APIGATEWAY_HTTPAPI, "logical_id_5", "physical_id_5"),
        ]
        patched_get_resources.return_value = mocked_return_value

        actual_result = resource_physical_id_resolver._fetch_resources_from_stack(set(given_resources))
        self.assertEqual(len(actual_result), 4)

        expected_results = [
            item
            for item in mocked_return_value
            if item.resource_type in ResourcePhysicalIdResolver.DEFAULT_SUPPORTED_RESOURCES
            and item.logical_resource_id in given_resources
        ]
        self.assertEqual(expected_results, actual_result)
