from asyncio import subprocess
import os
import platform
from queue import Queue
import shutil
from signal import CTRL_C_EVENT
from subprocess import CREATE_NEW_CONSOLE, CREATE_NEW_PROCESS_GROUP, PIPE, Popen
from threading import Thread
import uuid

import logging
import json
import tempfile
import time
from pathlib import Path
from unittest import skipIf

import boto3
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase

from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")

LOG = logging.getLogger(__name__)

LOG.handlers = []  # This is the key thing for the question!

# Start defining and assigning your handlers here
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncWatch(BuildIntegBase, PackageIntegBase, SyncIntegBase):
    @classmethod
    def setUpClass(cls):
        PackageIntegBase.setUpClass()
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "sync")

    def setUp(self):
        self.cfn_client = boto3.client("cloudformation")
        self.ecr_client = boto3.client("ecr")
        self.lambda_client = boto3.client("lambda")
        self.api_client = boto3.client("apigateway")
        self.sfn_client = boto3.client("stepfunctions")
        self.stacks = []
        self.s3_prefix = uuid.uuid4().hex
        self.test_dir = Path(tempfile.mkdtemp())
        # Remove temp dir so that shutil.copytree will not throw an error
        # Needed for python 3.6 and 3.7 as these versions don't have dirs_exist_ok
        shutil.rmtree(self.test_dir)
        shutil.copytree(self.test_data_path, self.test_dir)
        super().setUp()

    def tearDown(self):
        self.watch_process.terminate()
        # Close pipes
        self.watch_process.communicate()
        self.watch_process.wait()
        shutil.rmtree(self.test_dir)
        for stack in self.stacks:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                region = stack.get("region")
                cfn_client = (
                    self.cfn_client if not region else boto3.client("cloudformation", config=Config(region_name=region))
                )
                ecr_client = self.ecr_client if not region else boto3.client("ecr", config=Config(region_name=region))
                self._delete_companion_stack(cfn_client, ecr_client, self._stack_name_to_companion_stack(stack_name))
                cfn_client.delete_stack(StackName=stack_name)
        super().tearDown()

    def test_sync_watch(self):
        runtime = "python"
        template_before = f"infra/template-{runtime}-before.yaml"
        template_path = self.test_dir.joinpath(template_before)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=False,
            watch=True,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        self.watch_process = self.get_watch_process(sync_command_list)
        self.read_until(self.watch_process, "Enter Y to proceed with the command, or enter N to cancel:\n")

        self.watch_process.stdin.write("y\n")

        self.read_until(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=300)

        self.update_file(
            self.test_dir.joinpath("infra/template-python-after.yaml"),
            self.test_dir.joinpath("infra/template-python-before.yaml"),
        )

        self.read_until(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=300)
        time.sleep(2)

        self.watch_process.terminate()
        # self.read_until(watch_process, "abc\n")
        self.watch_process.wait(timeout=5)

    def get_watch_process(self, command_list):
        return Popen(
            command_list,
            stdout=PIPE,
            stderr=subprocess.STDOUT,
            stdin=PIPE,
            encoding="utf-8",
            bufsize=1,
            cwd=self.test_dir,
        )

    def update_file(self, source, destination):
        with open(source, "rb") as source_file:
            with open(destination, "wb") as destination_file:
                destination_file.write(source_file.read())

    def read_until(self, process, expected_output, timeout=5):
        result_queue = Queue()

        def _read_output():
            try:
                for output in process.stdout:
                    LOG.info(output.encode("utf-8"))
                    if output == expected_output:
                        result_queue.put(True)
                        return
            except Exception as ex:
                result_queue.put(ex)

        reading_thread = Thread(target=_read_output, daemon=True)
        reading_thread.start()
        reading_thread.join(timeout=timeout)
        if reading_thread.isAlive():
            expected_output_bytes = expected_output.encode("utf-8")
            raise TimeoutError(
                f"Did not get expected output after {timeout} seconds. Expected output: {expected_output_bytes}"
            )
        if result_queue.qsize() > 0:
            result = result_queue.get()
            if isinstance(result, Exception):
                raise result
        else:
            raise ValueError()
