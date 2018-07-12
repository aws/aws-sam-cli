from unittest import TestCase
import threading
from subprocess import Popen
import time
import os
import random

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class StartLambdaIntegBaseClass(TestCase):
    template = None
    binary_data_file = None
    integration_dir = str(Path(__file__).resolve().parents[2])

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        cls.template = cls.integration_dir + cls.template_path
        cls.port = str(StartLambdaIntegBaseClass.random_port())

        cls.thread = threading.Thread(target=cls.start_lambda())
        cls.thread.setDaemon(True)
        cls.thread.start()

    @classmethod
    def start_lambda(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        cls.start_lambda_process = \
            Popen([command, "local", "start-lambda", "-t", cls.template, "-p", cls.port, "--debug"])
        # we need to wait some time for start-lambda to start, hence the sleep
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        # After all the tests run, we need to kill the start-lambda process.
        cls.start_lambda_process.kill()

    @staticmethod
    def random_port():
        return random.randint(30000, 40000)
