from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.calculation import CheckCalculation
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class TestCalculations(TestCase):
    @patch("samcli.commands.check.calculation._check_limit")
    @patch("samcli.commands.check.calculation.CheckWarning")
    def test__generate_warning_message(self, patch_warning, patch_check_limit):
        """
        Other than capacity, the specific values (strings and ints) used in the parameter variables for
        "calculations._generate_warning_message" do not matter. They just have to be of type
        string and int, due to how the message string is formatted in "warning.set_message(...)"
        """
        graph_mock = Mock()
        warning_instance_mock = Mock()
        patch_warning.return_value = warning_instance_mock

        warning_instance_mock.message = Mock()
        graph_mock.green_warnings.append = Mock()
        graph_mock.yellow_warnings.append = Mock()
        graph_mock.red_warnings.append = Mock()
        graph_mock.red_burst_warnings.append = Mock()

        calculations = CheckCalculation(graph_mock)

        # Capacity <= 70
        capacity_used = 60
        resource_name = "string"
        concurrent_executions = 42
        duration = Mock()
        tps = Mock()
        burst_concurrency = Mock()

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        graph_mock.green_warnings.append.assert_called_once_with(warning_instance_mock)

        # Capacity > 70 and < 90
        capacity_used = 89
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        graph_mock.yellow_warnings.append.assert_called_once_with(warning_instance_mock)

        # Capacity >= 90 <= 100
        capacity_used = 90
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        graph_mock.red_warnings.append.assert_called_once_with(warning_instance_mock)

        # Capacity > 100
        capacity_used = 101
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        patch_check_limit.return_value = 815

        calculations._generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        graph_mock.red_burst_warnings.append.assert_called_once_with(warning_instance_mock)
        patch_check_limit.assert_called_once_with(tps, duration, burst_concurrency)

    @patch("samcli.commands.check.calculation._check_limit")
    @patch("samcli.commands.check.calculation.click")
    @patch("samcli.commands.check.calculation.boto3")
    def test_run_bottle_neck_calculations(self, patch_boto3, patch_click, patch_check_limit):
        import botocore

        graph_mock = Mock()
        resource_mock = Mock()

        graph_mock.resources_to_analyze = [resource_mock]

        resource_mock.resource_type = AWS_LAMBDA_FUNCTION
        resource_mock.resource_name = Mock()
        resource_mock.tps = Mock()
        resource_mock.duration = Mock()

        client_mock = Mock()

        patch_boto3.client.return_value = client_mock

        calculations = CheckCalculation(graph_mock)

        patch_check_limit.return_value = Mock()
        calculations._generate_warning_message = Mock()

        burst_mock = Mock()
        concurrent_mock = Mock()

        def get_quota(ServiceCode, QuotaCode):
            if QuotaCode == "L-548AE339":
                return {"Quota": {"Value": burst_mock}}
            elif QuotaCode == "L-B99A9384":
                return {"Quota": {"Value": concurrent_mock}}

        client_mock.get_aws_default_service_quota.side_effect = get_quota

        calculations.run_bottle_neck_calculations()

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
        )

        # Test error catches
        client_mock.get_aws_default_service_quota.side_effect = botocore.exceptions.ClientError(
            error_response={"Error": {"Message": "Stack with id test does not exist"}},
            operation_name="stack_status",
        )
        with self.assertRaises(botocore.exceptions.ClientError):
            calculations.run_bottle_neck_calculations()

        client_mock.get_aws_default_service_quota.side_effect = ValueError
        with self.assertRaises(ValueError):
            calculations.run_bottle_neck_calculations()

    def test_check_limit(self):
        from samcli.commands.check.calculation import _check_limit

        result1 = _check_limit(300, 200, 1000)
        result2 = _check_limit(300, 1500, 2000)
        result3 = _check_limit(1000, 300, 1500)
        result4 = _check_limit(1800, 1400, 450)

        self.assertEqual(result1, 6)
        self.assertEqual(result2, 22.5)
        self.assertEqual(result3, 20)
        self.assertEqual(result4, 560)
