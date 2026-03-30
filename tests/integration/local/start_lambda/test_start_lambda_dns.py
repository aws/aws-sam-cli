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
    def test_dns_configured_in_container(self):
        """
        Test that DNS servers are actually configured in the Docker container.
        This inspects the container configuration to verify DNS was set correctly.
        """
        # First invoke a function to ensure a container is created
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='{"key": "value"}')
        self.assertEqual(response.get("StatusCode"), 200)

        # Get SAM Lambda containers (running only, since that's what we just created)
        sam_containers = self.docker_client.containers.list(
            all=False, filters={"label": "sam.cli.container.type=lambda"}
        )

        # Verify at least one container exists
        self.assertGreater(len(sam_containers), 0, "Expected at least one running Lambda container")

        # Check DNS configuration in any of the containers
        dns_verified = False
        for container in sam_containers:
            try:
                container.reload()  # Refresh container state
                # Get DNS configuration from HostConfig
                host_config = container.attrs.get("HostConfig", {})
                container_dns = host_config.get("Dns", [])

                if container_dns:
                    # Verify our DNS servers are present
                    for expected_dns in self.dns_servers:
                        self.assertIn(
                            expected_dns,
                            container_dns,
                            f"Expected DNS server {expected_dns} not found in container {container.id}. "
                            f"Found: {container_dns}"
                        )
                    dns_verified = True
                    break  # Found a container with DNS configured

            except Exception as e:
                # Continue checking other containers if one fails
                continue

        self.assertTrue(
            dns_verified,
            f"Could not verify DNS configuration in any container. "
            f"Checked {len(sam_containers)} containers"
        )
