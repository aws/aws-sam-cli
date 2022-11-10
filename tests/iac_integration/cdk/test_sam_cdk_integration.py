from unittest import TestCase
from subprocess import Popen, PIPE
import os
import random
from pathlib import Path
import threading

import pytest
import requests
from parameterized import parameterized_class, parameterized

from tests.testing_utils import run_command, start_persistent_process, read_until_string, kill_process


@parameterized_class(
    ("cdk_project_path", "cdk_version", "cdk_stack_template"),
    [
        ("/testdata/cdk_v1/typescript", "1.x", "TestStack.template.json"),
        ("/testdata/cdk_v2/typescript", "2.x", "TestStack.template.json"),
        ("/testdata/cdk_v1/python", "1.x", "TestStack.template.json"),
        ("/testdata/cdk_v2/python", "2.x", "TestStack.template.json"),
        ("/testdata/cdk_v1/java", "1.x", "TestStack.template.json"),
        ("/testdata/cdk_v2/java", "2.x", "TestStack.template.json"),
    ],
)
class TestSamCdkIntegration(TestCase):
    integration_dir = str(Path(__file__).resolve().parents[0])
    cdk_project_path = ""
    cdk_version = ""
    cdk_stack_template = ""

    @classmethod
    def setUpClass(cls):
        cls.cdk_project = cls.integration_dir + cls.cdk_project_path
        cls.api_port = str(TestSamCdkIntegration.random_port())
        cls.build_cdk_project()
        cls.build()

        cls.start_api()
        cls.url = "http://127.0.0.1:{}".format(cls.api_port)

    @classmethod
    def build_cdk_project(cls):
        command_list = ["npx", f"aws-cdk@{cls.cdk_version}", "synth", "--no-staging"]
        working_dir = cls.cdk_project
        result = run_command(command_list, cwd=working_dir)
        if result.process.returncode != 0:
            raise Exception("cdk synth command failed")

    @classmethod
    def build(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"
        command_list = [command, "build", "-t", cls.cdk_stack_template]
        working_dir = cls.cdk_project + "/cdk.out"
        result = run_command(command_list, cwd=working_dir)
        if result.process.returncode != 0:
            raise Exception("sam build command failed")

    @classmethod
    def start_api(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        command_list = [command, "local", "start-api", "-p", cls.api_port]

        working_dir = cls.cdk_project + "/cdk.out"
        cls.start_api_process = Popen(command_list, cwd=working_dir, stderr=PIPE)

        while True:
            line = cls.start_api_process.stderr.readline()
            if "Press CTRL+C to quit" in str(line):
                break

        cls.stop_api_reading_thread = False

        def read_sub_process_stderr():
            while not cls.stop_api_reading_thread:
                cls.start_api_process.stderr.readline()

        cls.api_read_threading = threading.Thread(target=read_sub_process_stderr, daemon=True)
        cls.api_read_threading.start()

    @classmethod
    def tearDownClass(cls):
        # After all the tests run, we need to kill the start_lambda process.
        cls.stop_api_reading_thread = True
        kill_process(cls.start_api_process)

    @staticmethod
    def random_port():
        return random.randint(30000, 40000)

    @parameterized.expand(
        [
            ("/httpapis/nestedPythonFunction", "Hello World from Nested Python Function Construct 7"),
            ("/restapis/spec/pythonFunction", "Hello World from python function construct 7"),
            ("/restapis/normal/pythonFunction", "Hello World from python function construct 7"),
            ("/restapis/normal/functionPythonRuntime", "Hello World from function construct with python runtime 7"),
            ("/restapis/normal/preBuiltFunctionPythonRuntime", "Hello World from python pre built function 7"),
            (
                "/restapis/normal/bundledFunctionPythonRuntime",
                "Hello World from bundled function construct with python runtime 7",
            ),
            ("/restapis/normal/nodejsFunction", "Hello World from nodejs function construct 7"),
            ("/restapis/normal/functionNodeJsRuntime", "Hello World from function construct with nodejs runtime 7"),
            ("/restapis/normal/preBuiltFunctionNodeJsRuntime", "Hello World from nodejs pre built function 7"),
            ("/restapis/normal/goFunction", "Hello World from go function construct"),
            ("/restapis/normal/functionGoRuntime", "Hello World from function construct with go runtime"),
            ("/restapis/normal/dockerImageFunction", "Hello World from docker image function construct"),
            ("/restapis/normal/functionImageAsset", "Hello World from function construct with image asset"),
            (
                "/restapis/normal/dockerImageFunctionWithSharedCode",
                "Hello World from docker image function construct "
                "with a Dockerfile that shares code with another Dockerfile",
            ),
            (
                "/restapis/normal/functionImageAssetWithSharedCode",
                "Hello World from function construct with image asset "
                "with a Dockerfile that shares code with another Dockerfile",
            ),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=1000, method="thread")
    def test_invoke_api(self, url_suffix, expected_message):
        response = requests.get(self.url + url_suffix, timeout=800)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("message"), expected_message)
