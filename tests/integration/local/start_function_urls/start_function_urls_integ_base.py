"""
Base class for start-function-urls integration tests
"""

import json
import os
import random
import shutil
import tempfile
import time
import threading
import uuid
import logging
from pathlib import Path
from subprocess import Popen, PIPE
from typing import Optional, Dict, Any, List
from unittest import TestCase, skipIf

import docker
import requests
from docker.errors import APIError
from psutil import NoSuchProcess

from tests.integration.local.common_utils import InvalidAddressException, random_port, wait_for_local_process
from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    SKIP_DOCKER_MESSAGE,
    SKIP_DOCKER_TESTS,
    run_command,
    run_command_with_input,
    get_sam_command,
    kill_process,
)

LOG = logging.getLogger(__name__)


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class StartFunctionUrlsIntegBaseClass(TestCase):
    """
    Base class for start-function-urls integration tests
    """
    template: Optional[str] = None
    container_mode: Optional[str] = None
    parameter_overrides: Optional[Dict[str, str]] = None
    binary_data_file: Optional[str] = None
    integration_dir = str(Path(__file__).resolve().parents[2])
    invoke_image: Optional[List] = None
    layer_cache_base_dir: Optional[str] = None
    config_file: Optional[str] = None

    build_before_invoke = False
    build_overrides: Optional[Dict[str, str]] = None

    do_collect_cmd_init_output: bool = False

    command_list = None
    project_directory = None

    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        # This is the directory for tests/integration which will be used to find the testdata
        # files for integ tests
        cls.integration_dir = str(Path(__file__).resolve().parents[2])
        
        if hasattr(cls, 'template_path'):
            cls.template = cls.integration_dir + cls.template_path

        if cls.binary_data_file:
            cls.binary_data_file = os.path.join(cls.integration_dir, cls.binary_data_file)

        if cls.build_before_invoke:
            cls.build()

        # Initialize Docker client and clean up containers
        cls.docker_client = docker.from_env()
        for container in cls.docker_client.api.containers():
            try:
                cls.docker_client.api.remove_container(container, force=True)
            except APIError as ex:
                LOG.error("Failed to remove container %s", container, exc_info=ex)
        
        # Start the function URLs service
        cls.start_function_urls_with_retry()

    @classmethod
    def build(cls):
        """Build the SAM application"""
        command = get_sam_command()
        command_list = [command, "build"]
        if cls.build_overrides:
            overrides_arg = " ".join(
                ["ParameterKey={},ParameterValue={}".format(key, value) for key, value in cls.build_overrides.items()]
            )
            command_list += ["--parameter-overrides", overrides_arg]
        working_dir = str(Path(cls.template).resolve().parents[0])
        run_command(command_list, cwd=working_dir)

    @classmethod
    def start_function_urls_with_retry(cls, retries=3):
        """Start function URLs service with retry logic"""
        retry_count = 0
        while retry_count < retries:
            cls.port = str(random_port())
            try:
                cls.start_function_urls_service()
            except InvalidAddressException:
                retry_count += 1
                continue
            break

        if retry_count == retries:
            raise ValueError("Ran out of retries attempting to start function URLs service")

    @classmethod
    def start_function_urls_service(cls):
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
                LOG.info(line)

        def read_sub_process_stdout():
            while not cls.stop_reading_thread:
                LOG.info(cls.start_function_urls_process.stdout.readline())

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
        if hasattr(cls, 'read_threading'):
            cls.read_threading.join(timeout=1)
        if hasattr(cls, 'read_threading2'):
            cls.read_threading2.join(timeout=1)
            
        try:
            if hasattr(cls, 'start_function_urls_process'):
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
        timeout: int = 10,
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
            self.process = run_command_with_input(command_list, "")

        self.thread = threading.Thread(target=run_command)
        self.thread.start()

        # Wait for service to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.url}/", timeout=1)
                if response.status_code in [200, 403, 404]:
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)

        return False


class WritableStartFunctionUrlsIntegBaseClass(StartFunctionUrlsIntegBaseClass):
    """
    Base class for start-function-urls integration tests with writable templates
    """
    temp_path: Optional[str] = None
    template_path: Optional[str] = None
    code_path: Optional[str] = None
    docker_file_path: Optional[str] = None

    template_content: Optional[str] = None
    code_content: Optional[str] = None
    docker_file_content: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        """Set up test class with writable templates"""
        # Set up the integration directory first
        cls.integration_dir = str(Path(__file__).resolve().parents[2])
        
        # Create temporary directory for test files
        cls.temp_path = str(uuid.uuid4()).replace("-", "")[:10]
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir, ignore_errors=True)
        os.mkdir(working_dir)
        os.mkdir(Path(cls.integration_dir).resolve().joinpath(cls.temp_path).joinpath("dir"))
        
        # Set up file paths
        cls.template_path = f"/{cls.temp_path}/template.yaml"
        cls.code_path = f"/{cls.temp_path}/main.py"
        cls.code_path2 = f"/{cls.temp_path}/dir/main2.py"
        cls.docker_file_path = f"/{cls.temp_path}/Dockerfile"
        cls.docker_file_path2 = f"/{cls.temp_path}/Dockerfile2"

        # Write file contents
        if cls.template_content:
            cls._write_file_content(cls.template_path, cls.template_content)

        if cls.code_content:
            cls._write_file_content(cls.code_path, cls.code_content)

        if cls.docker_file_content:
            cls._write_file_content(cls.docker_file_path, cls.docker_file_content)

        # Call parent setUpClass
        super().setUpClass()

    @classmethod
    def _write_file_content(cls, path, content):
        """Write content to file"""
        with open(cls.integration_dir + path, "w") as f:
            f.write(content)

    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        super().tearDownClass()
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir, ignore_errors=True)
