import os
import re
import json
import uuid
from subprocess import Popen, PIPE

from unittest import skipIf

import boto3

from samcli.commands.destroy import verify_stack_exists
from tests.integration.destroy.test_destroy_integ_base import DestroyIntegBase

# Publish tests require credentials and Travis will only add credentials to the env if the PR is from the same repo.
# This is to restrict publish tests to run outside of Travis and when the branch is not master.
SKIP_DESTROY_TESTS = os.environ.get("TRAVIS", False) and os.environ.get("TRAVIS_BRANCH", "master") != "master"


@skipIf(SKIP_DESTROY_TESTS, "Skip publish tests in Travis only")
class TestDestroy(DestroyIntegBase):

    def test_basic_destroy(self):
        build_overrides = {"Runtime": "python3.6",
                           "CodeUri": ".",
                           "Handler": "main.handler"}
        stack_name = str(uuid.uuid4())
        self.build_package_deploy(build_overrides, stack_name)

        self.get_destroy_command_list(wait=True)
        command_list = self.get_destroy_command_list(stack_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        self.assertEquals(process.returncode, 0)

        client = boto3.client('cloudformation')
        verify_stack_exists(client, stack_name)

    def test_termination_protection_prompt(self):
        build_overrides = {"Runtime": "python3.6",
                           "CodeUri": ".",
                           "Handler": "main.handler"}
        stack_name = str(uuid.uuid4())
        self.build_package_deploy(build_overrides, stack_name)
        self.enable_stack_termination_protection(stack_name)

        self.get_destroy_command_list(wait=True)
        command_list = self.get_destroy_command_list(stack_name)

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        self.assertEquals(process.returncode, 1)

        client = boto3.client('cloudformation')
        verify_stack_exists(client, stack_name)
