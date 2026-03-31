"""
Integration tests for DNS option in sam local invoke
"""

import time
import threading
import pytest
from pathlib import Path
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from samcli.local.docker.utils import get_validated_container_client


class TestInvokeWithDNS(InvokeIntegBase):
    """
    Test that --container-dns option is properly passed to invoke command
    and DNS configuration is applied to containers
    """

    template = Path("template.yml")

    def setUp(self):
        self.dns_servers = ["8.8.8.8", "1.1.1.1"]
        self.docker_client = get_validated_container_client()

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_custom_dns(self):
        """
        Test that a function can be invoked successfully with custom DNS servers
        and verify DNS configuration is applied to the container.

        Uses a function that sleeps for 10 seconds to keep the container alive
        long enough for inspection.
        """
        from subprocess import Popen, PIPE, TimeoutExpired

        command_list = self.get_command_list(
            function_to_invoke="TimeoutFunctionWithParameter",
            template_path=self.template_path,
            no_event=True,
            parameter_overrides={"DefaultTimeout": "15"},  # Increase timeout to 15s
        )

        # Add DNS options
        for dns_server in self.dns_servers:
            command_list += ["--container-dns", dns_server]

        # Start invoke process (don't wait for it)
        process = Popen(command_list, stdout=PIPE, stderr=PIPE)

        try:
            # Poll for container - it should appear while function is sleeping
            sam_containers = []
            max_attempts = 50  # Poll for up to 5 seconds (50 * 0.1s)
            for attempt in range(max_attempts):
                time.sleep(0.1)
                sam_containers = self.docker_client.containers.list(
                    all=False, filters={"label": "sam.cli.container.type=lambda"}
                )
                if sam_containers:
                    break

            self.assertGreater(len(sam_containers), 0, "Expected at least one running Lambda container")

            # Check DNS configuration
            dns_verified = False
            for container in sam_containers:
                try:
                    container.reload()
                    host_config = container.attrs.get("HostConfig", {})
                    container_dns = host_config.get("Dns", [])

                    if container_dns:
                        for expected_dns in self.dns_servers:
                            self.assertIn(
                                expected_dns,
                                container_dns,
                                f"Expected DNS server {expected_dns} not found. Found: {container_dns}",
                            )
                        dns_verified = True
                        break
                except Exception as e:
                    continue

            self.assertTrue(dns_verified, "Could not verify DNS configuration in any container")

            # Now wait for invoke to complete
            stdout, stderr = process.communicate(timeout=300)
            self.assertEqual(process.returncode, 0, f"Invoke failed with stderr: {stderr.decode('utf-8')}")

        except TimeoutExpired:
            process.kill()
            process.wait()
            self.fail("Process timed out")

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_accepts_multiple_dns_servers(self):
        """
        Test that invoke command accepts multiple --container-dns options
        and executes successfully
        """
        command_list = self.get_command_list(
            function_to_invoke="TimeoutFunctionWithParameter",
            template_path=self.template_path,
            no_event=True,
            parameter_overrides={"DefaultTimeout": "15"},  # Increase timeout to 15s
        )

        # Add multiple DNS options
        command_list += ["--container-dns", "8.8.8.8"]
        command_list += ["--container-dns", "1.1.1.1"]
        command_list += ["--container-dns", "8.8.4.4"]

        stdout, stderr, return_code = self.run_command(command_list)

        self.assertEqual(return_code, 0, f"Command failed with stderr: {stderr}")

        # Verify we got valid output
        output = stdout.decode("utf-8")
        self.assertIn("Slept", output)
