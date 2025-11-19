"""
Shared base class for start-api and start-function-urls integration tests
"""

import logging
import os
import shutil
import threading
import uuid
from pathlib import Path
from subprocess import PIPE, Popen
from typing import Dict, List, Optional
from unittest import TestCase, skipIf

import docker
from docker.errors import APIError
from psutil import NoSuchProcess

from tests.integration.local.common_utils import InvalidAddressException, random_port, wait_for_local_process
from tests.testing_utils import (
    SKIP_DOCKER_MESSAGE,
    SKIP_DOCKER_TESTS,
    get_sam_command,
    kill_process,
    run_command,
)

LOG = logging.getLogger(__name__)


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class SharedStartServiceBaseClass(TestCase):
    """
    Shared base class for integration tests of local services (start-api, start-function-urls, etc.)
    
    This class provides common functionality for:
    - Docker client setup and cleanup
    - Build process
    - Parameter override handling
    - Service startup with retry logic
    - Thread management for process output
    - Teardown and cleanup
    """

    template: Optional[str] = None
    container_mode: Optional[str] = None
    parameter_overrides: Optional[Dict[str, str]] = None
    binary_data_file: Optional[str] = None
    integration_dir = str(Path(__file__).resolve().parents[1])
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
        """Set up test class - initialize paths and start service"""
        # This is the directory for tests/integration
        cls.integration_dir = str(Path(__file__).resolve().parents[1])

        if hasattr(cls, "template_path"):
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

        # Start the service with retry logic
        cls.start_service_with_retry()

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
    def start_service_with_retry(cls, retries=3):
        """Start service with retry logic"""
        retry_count = 0
        while retry_count < retries:
            cls.port = str(random_port())
            try:
                cls.start_service()
            except InvalidAddressException:
                retry_count += 1
                continue
            break

        if retry_count == retries:
            raise ValueError("Ran out of retries attempting to start service")

    @classmethod
    def start_service(cls):
        """
        Start the service - must be implemented by subclasses
        This method should start the specific service (start-api, start-function-urls, etc.)
        """
        raise NotImplementedError("Subclasses must implement start_service()")

    @classmethod
    def _make_parameter_override_arg(cls, overrides):
        """Make parameter override argument string"""
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    @classmethod
    def _start_process_with_output_threads(cls, command_list, process_attr_name="service_process"):
        """
        Common method to start a process and set up output reading threads
        
        Parameters
        ----------
        command_list : list
            Command and arguments to execute
        process_attr_name : str
            Attribute name to store the process object (default: 'service_process')
        """
        process = (
            Popen(command_list, stderr=PIPE, stdout=PIPE)
            if not cls.project_directory
            else Popen(command_list, stderr=PIPE, stdout=PIPE, cwd=cls.project_directory)
        )
        setattr(cls, process_attr_name, process)
        
        output = wait_for_local_process(process, cls.port, collect_output=cls.do_collect_cmd_init_output)
        setattr(cls, f"{process_attr_name}_output", output)

        cls.stop_reading_thread = False

        def read_sub_process_stderr():
            while not cls.stop_reading_thread:
                line = process.stderr.readline()
                LOG.info(line)

        def read_sub_process_stdout():
            while not cls.stop_reading_thread:
                LOG.info(process.stdout.readline())

        cls.read_threading = threading.Thread(target=read_sub_process_stderr, daemon=True)
        cls.read_threading.start()

        cls.read_threading2 = threading.Thread(target=read_sub_process_stdout, daemon=True)
        cls.read_threading2.start()

    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        # Stop reading threads
        cls.stop_reading_thread = True

        # Kill the service process
        try:
            if hasattr(cls, "service_process"):
                kill_process(cls.service_process)
            # Also try common alternative names
            if hasattr(cls, "start_api_process"):
                kill_process(cls.start_api_process)
            if hasattr(cls, "start_function_urls_process"):
                kill_process(cls.start_function_urls_process)
        except (NoSuchProcess, AttributeError) as e:
            LOG.info(f"Process cleanup: {e}")

    @staticmethod
    def get_binary_data(filename):
        """Get binary data from file"""
        if not filename:
            return None

        with open(filename, "rb") as fp:
            return fp.read()


class WritableSharedStartServiceBaseClass(SharedStartServiceBaseClass):
    """
    Shared base class for integration tests with writable templates
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
        cls.integration_dir = str(Path(__file__).resolve().parents[1])

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
