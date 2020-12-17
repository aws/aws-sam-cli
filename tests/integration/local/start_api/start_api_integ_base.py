import signal
from unittest import TestCase, skipIf
import threading
from subprocess import Popen
import time
import os
import random
from pathlib import Path

from tests.testing_utils import SKIP_DOCKER_MESSAGE, SKIP_DOCKER_TESTS


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class StartApiIntegBaseClass(TestCase):
    template = None
    container_mode = None
    parameter_overrides = None
    binary_data_file = None
    integration_dir = str(Path(__file__).resolve().parents[2])

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        cls.template = cls.integration_dir + cls.template_path

        if cls.binary_data_file:
            cls.binary_data_file = os.path.join(cls.integration_dir, cls.binary_data_file)

        cls.port = str(StartApiIntegBaseClass.random_port())

        cls.thread = threading.Thread(target=cls.start_api())
        cls.thread.setDaemon(True)
        cls.thread.start()

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
