from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.bottle_neck_calculations import BottleNeckCalculations
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class TestCalculations(TestCase):
    @patch("samcli.commands.check.bottle_neck_calculations._generate_path_string")
    @patch("samcli.commands.check.bottle_neck_calculations._check_limit")
    @patch("samcli.commands.check.bottle_neck_calculations.Warning")
    def test_generate_warning_message(self, patch_warning, patch_check_limit, patch_generate):
        """
        Other than capacity, the specific values (strings and ints) used in the parameter variables for
        "calculations._generate_warning_message" do not matter. They just have to be of type
        string and int, due to how the message string is formatted in "warning.set_message(...)"
        """
        graph_mock = Mock()
        warning_instance_mock = Mock()
        patch_warning.return_value = warning_instance_mock

        warning_instance_mock.message = Mock()
        graph_mock.green_warnings = []
        graph_mock.yellow_warnings = []
        graph_mock.red_warnings = []
        graph_mock.red_burst_warnings = []

        path_to_resource = []

        calculations = BottleNeckCalculations(graph_mock, "")

        # Capacity <= 70
        capacity_used = 60
        resource_name = "string"
        concurrent_executions = 42
        duration = Mock()
        tps = Mock()
        burst_concurrency = Mock()

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency, path_to_resource
        )

        # Capacity > 70 and < 90
        capacity_used = 89
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency, path_to_resource
        )

        # Capacity >= 90 <= 100
        capacity_used = 90
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency, path_to_resource
        )

        # Capacity > 100
        capacity_used = 101
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        patch_check_limit.return_value = 815

        calculations._get_error_file_lines = Mock()
        calculations._get_error_file_lines.return_value = ""

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency, path_to_resource
        )

        patch_check_limit.assert_called_once_with(tps, duration, burst_concurrency)

        patch_generate.assert_any_call(path_to_resource)

        self.assertEqual(len(graph_mock.green_warnings), 1)
        self.assertEqual(len(graph_mock.yellow_warnings), 1)
        self.assertEqual(len(graph_mock.red_warnings), 1)
        self.assertEqual(len(graph_mock.red_burst_warnings), 1)

    @patch("samcli.commands.check.bottle_neck_calculations._check_limit")
    @patch("samcli.commands.check.bottle_neck_calculations.click")
    @patch("samcli.commands.check.bottle_neck_calculations.boto3")
    def test_run_calculations(self, patch_boto3, patch_click, patch_check_limit):
        import botocore

        graph_mock = Mock()
        resource_mock = Mock()

        graph_mock.resources_to_analyze = {"": resource_mock}

        resource_mock.resource_type = AWS_LAMBDA_FUNCTION
        resource_mock.resource_name = Mock()
        resource_mock.tps = Mock()
        resource_mock.duration = Mock()
        resource_mock.path_to_resource = []

        client_mock = Mock()

        patch_boto3.client.return_value = client_mock

        calculations = BottleNeckCalculations(graph_mock, "")
        calculations.check_limit = Mock()
        calculations.check_limit.return_value = Mock()
        calculations._generate_warning_message = Mock()

        patch_check_limit.return_value = Mock()

        burst_mock = Mock()
        concurrent_mock = Mock()

        def get_quota(ServiceCode, QuotaCode):
            if QuotaCode == "L-548AE339":
                return {"Quota": {"Value": burst_mock}}
            elif QuotaCode == "L-B99A9384":
                return {"Quota": {"Value": concurrent_mock}}

        client_mock.get_aws_default_service_quota.side_effect = get_quota

        calculations.run_calculations()

        patch_boto3.client.assert_called_once_with("service-quotas")
        patch_check_limit.assert_called_once_with(resource_mock.tps, resource_mock.duration, concurrent_mock)

        client_mock.get_aws_default_service_quota.assert_called()
        calculations._generate_warning_message.assert_called_once_with(
            patch_check_limit.return_value,
            resource_mock.resource_name,
            concurrent_mock,
            resource_mock.duration,
            resource_mock.tps,
            burst_mock,
            resource_mock.path_to_resource,
        )

        # Test error catches
        client_mock.get_aws_default_service_quota.side_effect = botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "Stack with id test does not exist"}},
            operation_name="stack_status",
        )
        with self.assertRaises(botocore.exceptions.ClientError):
            calculations.run_calculations()

        client_mock.get_aws_default_service_quota.side_effect = ValueError
        with self.assertRaises(ValueError):
            calculations.run_calculations()

    def test_check_limit(self):
        from samcli.commands.check.bottle_neck_calculations import _check_limit

        result1 = _check_limit(300, 200, 1000)
        result2 = _check_limit(300, 1500, 2000)
        result3 = _check_limit(1000, 300, 1500)
        result4 = _check_limit(1800, 1400, 450)

        self.assertEqual(result1, 6)
        self.assertEqual(result2, 22.5)
        self.assertEqual(result3, 20)
        self.assertEqual(result4, 560)
