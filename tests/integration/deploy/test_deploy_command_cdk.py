import json
import os
import shutil
import tempfile
import uuid
import time
import copy
import logging
from unittest import skipIf

import boto3
import docker
from parameterized import parameterized

from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import CdkPackageIntegPythonBase, PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import CommandResult, run_command, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")
LOG = logging.getLogger(__name__)


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeployCdkPython(CdkPackageIntegPythonBase, DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
        # setup signing profile arn & name
        cls.signing_profile_name = os.environ.get("AWS_SIGNING_PROFILE_NAME")
        cls.signing_profile_version_arn = os.environ.get("AWS_SIGNING_PROFILE_VERSION_ARN")

        CdkPackageIntegPythonBase.setUpClass()
        DeployIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stack_names = []
        time.sleep(CFN_SLEEP)
        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
        for stack_name in self.stack_names:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            if stack_name != SAM_CLI_STACK_NAME:
                self.cf_client.delete_stack(StackName=stack_name)
        super().tearDown()

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"

    def _replace_cloud_assembly_stack_name(self, manifest_path, original_stack_name, new_stack_name):
        with open(manifest_path, "r") as fp:
            manifest_dict = json.loads(fp.read())
        artifacts_dict = manifest_dict["artifacts"]
        if original_stack_name in artifacts_dict:
            artifacts_dict[new_stack_name] = copy.deepcopy(artifacts_dict[original_stack_name])
            del artifacts_dict[original_stack_name]
        with open(manifest_path, "w") as fp:
            fp.write(json.dumps(manifest_dict, indent=4))

    @parameterized.expand(["aws-lambda-function"])
    def test_package_and_deploy_no_s3_bucket_all_args(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file:
            # Package necessary artifacts.
            package_command_list = self.get_command_list(
                s3_bucket=self.bucket_name,
                output_template_file=output_template_file.name,
                cdk_app=f"{self.venv_python} app.py",
            )
            package_process = run_command(command_list=package_command_list, cwd=self.working_dir)
            self.assertEqual(package_process.process.returncode, 0)

            stack_name = self._method_to_stack_name(self.id())
            self.stack_names.append(stack_name)

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

            # as we are deploying with an pacakaged output template, we don't need to run the command in self.working_dir
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

            # as we are deploying with an pacakaged output template, we don't need to run the command in self.working_dir
            deploy_process = run_command(deploy_command_list_execute)
            self.assertEqual(deploy_process.process.returncode, 0)

    @parameterized.expand(["aws-lambda-function"])
    def test_no_package_and_deploy_with_s3_bucket_all_args(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
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
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-lambda-function"])
    def test_no_package_and_deploy_with_s3_bucket_and_no_confirm_changeset(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
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
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_command_list.append("--no-confirm-changeset")

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_no_redeploy_on_same_built_artifacts(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Build project
        build_command_list = self.get_minimal_build_command_list(
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )
        run_command(build_command_list, cwd=self.working_dir)

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

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # ReBuild project, absolutely nothing has changed, will result in same build artifacts.
        run_command(build_command_list, cwd=self.working_dir)

        # Re-deploy, this should cause an empty changeset error and not re-deploy.
        # This will cause a non zero exit code.
        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-lambda-function"])
    def test_no_package_and_deploy_with_s3_bucket_all_args_confirm_changeset(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
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
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command_with_input(deploy_command_list, "Y".encode(), cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_without_s3_bucket(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        # Error asking for s3 bucket
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        self.assertIn(
            bytes(
                "Cannot skip both --resolve-s3 and --s3-bucket parameters. Please provide one of these arguments.",
                encoding="utf-8",
            ),
            deploy_process_execute.stderr,
        )

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_without_stack_name(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 2)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_with_non_exist_stack_name(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
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
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            cdk_app=f"{self.venv_python} app.py",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 2)
        self.assertIn(
            bytes(
                f"Stack with stack name '{stack_name}' not found.",
                encoding="utf-8",
            ),
            deploy_process_execute.stderr,
        )

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_without_capabilities(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_with_s3_bucket_switch_region(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
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

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_twice_with_no_fail_on_empty_changeset(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        deploy_command_list = self.get_deploy_command_list(
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
            fail_on_empty_changeset=False,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        stdout = deploy_process_execute.stdout.strip()
        self.assertIn(bytes(f"No changes to deploy. Stack {stack_name} is up to date", encoding="utf-8"), stdout)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_twice_with_fail_on_empty_changeset(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        deploy_command_list = self.get_deploy_command_list(
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
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        deploy_command_list = self.get_deploy_command_list(
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
            fail_on_empty_changeset=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(bytes(f"Error: No changes to deploy. Stack {stack_name} is up to date", encoding="utf-8"), stderr)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_zip(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )

        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_set_parameter(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\n\n\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_set_capabilities(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\nCAPABILITY_IAM CAPABILITY_NAMED_IAM\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_capabilities_default(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        # Set no for Allow SAM CLI IAM role creation, but allow default of ["CAPABILITY_IAM"] by just hitting the return key.
        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\n\n\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_set_confirm_changeset(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\nY\n\nY\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_guided_with_non_exist_stack_name(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        # self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            guided=True,
            cdk_app=f"{self.venv_python} app.py",
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\n\n\n\n\n\n".format(stack_name).encode(),
            cwd=self.working_dir,
        )

        self.assertEqual(deploy_process_execute.process.returncode, 1)
        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(f"There is no stack with name '{stack_name}'.", encoding="utf-8"),
            stderr,
        )
        # self.stack_names.append(SAM_CLI_STACK_NAME)

    @parameterized.expand(["aws-lambda-function"])
    def test_deploy_with_no_s3_bucket_set_resolve_s3(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            resolve_s3=True,
            cdk_app=f"{self.venv_python} app.py",
            cdk_context=f"stack_name={stack_name}",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-lambda-function", "samconfig-invalid-syntax.toml")])
    def test_deploy_with_invalid_config(self, cdk_app_loc, config_file):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        config_path = self.test_data_path.joinpath(config_file)

        deploy_command_list = self.get_deploy_command_list(
            config_file=config_path,
            cdk_app=f"{self.venv_python} app.py",
        )

        deploy_process_execute = run_command(deploy_command_list, cwd=self.working_dir)
        self.assertEqual(deploy_process_execute.process.returncode, 1)
        self.assertIn("Error reading configuration: Unexpected character", str(deploy_process_execute.stderr))
