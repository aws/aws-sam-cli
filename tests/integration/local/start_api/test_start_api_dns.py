"""
Integration tests for DNS option in sam local start-api
"""

import time
import threading
import requests
import pytest
from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass
from tests.testing_utils import get_sam_command


class TestStartApiWithDNS(StartApiIntegBaseClass):
    """
    Test that --container-dns option is properly passed to start-api command
    and the service starts successfully with custom DNS configuration
    """

    template_path = "/testdata/start_api/template.yaml"

    @classmethod
    def setUpClass(cls):
        cls.dns_servers = ["8.8.8.8", "1.1.1.1"]

        command = get_sam_command()
        cls.command_list = [command, "local", "start-api", "-t", cls.integration_dir + cls.template_path]

        for dns_server in cls.dns_servers:
            cls.command_list += ["--container-dns", dns_server]

        super().setUpClass()

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_api_request_with_custom_dns(self):
        """
        Test that an API request succeeds when start-api
        is started with custom DNS servers
        """
        response = requests.get(f"http://127.0.0.1:{self.port}/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_dns_configured_in_container(self):
        """
        Test that DNS servers are actually configured in the Docker container.
        This inspects the container configuration to verify DNS was set correctly.
        """
        # Start async request to keep container alive during inspection
        response_holder = {}

        def make_request():
            response_holder["response"] = requests.get(
                f"http://127.0.0.1:{self.port}/sleepfortenseconds/function0", timeout=300
            )

        request_thread = threading.Thread(target=make_request)
        request_thread.start()

        # Wait for container to start and be in sleep phase
        time.sleep(7)

        sam_containers = self.docker_client.containers.list(
            all=False, filters={"label": "sam.cli.container.type=lambda"}
        )

        self.assertGreater(len(sam_containers), 0, "Expected at least one running Lambda container")

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
                            f"Expected DNS server {expected_dns} not found in container {container.id}. "
                            f"Found: {container_dns}",
                        )
                    dns_verified = True
                    break

            except Exception as e:
                continue

        self.assertTrue(
            dns_verified,
            f"Could not verify DNS configuration in any container. Checked {len(sam_containers)} containers",
        )

        # Wait for request to complete
        request_thread.join()
        self.assertEqual(response_holder["response"].status_code, 200)
