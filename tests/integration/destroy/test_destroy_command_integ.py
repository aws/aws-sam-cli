import logging
import os
import re
import json
import time
import uuid
from subprocess import Popen, PIPE

from unittest import skipIf

import boto3
from botocore.exceptions import ClientError

from samcli.commands.destroy import verify_stack_exists
from tests.integration.destroy.test_destroy_integ_base import DestroyIntegBase

LOG = logging.getLogger(__name__)

# Publish tests require credentials and Travis will only add credentials to the env if the PR is from the same repo.
# This is to restrict publish tests to run outside of Travis and when the branch is not master.
SKIP_DESTROY_TESTS = os.environ.get("TRAVIS", False) and os.environ.get("TRAVIS_BRANCH", "master") != "master"


@skipIf(SKIP_DESTROY_TESTS, "Skip publish tests in Travis only")
class TestDestroy(DestroyIntegBase):

    def test_basic_destroy(self):
        pass
        # stack_name = "test-destroy-" + str(uuid.uuid4())
        # self.build_package_deploy(stack_name)
        # time.sleep(5)
        # command_list = self.get_destroy_command_list(stack_name, wait=True)
        # LOG.info("Running Destroy Command: {}".format(command_list))
        # process = Popen(command_list, stdout=PIPE)
        # process.wait()
        # self.assertEqual(process.returncode, 0)
        #
        # client = boto3.client('cloudformation')
        # try:
        #     verify_stack_exists(client, stack_name)
        #     self.fail()  # Fail if the stack exists
        # except (ClientError, SystemExit) as e:
        #     pass
    #
    # def test_termination_protection_prompt(self):
    #     stack_name = "test-destroy-protected-" + str(uuid.uuid4())
    #     self.build_package_deploy(stack_name)
    #     self.enable_stack_termination_protection(stack_name)
    #     time.sleep(5)
    #     command_list = self.get_destroy_command_list(stack_name, wait=True)
    #     LOG.info("Running Destroy Command: {}".format(command_list))
    #     process = Popen(command_list, stdout=PIPE)
    #     process.wait()
    #     self.assertEqual(process.returncode, 1)
    #
    #     client = boto3.client('cloudformation')
    #     try:
    #         verify_stack_exists(client, stack_name)
    #     except (ClientError, SystemExit) as e:
    #         self.fail()
    #
    #
