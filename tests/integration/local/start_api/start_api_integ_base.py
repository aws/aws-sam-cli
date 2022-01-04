import shutil
import uuid
from typing import List, Optional, Dict
from unittest import TestCase, skipIf
import threading
from subprocess import Popen
import time
import os
import random
from pathlib import Path

import docker

from tests.testing_utils import SKIP_DOCKER_MESSAGE, SKIP_DOCKER_TESTS, run_command


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class StartApiIntegBaseClass(TestCase):
    template: Optional[str] = None
    container_mode: Optional[str] = None
    parameter_overrides: Optional[Dict[str, str]] = None
    binary_data_file: Optional[str] = None
    integration_dir = str(Path(__file__).resolve().parents[2])
    invoke_image: Optional[List] = None

    build_before_invoke = False
    build_overrides: Optional[Dict[str, str]] = None

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        cls.template = cls.integration_dir + cls.template_path

        if cls.binary_data_file:
            cls.binary_data_file = os.path.join(cls.integration_dir, cls.binary_data_file)

        if cls.build_before_invoke:
            cls.build()

        cls.port = str(StartApiIntegBaseClass.random_port())

        cls.docker_client = docker.from_env()
        for container in cls.docker_client.api.containers():
            cls.docker_client.api.remove_container(container, force=True)

        cls.thread = threading.Thread(target=cls.start_api())
        cls.thread.setDaemon(True)
        cls.thread.start()

    @classmethod
    def build(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"
        command_list = [command, "build"]
        if cls.build_overrides:
            overrides_arg = " ".join(
                ["ParameterKey={},ParameterValue={}".format(key, value) for key, value in cls.build_overrides.items()]
            )
            command_list += ["--parameter-overrides", overrides_arg]
        working_dir = str(Path(cls.template).resolve().parents[0])
        run_command(command_list, cwd=working_dir)

    @classmethod
    def start_api(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        command_list = [command, "local", "start-api", "-t", cls.template, "-p", cls.port]

        if cls.container_mode:
            command_list += ["--warm-containers", cls.container_mode]

        if cls.parameter_overrides:
            command_list += ["--parameter-overrides", cls._make_parameter_override_arg(cls.parameter_overrides)]

        if cls.invoke_image:
            for image in cls.invoke_image:
                command_list += ["--invoke-image", image]

        cls.start_api_process = Popen(command_list)
        # we need to wait some time for start-api to start, hence the sleep
        time.sleep(5)

    @classmethod
    def _make_parameter_override_arg(self, overrides):
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    @classmethod
    def tearDownClass(cls):
        # After all the tests run, we need to kill the start-api process.
        cls.start_api_process.kill()

    @staticmethod
    def random_port():
        return random.randint(30000, 40000)

    @staticmethod
    def get_binary_data(filename):
        if not filename:
            return None

        with open(filename, "rb") as fp:
            return fp.read()


class WatchWarmContainersIntegBaseClass(StartApiIntegBaseClass):
    temp_path: Optional[str] = None
    template_path: Optional[str] = None
    code_path: Optional[str] = None
    docker_file_path: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        cls.temp_path = str(uuid.uuid4()).replace("-", "")[:10]
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir)
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
        working_dir = str(Path(cls.integration_dir).resolve().joinpath(cls.temp_path))
        if Path(working_dir).resolve().exists():
            shutil.rmtree(working_dir)
        super().tearDownClass()
