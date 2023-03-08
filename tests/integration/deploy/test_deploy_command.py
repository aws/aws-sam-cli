import os
import tempfile
import uuid
from pathlib import Path
from unittest import skipIf

import botocore
import docker
from botocore.exceptions import ClientError
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeploy(DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("public.ecr.aws/sam/emulation-python3.8", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.8", tag="latest")
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.8-2", tag="latest")
            cls.docker_client.api.tag(f"{repo}:{tag}", "colorsrandomfunctionf61b9209", tag="latest")

        # setup signing profile arn & name
        cls.signing_profile_name = os.environ.get("AWS_SIGNING_PROFILE_NAME")
        cls.signing_profile_version_arn = os.environ.get("AWS_SIGNING_PROFILE_VERSION_ARN")
        super().setUpClass()

    def setUp(self):
        self.sns_arn = os.environ.get("AWS_SNS")
        super().setUp()

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
            "cdk_v1_synthesized_template_zip_functions.json",
            "cdk_v1_synthesized_template_Level1_nested_zip_functions.json",
        ]
    )
    def test_package_and_deploy_no_s3_bucket_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file:
            # Package necessary artifacts.
            package_command_list = self.get_command_list(
                template=template_path,
                s3_bucket=self.s3_bucket.name,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template_file.name,
            )
            package_process = self.run_command(command_list=package_command_list)

            self.assertEqual(package_process.process.returncode, 0)

            stack_name = self._method_to_stack_name(self.id())
            self.stacks.append({"name": stack_name})

            # Deploy and only show changeset.
            deploy_command_list_no_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix=self.s3_prefix,
                s3_bucket=self.s3_bucket.name,
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                no_execute_changeset=True,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            deploy_process_no_execute = self.run_command(deploy_command_list_no_execute)
            self.assertEqual(deploy_process_no_execute.process.returncode, 0)

            # Deploy the given stack with the changeset.
            deploy_command_list_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix=self.s3_prefix,
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            deploy_process = self.run_command(deploy_command_list_execute)
            self.assertEqual(deploy_process.process.returncode, 0)

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
            "cdk_v1_synthesized_template_zip_functions.json",
            "cdk_v1_synthesized_template_Level1_nested_zip_functions.json",
        ]
    )
    def test_no_package_and_deploy_with_s3_bucket_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
            "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
        ]
    )
    def test_no_package_and_deploy_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            ("Hello", "aws-serverless-function-image.yaml"),
            ("MyLambdaFunction", "aws-lambda-function-image.yaml"),
            ("ColorsRandomFunctionF61B9209", "cdk_v1_synthesized_template_image_functions.json"),
            ("ColorsRandomFunction", "cdk_v1_synthesized_template_image_functions.json"),
            ("ColorsRandomFunction", "cdk_v1_synthesized_template_Level1_nested_image_functions.json"),
            ("ColorsRandomFunctionF61B9209", "cdk_v1_synthesized_template_Level1_nested_image_functions.json"),
            (
                "Level1Stack/Level2Stack/ColorsRandomFunction",
                "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
            ),
        ]
    )
    def test_no_package_and_deploy_with_s3_bucket_all_args_image_repositories(self, resource_id, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
            "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
        ]
    )
    def test_no_package_and_deploy_resolve_image_repos(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            resolve_image_repos=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        companion_stack_name = self._stack_name_to_companion_stack(stack_name)
        self._assert_companion_stack(self.cfn_client, companion_stack_name)
        self._assert_companion_stack_content(self.ecr_client, companion_stack_name)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_no_package_and_deploy_with_s3_bucket_and_no_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_no_redeploy_on_same_built_artifacts(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        # Build project
        build_command_list = self.get_minimal_build_command_list(template_file=template_path)

        self.run_command(build_command_list)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})
        # Should result in a zero exit code.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # ReBuild project, absolutely nothing has changed, will result in same build artifacts.

        self.run_command(build_command_list)

        # Re-deploy, this should cause an empty changeset error and not re-deploy.
        # This will cause a non zero exit code.

        deploy_process_execute = self.run_command(deploy_command_list)
        # Does not cause a re-deploy
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_no_package_and_deploy_with_s3_bucket_all_args_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=True,
        )

        deploy_process_execute = self.run_command_with_input(deploy_command_list, "Y".encode())
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_without_s3_bucket(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
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

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_without_stack_name(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 2)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_without_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    def test_deploy_without_template_file(self):
        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        # Error template file not specified
        self.assertEqual(deploy_process_execute.process.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_with_s3_bucket_switch_region(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.bucket_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
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

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_twice_with_no_fail_on_empty_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        kwargs = {
            "template_file": template_path,
            "stack_name": stack_name,
            "capabilities": "CAPABILITY_IAM",
            "s3_prefix": self.s3_prefix,
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
        deploy_process_execute = self.run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Deploy with `--no-fail-on-empty-changeset` after deploying the same template first
        deploy_command_list = self.get_deploy_command_list(fail_on_empty_changeset=False, **kwargs)

        deploy_process_execute = self.run_command(deploy_command_list)
        # Deploy should not fail
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        stdout = deploy_process_execute.stdout.strip()
        self.assertIn(bytes(f"No changes to deploy. Stack {stack_name} is up to date", encoding="utf-8"), stdout)

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_twice_with_fail_on_empty_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        kwargs = {
            "template_file": template_path,
            "stack_name": stack_name,
            "capabilities": "CAPABILITY_IAM",
            "s3_prefix": self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Deploy with `--fail-on-empty-changeset` after deploying the same template first
        deploy_command_list = self.get_deploy_command_list(fail_on_empty_changeset=True, **kwargs)

        deploy_process_execute = self.run_command(deploy_command_list)
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
            template_file=template_path, stack_name=stack_name, s3_prefix=self.s3_prefix, capabilities="CAPABILITY_IAM"
        )
        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-serverless-inline.yaml", "samconfig-read-boolean-tomlkit.toml")])
    def test_deploy_with_toml_config(self, template_file, config_file):
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            s3_prefix=self.s3_prefix,
            config_file=config_path,
            capabilities="CAPABILITY_IAM",
        )
        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function-image.yaml", "aws-lambda-function-image.yaml"])
    def test_deploy_guided_image_auto(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list, f"{stack_name}\n\n\n\n\ny\n\n\ny\n\n\n\n".encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})

        companion_stack_name = self._stack_name_to_companion_stack(stack_name)
        self._assert_companion_stack(self.cfn_client, companion_stack_name)
        self._assert_companion_stack_content(self.ecr_client, companion_stack_name)

        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand([("aws-serverless-function-image.yaml", True), ("aws-lambda-function-image.yaml", False)])
    def test_deploy_guided_image_specify(self, template_file, does_ask_for_authorization):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        autorization_question_answer = "\n" if does_ask_for_authorization else ""

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            f"{stack_name}\n\n\n\n\ny\n\n\n{autorization_question_answer}n\n{self.ecr_repo_name}\n\n\n\n".encode(),
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # Verify companion stack does not exist
        try:
            self.cfn_client.describe_stacks(StackName=self._stack_name_to_companion_stack(stack_name))
        except ClientError:
            pass
        else:
            self.fail("Companion stack was created. This should not happen with specifying image repos.")

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

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\n\n\n\n\n\n\n".format(stack_name).encode(),
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

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\nCAPABILITY_IAM CAPABILITY_NAMED_IAM\n\n\n\n\n".format(stack_name).encode(),
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
        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\n\nn\n\n\n\n\n\n\n".format(stack_name).encode(),
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

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            "{}\n\nSuppliedParameter\nY\n\n\nY\n\n\n\n".format(stack_name).encode(),
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
            s3_prefix=self.s3_prefix,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand([("aws-serverless-function.yaml", "samconfig-invalid-syntax.toml")])
    def test_deploy_with_invalid_config(self, template_file, config_file):
        template_path = self.test_data_path.joinpath(template_file)
        config_path = self.test_data_path.joinpath(config_file)

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, s3_prefix=self.s3_prefix, config_file=config_path
        )

        deploy_process_execute = self.run_command(deploy_command_list)
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
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            capabilities="CAPABILITY_IAM",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
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
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            capabilities="CAPABILITY_IAM",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
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
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            signing_profiles=signing_profiles_param,
            parameter_overrides=f"SigningProfileVersionArn={signing_profile_version_arn} "
            f"UntrustedArtifactOnDeployment={enforce_param}",
        )

        deploy_process_execute = self.run_command(deploy_command_list)

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
            s3_prefix=self.s3_prefix,
            stack_name=stack_name,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            region=region,  # the !FindInMap has an entry for use-east-2 region only
        )
        deploy_process_execute = self.run_command(deploy_command_list)

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

        deploy_process_execute = self.run_command_with_input(
            deploy_command_list,
            f"{stack_name}\n{region}\n\nN\nCAPABILITY_IAM CAPABILITY_AUTO_EXPAND\nn\nN\n".encode(),
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
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            image_repository=self.ecr_repo_name,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        process_stdout = deploy_process_execute.stdout.decode()
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # verify child stack ChildStackX's creation
        self.assertRegex(process_stdout, r"CREATE_COMPLETE.+ChildStackX")

    @parameterized.expand([os.path.join("stackset", "template.yaml")])
    def test_deploy_stackset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            # Note(xinhol): --capabilities does not allow passing multiple, we need to fix it
            # here we use samconfig-stackset.toml as a workaround
            config_file=self.test_data_path.joinpath("samconfig-stackset.toml"),
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            image_repository=self.ecr_repo_name,
        )

        prevdir = os.getcwd()
        os.chdir(os.path.expanduser(os.path.dirname(template_path)))
        deploy_process_execute = self.run_command(deploy_command_list)
        process_stdout = deploy_process_execute.stdout.decode()
        os.chdir(prevdir)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # verify child stack ChildStackX's creation
        self.assertRegex(process_stdout, r"CREATE_COMPLETE.+StackSetA")

    @parameterized.expand(["aws-dynamodb-error.yaml"])
    def test_deploy_create_failed_rollback(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackCreateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "ROLLBACK_COMPLETE" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-dynamodb-error.yaml"])
    def test_deploy_create_failed_disable_rollback(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            disable_rollback=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackCreateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "CREATE_FAILED" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

        # Fix template and deploy again
        template_path = self.test_data_path.joinpath("aws-dynamodb-error-fixed.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            disable_rollback=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_update_failed_rollback(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # First deploy a simple template that should work
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Now update stack with failing template
        template_path = self.test_data_path.joinpath("aws-dynamodb-error.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackUpdateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "UPDATE_ROLLBACK_COMPLETE" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_update_failed_disable_rollback(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # First deploy a simple template that should work
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Now update stack with failing template
        template_path = self.test_data_path.joinpath("aws-dynamodb-error.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            disable_rollback=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackUpdateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "UPDATE_FAILED" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

        # Fix template and deploy again
        template_path = self.test_data_path.joinpath("aws-dynamodb-error-fixed.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            disable_rollback=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-serverless-function-cdk.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_deploy_logs_warning_with_cdk_project(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
        )

        warning_message = bytes(
            f"Warning: CDK apps are not officially supported with this command.{os.linesep}"
            "We recommend you use this alternative command: cdk deploy",
            encoding="utf-8",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertIn(warning_message, deploy_process_execute.stdout)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

    @parameterized.expand(["aws-dynamodb-error.yaml"])
    def test_deploy_on_failure_do_nothing_new_invalid_stack(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            on_failure="DO_NOTHING",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackCreateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "CREATE_FAILED" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_on_failure_do_nothing_existing_stack(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # First deploy a simple template that should work
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Failing template
        template_path = self.test_data_path.joinpath("aws-dynamodb-error.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            on_failure="DO_NOTHING",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 1)

        stderr = deploy_process_execute.stderr.strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update the stack: {stack_name}, Waiter StackUpdateComplete failed: "
                f'Waiter encountered a terminal failure state: For expression "Stacks[].StackStatus" '
                f'we matched expected path: "UPDATE_FAILED" at least once',
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-dynamodb-error.yaml"])
    def test_deploy_on_failure_delete_new_stack(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            on_failure="DELETE",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Check if the stack is deleted from CloudFormation
        stack_exists = True
        try:
            self.cfn_client.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError:
            stack_exists = False

        self.assertFalse(stack_exists)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_on_failure_delete_existing_stack(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # First deploy a simple template that should work
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Failing template
        template_path = self.test_data_path.joinpath("aws-dynamodb-error.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            on_failure="DELETE",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Check if the stack rolled back successfully
        result = self.cfn_client.describe_stacks(StackName=stack_name)
        self.assertEqual(str(result["Stacks"][0]["StackStatus"]), "UPDATE_ROLLBACK_COMPLETE")

    @parameterized.expand(["aws-dynamodb-error.yaml"])
    def test_deploy_on_failure_delete_existing_stack_fails(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Deploy bad stack with no rollback
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            disable_rollback=True,
        )

        deploy_process_execute = self.run_command(deploy_command_list)

        # Failing template
        template_path = self.test_data_path.joinpath(template_file)
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            image_repository=self.ecr_repo_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="ShardCountParameter=1",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            on_failure="DELETE",
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Check if the stack is deleted from CloudFormation
        stack_exists = True
        try:
            self.cfn_client.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError:
            stack_exists = False

        self.assertFalse(stack_exists)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_update_stack_correct_stack_outputs(self, template):
        template_path = self.test_data_path.joinpath(template)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Deploy template that creates single resource
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Deploy template that modifies existing resource, this should only UPDATE
        template_path = self.test_data_path.joinpath("aws-serverless-function-cdk.yaml")
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=self.s3_prefix,
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

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)

        # Check we don't have any instances of CREATE_COMPLETE since we are only updating
        process_stdout = deploy_process_execute.stdout.decode()
        self.assertNotRegex(process_stdout, r"CREATE_COMPLETE.+HelloWorldFunction")
        self.assertRegex(process_stdout, r"UPDATE_COMPLETE.+HelloWorldFunction")

    def test_deploy_with_language_extensions(self):
        template = Path(__file__).resolve().parents[1].joinpath("testdata", "buildcmd", "language-extensions.yaml")
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template, stack_name=stack_name, s3_prefix=self.s3_prefix, capabilities="CAPABILITY_IAM"
        )
        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
