import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest import skipIf
import logging
import boto3
import docker
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Delete tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DELETE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")
LOG = logging.getLogger(__name__)


@skipIf(SKIP_DELETE_TESTS, "Skip delete tests in CI/CD only")
class TestDelete(PackageIntegBase, DeployIntegBase, DeleteIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
            # below 3 images are for test_deploy_nested_stacks()
            # ("python", "3.9-slim"),
            # ("python", "3.8-slim"),
            # ("python", "3.7-slim"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)

        PackageIntegBase.setUpClass()
        DeployIntegBase.setUpClass()
        DeleteIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.stacks = []
        time.sleep(CFN_SLEEP)
        super().setUp()

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            # "aws-glue-job.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_delete_with_s3_bucket_prefix_present(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        LOG.info(template_path)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        config_file_name = stack_name + ".toml"
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, guided=True, config_file=config_file_name
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, config_file=self.test_data_path.joinpath(config_file_name), force=True
        )

        LOG.info(delete_command_list)
        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 0)

        # Remove the local config file created
        config_file_path = self.test_data_path.joinpath(config_file_name)
        if os.path.isfile(config_file_path):
            os.remove(config_file_path)

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"
