"""
Base class for start-function-urls integration tests
"""

import logging
import random
import threading
import time
from pathlib import Path
from subprocess import PIPE, Popen
from typing import Any, Dict, List, Optional

import requests
from psutil import NoSuchProcess

from tests.integration.local.common_utils import wait_for_local_process
from tests.integration.local.shared_start_service_base import (
    SharedStartServiceBaseClass,
    WritableSharedStartServiceBaseClass,
)
from tests.testing_utils import (
    get_sam_command,
    kill_process,
    run_command_with_input,
)

LOG = logging.getLogger(__name__)


class StartFunctionUrlIntegBaseClass(SharedStartServiceBaseClass):
    """
    Base class for start-function-urls integration tests
    Inherits common functionality from SharedStartServiceBaseClass
    """

    @classmethod
    def start_service(cls):
        """Start the function URLs service"""
        command = get_sam_command()

        command_list = cls.command_list or [command, "local", "start-function-urls", "--template", cls.template]
        command_list.extend(["--port-range", f"{cls.port}-{int(cls.port)+10}"])
        command_list.append("--beta-features")  # Add beta features flag to bypass prompt

        if cls.container_mode:
            command_list += ["--warm-containers", cls.container_mode]

        if cls.parameter_overrides:
            command_list += ["--parameter-overrides", cls._make_parameter_override_arg(cls.parameter_overrides)]

        if cls.layer_cache_base_dir:
            command_list += ["--layer-cache-basedir", cls.layer_cache_base_dir]

        if cls.invoke_image:
            for image in cls.invoke_image:
                command_list += ["--invoke-image", image]

        if cls.config_file:
            command_list += ["--config-file", cls.config_file]

        cls.start_function_urls_process = (
            Popen(command_list, stderr=PIPE, stdout=PIPE)
            if not cls.project_directory
            else Popen(command_list, stderr=PIPE, stdout=PIPE, cwd=cls.project_directory)
        )
        cls.start_function_urls_process_output = wait_for_local_process(
            cls.start_function_urls_process, cls.port, collect_output=cls.do_collect_cmd_init_output
        )

        cls.stop_reading_thread = False

        def read_sub_process_stderr():
            while not cls.stop_reading_thread:
                line = cls.start_function_urls_process.stderr.readline()
                if line:  # Only log if there's actual content
                    LOG.info(line.decode('utf-8').strip() if isinstance(line, bytes) else line.strip())

        def read_sub_process_stdout():
            while not cls.stop_reading_thread:
                line = cls.start_function_urls_process.stdout.readline()
                if line:  # Only log if there's actual content
                    LOG.info(line.decode('utf-8').strip() if isinstance(line, bytes) else line.strip())

        cls.read_threading = threading.Thread(target=read_sub_process_stderr, daemon=True)
        cls.read_threading.start()

        cls.read_threading2 = threading.Thread(target=read_sub_process_stdout, daemon=True)
        cls.read_threading2.start()

    @classmethod
    def _make_parameter_override_arg(cls, overrides):
        """Make parameter override argument string"""
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        # After all the tests run, we need to kill the start-function-urls process
        cls.stop_reading_thread = True

        # Stop the reading threads first
        if hasattr(cls, "read_threading"):
            cls.read_threading.join(timeout=1)
        if hasattr(cls, "read_threading2"):
            cls.read_threading2.join(timeout=1)

        try:
            if hasattr(cls, "start_function_urls_process"):
                # First try to terminate gracefully
                cls.start_function_urls_process.terminate()
                try:
                    cls.start_function_urls_process.wait(timeout=2)
                except:
                    # If that doesn't work, force kill
                    kill_process(cls.start_function_urls_process)
                finally:
                    # Close the pipes to prevent resource warnings
                    if cls.start_function_urls_process.stdout:
                        cls.start_function_urls_process.stdout.close()
                    if cls.start_function_urls_process.stderr:
                        cls.start_function_urls_process.stderr.close()
        except (NoSuchProcess, AttributeError) as e:
            LOG.info(f"Process cleanup: {e}")

    @staticmethod
    def get_binary_data(filename):
        """Get binary data from file"""
        if not filename:
            return None

        with open(filename, "rb") as fp:
            return fp.read()

    def setUp(self):
        """Set up test method"""
        super().setUp()
        self.cmd = get_sam_command()
        self.port = str(random.randint(3001, 4000))
        self.host = "127.0.0.1"
        self.url = f"http://{self.host}:{self.port}"
        self.process = None
        self.thread = None

    def tearDown(self):
        """Tear down test method"""
        if self.process:
            try:
                self.process.kill()
            except:
                pass
            self.process = None
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        super().tearDown()

    def start_function_urls(
        self,
        template_path: str,
        port: Optional[str] = None,
        env_vars: Optional[str] = None,
        parameter_overrides: Optional[Dict[str, str]] = None,
        docker_network: Optional[str] = None,
        container_host: Optional[str] = None,
        extra_args: Optional[str] = None,
        timeout: int = 30,  # Increased timeout from 15 to 30 seconds
    ):
        """
        Start the function URLs service in a background thread

        Parameters
        ----------
        template_path : str
            Path to SAM template
        port : Optional[str]
            Port to run service on
        env_vars : Optional[str]
            Path to environment variables file
        parameter_overrides : Optional[Dict[str, str]]
            Parameter overrides for the template
        docker_network : Optional[str]
            Docker network to use
        container_host : Optional[str]
            Container host to use
        extra_args : Optional[str]
            Extra arguments to pass to the command
        timeout : int
            Timeout for starting the service
        """
        port_to_use = port or self.port
        command_list = [
            self.cmd,
            "local",
            "start-function-urls",
            "--template",
            template_path,
            "--port-range",
            f"{port_to_use}-{int(port_to_use)+10}",
            "--host",
            self.host,
            "--beta-features",  # Add beta features flag to bypass prompt
        ]

        if env_vars:
            command_list.extend(["--env-vars", env_vars])

        if parameter_overrides:
            overrides = " ".join([f"{k}={v}" for k, v in parameter_overrides.items()])
            command_list.extend(["--parameter-overrides", overrides])

        if docker_network:
            command_list.extend(["--docker-network", docker_network])

        if container_host:
            command_list.extend(["--container-host", container_host])

        if extra_args:
            command_list.extend(extra_args.split())

        def run_command():
            import os

            env = os.environ.copy()
            env["SAM_CLI_BETA_FEATURES"] = "1"
            self.process = run_command_with_input(command_list, b"y\n", env=env)

        self.thread = threading.Thread(target=run_command)
        self.thread.start()

        # Wait for service to start - try multiple ports in the range
        start_time = time.time()
        port_range_start = int(port_to_use)
        port_range_end = port_range_start + 10

        while time.time() - start_time < timeout:
            # Try all ports in the range
            for test_port in range(port_range_start, port_range_end + 1):
                test_url = f"http://{self.host}:{test_port}"
                try:
                    response = requests.get(f"{test_url}/", timeout=2)  # Increased timeout
                    if response.status_code in [200, 403, 404]:
                        # Give extra time for full initialization
                        time.sleep(3)
                        return True
                except requests.exceptions.RequestException:
                    pass
            time.sleep(1)  # Increased sleep between retries

        return False


class WritableStartFunctionUrlIntegBaseClass(WritableSharedStartServiceBaseClass, StartFunctionUrlIntegBaseClass):
    """
    Base class for start-function-urls integration tests with writable templates
    Inherits from both WritableSharedStartServiceBaseClass (for file management) 
    and StartFunctionUrlIntegBaseClass (for function URL specific methods)
    """

    @classmethod
    def start_service(cls):
        """Start the function URLs service - delegates to StartFunctionUrlIntegBaseClass implementation"""
        # Use the same implementation as StartFunctionUrlIntegBaseClass
        StartFunctionUrlIntegBaseClass.start_service.__func__(cls)
