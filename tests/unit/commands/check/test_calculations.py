from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.calculations import Calculations


class TestCalculations(TestCase):
    @patch("samcli.commands.check.calculations.Warning")
    def test_generate_warning_message(self, patch_warning):
        """
        Other than capacity, the specific values (strings and ints) used in the parameter variables for
        "calculations.generate_warning_message" do not matter. They just have to be of type
        string and int, due to how the message string is formatted in "warning.set_message(...)"
        """
        graph_mock = Mock()
        warning_instance_mock = Mock()
        patch_warning.return_value = warning_instance_mock

        warning_instance_mock.set_message = Mock()
        graph_mock.add_green_warning = Mock()
        graph_mock.add_yellow_warning = Mock()
        graph_mock.add_red_warning = Mock()
        graph_mock.add_red_burst_warning = Mock()

        calculations = Calculations(graph_mock)

        # Capacity <= 70
        capacity_used = 60
        resource_name = "string"
        concurrent_executions = 42
        duration = Mock()
        tps = Mock()
        burst_concurrency = Mock()

        calculations.generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        warning_instance_mock.set_message.assert_called_with(
            "For the lambda function [%s], you will not be close to its soft limit of %i concurrent executions."
            % (resource_name, concurrent_executions)
        )
        graph_mock.add_green_warning.assert_called_once_with(warning_instance_mock)

        # Capacity > 70 and < 90
        capacity_used = 89
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations.generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        warning_instance_mock.set_message.assert_called_with(
            "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. A limit increase should be considered:\nhttps://console.aws.amazon.com/servicequotas"
            % (resource_name, duration, tps, round(capacity_used))
        )
        graph_mock.add_yellow_warning.assert_called_once_with(warning_instance_mock)

        # Capacity >= 90 <= 100
        capacity_used = 90
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations.generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        warning_instance_mock.set_message.assert_called_with(
            "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It is very close to the limits of the lambda function. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
            % (resource_name, duration, tps, round(capacity_used))
        )
        graph_mock.add_red_warning.assert_called_once_with(warning_instance_mock)

        # Capacity > 100
        capacity_used = 101
        resource_name = "4"
        concurrent_executions = 8
        duration = 15
        tps = 16
        burst_concurrency = 2342

        calculations.check_limit = Mock()
        calculations.check_limit.return_value = 815

        calculations.generate_warning_message(
            capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
        )

        warning_instance_mock.set_message.assert_called_with(
            "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It exceeds the limits of the lambda function. It will use %i%% of the available burst concurrency. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
            % (resource_name, duration, tps, round(capacity_used), round(calculations.check_limit.return_value))
        )
        graph_mock.add_red_burst_warning.assert_called_once_with(warning_instance_mock)

    @patch("samcli.commands.check.calculations.click")
    @patch("samcli.commands.check.calculations.boto3")
    def test_run_bottle_neck_calculations(self, patch_boto3, patch_click):
        # pass
        # Cannot mock client. Need to find a way around it.
        graph_mock = Mock()
        resource_mock = Mock()

        graph_mock.get_resources_to_analyze.return_value = [resource_mock]

        resource_mock.get_resource_type.return_value = "AWS::Lambda::Function"
        resource_mock.get_name.return_value = Mock()
        resource_mock.get_tps.return_value = Mock()
        resource_mock.get_duration.return_value = Mock()

        client_mock = Mock()

        patch_boto3.client.return_value = client_mock

        calculations = Calculations(graph_mock)
        calculations.check_limit = Mock()
        calculations.check_limit.return_value = Mock()
        calculations.generate_warning_message = Mock()

        burst_mock = Mock()
        concurrent_mock = Mock()

        client_mock.get_aws_default_service_quota(ServiceCode="lambda", QuotaCode="L-548AE339").return_value = {
            "Quota": {"Value": burst_mock}
        }
        client_mock.get_aws_default_service_quota(ServiceCode="lambda", QuotaCode="L-B99A9384").return_value = {
            "Quota": {"Value": concurrent_mock}
        }

        burst_concurrency = client_mock.get_aws_default_service_quota(
            ServiceCode="lambda", QuotaCode="L-548AE339"
        ).return_value["Quota"]["Value"]
        concurrent_executions = client_mock.get_aws_default_service_quota(
            ServiceCode="lambda", QuotaCode="L-B99A9384"
        ).return_value["Quota"]["Value"]

        calculations.run_bottle_neck_calculations()

        patch_boto3.client.assert_called_once_with("service-quotas")
        calculations.check_limit.assert_called_once_with(
            resource_mock.get_tps.return_value, resource_mock.get_duration.return_value, concurrent_executions
        )

        client_mock.get_aws_default_service_quota.assert_called()

    def test_check_limit(self):
        graph_mock = Mock()

        calculations = Calculations(graph_mock)

        result1 = calculations.check_limit(300, 200, 1000)
        result2 = calculations.check_limit(300, 1500, 2000)
        result3 = calculations.check_limit(1000, 300, 1500)
        result4 = calculations.check_limit(1800, 1400, 450)

        self.assertEqual(result1, 6)
        self.assertEqual(result2, 22.5)
        self.assertEqual(result3, 20)
        self.assertEqual(result4, 560)
