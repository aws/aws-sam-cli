"""
Integration tests for DNS option in sam local start-api
"""

import requests
import pytest
from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass


class TestStartApiWithDNS(StartApiIntegBaseClass):
    """
    Test that --container-dns option is properly passed to start-api command
    and the service starts successfully with custom DNS configuration
    """

    template_path = "/testdata/start_api/template.yaml"

    @classmethod
    def setUpClass(cls):
        # Set DNS options before starting the service
        cls.dns_servers = ["8.8.8.8", "1.1.1.1"]
        super().setUpClass()

    @classmethod
    def start_api(cls):
        """Override to add DNS options to the start-api command"""
        # Get the base command
        command = cls._get_sam_command()
        from tests.testing_utils import get_sam_command

        command_list = cls.command_list or [get_sam_command(), "local", "start-api", "-t", cls.template]
        command_list.extend(["-p", cls.port])

        if cls.container_mode:
            command_list += ["--warm-containers", cls.container_mode]

        if cls.parameter_overrides:
            command_list += ["--parameter-overrides", cls._make_parameter_override_arg(cls.parameter_overrides)]

        if cls.layer_cache_base_dir:
            command_list += ["--layer-cache-basedir", cls.layer_cache_base_dir]

        if cls.invoke_image:
            for image in cls.invoke_image:
                command_list += ["--invoke-image", image]

        if cls.disable_authorizer:
            command_list += ["--disable-authorizer"]

        if cls.container_host_interface:
            command_list += ["--container-host-interface", cls.container_host_interface]

        if cls.config_file:
            command_list += ["--config-file", cls.config_file]

        # Add DNS options
        if hasattr(cls, "dns_servers") and cls.dns_servers:
            for dns_server in cls.dns_servers:
                command_list += ["--container-dns", dns_server]

        # Start the process using the parent class's logic
        from subprocess import Popen, PIPE
        from tests.integration.local.common_utils import wait_for_local_process
        import threading

        cls.start_api_process = (
            Popen(command_list, stderr=PIPE, stdout=PIPE)
            if not cls.project_directory
            else Popen(command_list, stderr=PIPE, stdout=PIPE, cwd=cls.project_directory)
        )
        cls.start_api_process_output = wait_for_local_process(
            cls.start_api_process, cls.port, collect_output=cls.do_collect_cmd_init_output
        )

        cls.stop_reading_thread = False

        def read_sub_process_stderr():
            import logging

            LOG = logging.getLogger(__name__)
            while not cls.stop_reading_thread:
                line = cls.start_api_process.stderr.readline()
                if line:
                    line_str = line.decode("utf-8").strip()
                    cls.start_api_process_output += line_str + "\n"
                    if line.strip():
                        LOG.info(line)

        def read_sub_process_stdout():
            import logging

            LOG = logging.getLogger(__name__)
            while not cls.stop_reading_thread:
                line = cls.start_api_process.stdout.readline()
                if line:
                    line_str = line.decode("utf-8").strip()
                    cls.start_api_process_output += line_str + "\n"
                    if line.strip():
                        LOG.info(line)

        cls.read_threading = threading.Thread(target=read_sub_process_stderr, daemon=True)
        cls.read_threading.start()

        cls.read_threading2 = threading.Thread(target=read_sub_process_stdout, daemon=True)
        cls.read_threading2.start()

    @classmethod
    def _get_sam_command(cls):
        from tests.testing_utils import get_sam_command

        return get_sam_command()

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
        # Make a request to trigger container creation
        response = requests.get(f"http://127.0.0.1:{self.port}/anyandall", timeout=300)
        self.assertEqual(response.status_code, 200)

        sam_containers = self.docker_client.containers.list(
            all=False, filters={"label": "sam.cli.container.type=lambda"}
        )

        self.assertGreater(len(sam_containers), 0, "Expected at least one running Lambda container")

        # Check DNS configuration in any of the containers
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
                    # Found a container with DNS configured
                    break

            except Exception as e:
                # Continue checking other containers if one fails
                continue

        self.assertTrue(
            dns_verified,
            f"Could not verify DNS configuration in any container. " f"Checked {len(sam_containers)} containers",
        )
