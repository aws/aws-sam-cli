"""
Integration tests for DNS option in sam local start-lambda
"""
import pytest
from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass


class TestStartLambdaWithDNS(StartLambdaIntegBaseClass):
    """
    Test that --dns option is properly passed to start-lambda command
    and the service starts successfully with custom DNS configuration
    """

    template_path = "/testdata/invoke/template.yml"

    @classmethod
    def setUpClass(cls):
        # Override to add DNS options to the start-lambda command
        cls.dns_servers = ["8.8.8.8", "1.1.1.1"]
        super().setUpClass()

    @classmethod
    def get_start_lambda_command(
        cls,
        port=None,
        template_path=None,
        env_var_path=None,
        container_mode=None,
        container_host_interface=None,
        parameter_overrides=None,
        invoke_image=None,
        hook_name=None,
        beta_features=None,
        terraform_plan_file=None,
        function_logical_ids=None,
    ):
        # Get base command from parent class
        command_list = super().get_start_lambda_command(
            port=port,
            template_path=template_path,
            env_var_path=env_var_path,
            container_mode=container_mode,
            container_host_interface=container_host_interface,
            parameter_overrides=parameter_overrides,
            invoke_image=invoke_image,
            hook_name=hook_name,
            beta_features=beta_features,
            terraform_plan_file=terraform_plan_file,
            function_logical_ids=function_logical_ids,
        )

        # Add DNS options
        if hasattr(cls, "dns_servers") and cls.dns_servers:
            for dns_server in cls.dns_servers:
                command_list += ["--dns", dns_server]

        return command_list

    def setUp(self):
        self.lambda_client = self.get_local_lambda_client()

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_function_with_custom_dns(self):
        """
        Test that a function can be invoked successfully when start-lambda
        is started with custom DNS servers
        """
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='{"key": "value"}')

        self.assertEqual(response.get("StatusCode"), 200)
        payload = response.get("Payload").read().decode("utf-8")
        # EchoEventFunction should echo back the input
        self.assertIn("key", payload)
        self.assertIn("value", payload)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_multiple_invocations_with_dns(self):
        """
        Test that multiple invocations work correctly with custom DNS
        """
        # Invoke the function multiple times
        for i in range(3):
            response = self.lambda_client.invoke(
                FunctionName="EchoEventFunction", Payload=f'{{"iteration": {i}}}'
            )

            self.assertEqual(response.get("StatusCode"), 200)
            payload = response.get("Payload").read().decode("utf-8")
            self.assertIn("iteration", payload)
