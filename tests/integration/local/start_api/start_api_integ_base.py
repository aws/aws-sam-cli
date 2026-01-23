import shutil
import uuid
from typing import List, Optional, Dict
from unittest import TestCase, skipIf
import threading
from subprocess import Popen, PIPE
import os
import logging
from pathlib import Path

from docker.errors import APIError
from psutil import NoSuchProcess

from samcli.local.docker.utils import get_validated_container_client
from tests.integration.local.common_utils import InvalidAddressException, random_port, wait_for_local_process
from tests.testing_utils import kill_process, get_sam_command
from tests.testing_utils import SKIP_DOCKER_MESSAGE, SKIP_DOCKER_TESTS, run_command

LOG = logging.getLogger(__name__)


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class StartApiIntegBaseClass(TestCase):
    template: Optional[str] = None
    container_mode: Optional[str] = None
    parameter_overrides: Optional[Dict[str, str]] = None
    binary_data_file: Optional[str] = None
    integration_dir = str(Path(__file__).resolve().parents[2])
    invoke_image: Optional[List] = None
    layer_cache_base_dir: Optional[str] = None
    disable_authorizer: Optional[bool] = False
    config_file: Optional[str] = None
    container_host_interface: Optional[str] = None
    # container_labels no longer needed - container IDs are parsed from output

    build_before_invoke = False
    build_overrides: Optional[Dict[str, str]] = None

    do_collect_cmd_init_output: bool = False

    command_list = None
    project_directory = None

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        cls.template = cls.integration_dir + cls.template_path

        if cls.binary_data_file:
            cls.binary_data_file = os.path.join(cls.integration_dir, cls.binary_data_file)

        if cls.build_before_invoke:
            cls.build()

        cls.docker_client = get_validated_container_client()
        # Only remove containers with SAM CLI labels to avoid interfering with other processes
        try:
            sam_containers = cls.docker_client.containers.list(
                all=True, filters={"label": "sam.cli.container.type=lambda"}
            )
            for container in sam_containers:
                try:
                    container.remove(force=True)
                    LOG.info("Removed existing SAM CLI container %s", container.short_id)
                except APIError as ex:
                    LOG.error("Failed to remove existing SAM CLI container %s", container.short_id, exc_info=ex)
        except Exception as ex:
            LOG.error("Failed to clean up existing SAM CLI containers", exc_info=ex)
        cls.start_api_with_retry()

    @classmethod
    def build(cls):
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
    def start_api_with_retry(cls, retries=3):
        retry_count = 0
        while retry_count < retries:
            cls.port = str(random_port())
            try:
                cls.start_api()
            except InvalidAddressException:
                retry_count += 1
                continue
            break

        if retry_count == retries:
            raise ValueError("Ran out of retries attempting to start api")

    @classmethod
    def start_api(cls):
        command = get_sam_command()

        command_list = cls.command_list or [command, "local", "start-api", "-t", cls.template]
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

        # Container labels are no longer needed - container IDs are parsed from output

        if cls.config_file:
            command_list += ["--config-file", cls.config_file]

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
            while not cls.stop_reading_thread:
                line = cls.start_api_process.stderr.readline()
                if line:
                    line_str = line.decode("utf-8").strip()
                    cls.start_api_process_output += line_str + "\n"
                    if line.strip():
                        LOG.info(line)

        def read_sub_process_stdout():
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
    def _make_parameter_override_arg(self, overrides):
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    @classmethod
    def tearDownClass(cls):
        # After all the tests run, we need to kill the start-api process.
        cls.stop_reading_thread = True
        try:
            kill_process(cls.start_api_process)
        except NoSuchProcess:
            LOG.info("Process has already been terminated")

        # Clean up any remaining SAM CLI containers
        try:
            docker_client = get_validated_container_client()
            # Only remove containers with SAM CLI labels to avoid interfering with other processes
            sam_containers = docker_client.containers.list(all=True, filters={"label": "sam.cli.container.type=lambda"})
            for container in sam_containers:
                try:
                    container.remove(force=True)
                    LOG.info("Removed SAM CLI container %s", container.short_id)
                except APIError as ex:
                    LOG.error("Failed to remove SAM CLI container %s", container.short_id, exc_info=ex)
        except Exception as ex:
            LOG.error("Failed to clean up SAM CLI containers", exc_info=ex)

    @staticmethod
    def get_binary_data(filename):
        if not filename:
            return None

        with open(filename, "rb") as fp:
            return fp.read()


class WritableStartApiIntegBaseClass(StartApiIntegBaseClass):
    temp_path: Optional[str] = None
    template_path: Optional[str] = None
    code_path: Optional[str] = None
    docker_file_path: Optional[str] = None

    template_content: Optional[str] = None
    code_content: Optional[str] = None
    docker_file_content: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        cls.temp_path = str(uuid.uuid4()).replace("-", "")[:10]
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir, ignore_errors=True)
        os.mkdir(working_dir)
        os.mkdir(Path(cls.integration_dir).resolve().joinpath(cls.temp_path).joinpath("dir"))
        cls.template_path = f"/{cls.temp_path}/template.yaml"
        cls.code_path = f"/{cls.temp_path}/main.py"
        cls.code_path2 = f"/{cls.temp_path}/dir/main2.py"
        cls.docker_file_path = f"/{cls.temp_path}/Dockerfile"
        cls.docker_file_path2 = f"/{cls.temp_path}/Dockerfile2"

        if cls.template_content:
            cls._write_file_content(cls.template_path, cls.template_content)

        if cls.code_content:
            cls._write_file_content(cls.code_path, cls.code_content)

        if cls.docker_file_content:
            cls._write_file_content(cls.docker_file_path, cls.docker_file_content)

        super().setUpClass()

    @classmethod
    def _write_file_content(cls, path, content):
        with open(cls.integration_dir + path, "w") as f:
            f.write(content)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir, ignore_errors=True)
