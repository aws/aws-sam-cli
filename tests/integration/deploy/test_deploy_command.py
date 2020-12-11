import os
import shutil
import tempfile
import uuid
import time
from unittest import skipIf

import boto3
from parameterized import parameterized

from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import CommandResult, run_command, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeploy(PackageIntegBase, DeployIntegBase):
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
        self.stack_names.append(stack_name)

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
    def test_no_package_and_deploy_with_s3_bucket_all_args_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

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

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_and_no_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

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
        self.stack_names.append(stack_name)
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
        self.stack_names.append(stack_name)

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
                f"S3 Bucket not specified, use --s3-bucket to specify a bucket name or run sam deploy --guided",
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
        self.stack_names.append(stack_name)

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
        self.stack_names.append(stack_name)

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
        self.stack_names.append(stack_name)

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
        self.stack_names.append(stack_name)

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, stack_name=stack_name, capabilities="CAPABILITY_IAM"
        )
        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function-image.yaml"])
    def test_deploy_guided_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, f"{stack_name}\n\n{self.ecr_repo_name}\n\n\ny\n\n\n\n\n\n".encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_parameter(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\nCAPABILITY_IAM CAPABILITY_NAMED_IAM\n\n\n\n".format(stack_name).encode(),
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_capabilities_default(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        # Set no for Allow SAM CLI IAM role creation, but allow default of ["CAPABILITY_IAM"] by just hitting the return key.
        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\n\nn\n\n\n\n\n\n".format(stack_name).encode()
        )
        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\nSuppliedParameter\nY\n\nY\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_no_s3_bucket_set_resolve_s3(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stack_names.append(stack_name)

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

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"
