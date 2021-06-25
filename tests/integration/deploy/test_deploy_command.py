import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest import skipIf

import boto3
import docker
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeploy(PackageIntegBase, DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
            # below 3 images are for test_deploy_nested_stacks()
            ("python", "3.9-slim"),
            ("python", "3.8-slim"),
            ("python", "3.7-slim"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
        # setup signing profile arn & name
        cls.signing_profile_name = os.environ.get("AWS_SIGNING_PROFILE_NAME")
        cls.signing_profile_version_arn = os.environ.get("AWS_SIGNING_PROFILE_VERSION_ARN")
        PackageIntegBase.setUpClass()
        DeployIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stacks = []
        time.sleep(CFN_SLEEP)
        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
        for stack in self.stacks:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                region = stack.get("region")
                cf_client = (
                    self.cf_client if not region else boto3.client("cloudformation", config=Config(region_name=region))
                )
                cf_client.delete_stack(StackName=stack_name)
        super().tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_package_and_deploy_no_s3_bucket_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file:
            # Package necessary artifacts.
            package_command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name, template=template_path, output_template_file=output_template_file.name
            )
            package_process = run_command(command_list=package_command_list)

            self.assertEqual(package_process.process.returncode, 0)

            stack_name = self._method_to_stack_name(self.id())
            self.stacks.append({"name": stack_name})

            # Deploy and only show changeset.
            deploy_command_list_no_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix="integ_deploy",
                s3_bucket=self.s3_bucket.name,
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                no_execute_changeset=True,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            deploy_process_no_execute = run_command(deploy_command_list_no_execute)
            self.assertEqual(deploy_process_no_execute.process.returncode, 0)

            # Deploy the given stack with the changeset.
            deploy_command_list_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix="integ_deploy",
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            deploy_process = run_command(deploy_command_list_execute)
            self.assertEqual(deploy_process.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function-image.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_all_args_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("Hello", "aws-serverless-function-image.yaml")])
    def test_no_package_and_deploy_with_s3_bucket_all_args_image_repositories(self, resource_id, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            image_repositories=f"{resource_id}={self.ecr_repo_name}",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_and_no_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_command_list.append("--no-confirm-changeset")

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_no_redeploy_on_same_built_artifacts(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        # Build project
        build_command_list = self.get_minimal_build_command_list(template_file=template_path)

        run_command(build_command_list)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})
        # Should result in a zero exit code.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # ReBuild project, absolutely nothing has changed, will result in same build artifacts.

        run_command(build_command_list)

        # Re-deploy, this should cause an empty changeset error and not re-deploy.
        # This will cause a non zero exit code.

        deploy_process_execute = run_command(deploy_command_list)
        # Does not cause a re-deploy
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_all_args_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=True,
        )

        deploy_process_execute = run_command_with_input(deploy_command_list, "Y".encode())
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_s3_bucket(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        # Error asking for s3 bucket
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        self.assertIn(
            bytes(
                f"S3 Bucket not specified, use --s3-bucket to specify a bucket name, or use --resolve-s3 \
to create a managed default bucket, or run sam deploy --guided",
                encoding="utf-8",
            ),
            deploy_process_execute.stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_stack_name(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 2)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_template_file(self, template_file):
        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        # Error template file not specified
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_s3_bucket_switch_region(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.bucket_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.bucket_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region="eu-west-2",
        )

        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should fail, asking for s3 bucket
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update stack {stack_name} : "
                f"deployment s3 bucket is in a different region, try sam deploy --guided",
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_twice_with_no_fail_on_empty_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        kwargs = {
            "template_file": template_path,
            "stack_name": stack_name,
            "capabilities": "CAPABILITY_IAM",
            "s3_prefix": "integ_deploy",
            "s3_bucket": self.bucket_name,
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "no_execute_changeset": False,
            "tags": "integ=true clarity=yes foo_bar=baz",
            "confirm_changeset": False,
        }
        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(**kwargs)
        print("######################################")
        print(deploy_command_list)
        print("######################################")
        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Deploy with `--no-fail-on-empty-changeset` after deploying the same template first
        deploy_command_list = self.get_deploy_command_list(fail_on_empty_changeset=False, **kwargs)

        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should not fail
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        stdout = deploy_process_execute.stdout.strip()
        self.assertIn(bytes(f"No changes to deploy. Stack {stack_name} is up to date", encoding="utf-8"), stdout)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_twice_with_fail_on_empty_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        kwargs = {
            "template_file": template_path,
            "stack_name": stack_name,
            "capabilities": "CAPABILITY_IAM",
            "s3_prefix": "integ_deploy",
            "s3_bucket": self.bucket_name,
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "no_execute_changeset": False,
            "tags": "integ=true clarity=yes foo_bar=baz",
            "confirm_changeset": False,
        }
        deploy_command_list = self.get_deploy_command_list(**kwargs)

        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Deploy with `--fail-on-empty-changeset` after deploying the same template first
        deploy_command_list = self.get_deploy_command_list(fail_on_empty_changeset=True, **kwargs)

        deploy_process_execute = run_command(deploy_command_list)
        # Deploy should not fail
        self.assertNotEqual(deploy_process_execute.process.returncode, 0)
        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(bytes(f"Error: No changes to deploy. Stack {stack_name} is up to date", encoding="utf-8"), stderr)

    @parameterized.expand(["aws-serverless-inline.yaml"])
    def test_deploy_inline_no_package(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, stack_name=stack_name, capabilities="CAPABILITY_IAM"
        )
        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-serverless-inline.yaml", "samconfig-read-boolean-tomlkit.toml")])
    def test_deploy_with_toml_config(self, template_file, config_file):
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, stack_name=stack_name, config_file=config_path, capabilities="CAPABILITY_IAM"
        )
        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function-image.yaml"])
    def test_deploy_guided_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, f"{stack_name}\n\n{self.ecr_repo_name}\n\n\ny\n\n\n\n\n\n".encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_parameter(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\nCAPABILITY_IAM CAPABILITY_NAMED_IAM\n\n\n\n".format(stack_name).encode(),
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_capabilities_default(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        # Set no for Allow SAM CLI IAM role creation, but allow default of ["CAPABILITY_IAM"] by just hitting the return key.
        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\n\nn\n\n\n\n\n\n".format(stack_name).encode()
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\nY\n\nY\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_no_s3_bucket_set_resolve_s3(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            resolve_s3=True,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-serverless-function.yaml", "samconfig-invalid-syntax.toml")])
    def test_deploy_with_invalid_config(self, template_file, config_file):
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        deploy_command_list = self.get_deploy_command_list(template_file=template_path, config_file=config_path)

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        self.assertIn("Error reading configuration: Unexpected character", str(deploy_process_execute.stderr))

    @parameterized.expand([("aws-serverless-function.yaml", "samconfig-tags-list.toml")])
    def test_deploy_with_valid_config_tags_list(self, template_file, config_file):
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            config_file=config_path,
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            capabilities="CAPABILITY_IAM",
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-serverless-function.yaml", "samconfig-tags-string.toml")])
    def test_deploy_with_valid_config_tags_string(self, template_file, config_file):
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            config_file=config_path,
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            capabilities="CAPABILITY_IAM",
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([(True, True, True), (False, True, False), (False, False, True), (True, False, True)])
    def test_deploy_with_code_signing_params(self, should_sign, should_enforce, will_succeed):
        """
        Signed function with UntrustedArtifactOnDeployment = Enforced config should succeed
        Signed function with UntrustedArtifactOnDeployment = Warn config should succeed
        Unsigned function with UntrustedArtifactOnDeployment = Enforce config should fail
        Unsigned function with UntrustedArtifactOnDeployment = Warn config should succeed
        """
        template_path = self.test_data_path.joinpath("aws-serverless-function-with-code-signing.yaml")
        stack_name = self._method_to_stack_name(self.id())
        signing_profile_version_arn = TestDeploy.signing_profile_version_arn
        signing_profile_name = TestDeploy.signing_profile_name

        if not signing_profile_name or not signing_profile_version_arn:
            self.fail(
                "Missing resources for Code Signer integration tests. Please provide "
                "AWS_SIGNING_PROFILE_NAME and AWS_SIGNING_PROFILE_VERSION_ARN environment variables"
            )

        self.stacks.append({"name": stack_name})

        signing_profiles_param = None
        if should_sign:
            signing_profiles_param = f"HelloWorldFunctionWithCsc={signing_profile_name}"

        enforce_param = "Warn"
        if should_enforce:
            enforce_param = "Enforce"

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            signing_profiles=signing_profiles_param,
            parameter_overrides=f"SigningProfileVersionArn={signing_profile_version_arn} "
            f"UntrustedArtifactOnDeployment={enforce_param}",
        )

        deploy_process_execute = run_command(deploy_command_list)

        if will_succeed:
            self.assertEqual(deploy_process_execute.process.returncode, 0)
        else:
            self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(
        [
            ("aws-serverless-application-with-application-id-map.yaml", None, False),
            ("aws-serverless-application-with-application-id-map.yaml", "us-east-2", True),
        ]
    )
    def test_deploy_sar_with_location_from_map(self, template_file, region, will_succeed):
        template_path = Path(__file__).resolve().parents[1].joinpath("testdata", "buildcmd", template_file)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name, "region": region})

        # The default region (us-east-1) has no entry in the map
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            region=region,  # the !FindInMap has an entry for use-east-2 region only
        )
        deploy_process_execute = run_command(deploy_command_list)

        if will_succeed:
            self.assertEqual(deploy_process_execute.process.returncode, 0)
        else:
            self.assertEqual(deploy_process_execute.process.returncode, 1)
            self.assertIn("Property \\'ApplicationId\\' cannot be resolved.", str(deploy_process_execute.stderr))

    @parameterized.expand(
        [
            ("aws-serverless-application-with-application-id-map.yaml", None, False),
            ("aws-serverless-application-with-application-id-map.yaml", "us-east-2", True),
        ]
    )
    def test_deploy_guided_sar_with_location_from_map(self, template_file, region, will_succeed):
        template_path = Path(__file__).resolve().parents[1].joinpath("testdata", "buildcmd", template_file)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name, "region": region})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, f"{stack_name}\n{region}\n\nN\nCAPABILITY_IAM CAPABILITY_AUTO_EXPAND\nN\n".encode()
        )

        if will_succeed:
            self.assertEqual(deploy_process_execute.process.returncode, 0)
        else:
            self.assertEqual(deploy_process_execute.process.returncode, 1)
            self.assertIn("Property \\'ApplicationId\\' cannot be resolved.", str(deploy_process_execute.stderr))

    @parameterized.expand(
        [os.path.join("deep-nested", "template.yaml"), os.path.join("deep-nested-image", "template.yaml")]
    )
    def test_deploy_nested_stacks(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            # Note(xinhol): --capabilities does not allow passing multiple, we need to fix it
            # here we use samconfig-deep-nested.toml as a workaround
            config_file=self.test_data_path.joinpath("samconfig-deep-nested.toml"),
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            image_repository=self.ecr_repo_name,
        )

        deploy_process_execute = run_command(deploy_command_list)
        process_stdout = deploy_process_execute.stdout.decode()
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # verify child stack ChildStackX's creation
        self.assertRegex(process_stdout, r"CREATE_COMPLETE.+ChildStackX")

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"
