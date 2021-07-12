from unittest import skipIf

from parameterized import parameterized

from tests.integration.pipeline.base import BootstrapIntegBase
from tests.testing_utils import (
    run_command_with_input,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    run_command,
    run_command_with_inputs,
)
import boto3
from botocore.exceptions import ClientError

# bootstrap tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_BOOTSTRAP_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_BOOTSTRAP_TESTS, "Skip bootstrap tests in CI/CD only")
class TestBootstrap(BootstrapIntegBase):
    @parameterized.expand([("create_image_repository",), (False,)])
    def test_interactive_with_no_resources_provided(self, create_image_repository: bool):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            env_name,
            "",  # pipeline user
            "",  # Pipeline execution role
            "",  # CloudFormation execution role
            "",  # Artifacts bucket
            "2" if create_image_repository else "1",  # Should we create ECR repo, 1 - No, 2 - Yes
            "y",  # proceed
        ]

        bootstrap_process_execute = run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("We have created the following resources", stdout)
        # make sure pipeline user's credential is printed
        self.assertIn("ACCESS_KEY_ID", stdout)
        self.assertIn("SECRET_ACCESS_KEY", stdout)

        common_resources = {
            "PipelineUser",
            "PipelineUserAccessKey",
            "CloudFormationExecutionRole",
            "PipelineExecutionRole",
            "ArtifactsBucket",
            "ArtifactsBucketPolicy",
            "PipelineExecutionRolePermissionPolicy",
        }
        if create_image_repository:
            self.assertSetEqual(
                {
                    *common_resources,
                    "ImageRepository",
                },
                self._extract_created_resource_logical_ids(stack_name),
            )
        else:
            self.assertSetEqual(common_resources, self._extract_created_resource_logical_ids(stack_name))

    @parameterized.expand([("create_image_repository",), (False,)])
    def test_non_interactive_with_no_resources_provided(self, create_image_repository: bool):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True, create_image_repository=create_image_repository, no_confirm_changeset=True
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 2)
        stderr = bootstrap_process_execute.stderr.decode()
        self.assertIn("Missing required parameter", stderr)

    def test_interactive_with_all_required_resources_provided(self):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            env_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "arn:aws:iam::123:role/role-name",  # Pipeline execution role
            "arn:aws:iam::123:role/role-name",  # CloudFormation execution role
            "arn:aws:s3:::bucket-name",  # Artifacts bucket
            "3",  # Should we create ECR repo, 3 - specify one
            "arn:aws:ecr:::repository/repo-name",  # ecr repo
            "y",  # proceed
        ]

        bootstrap_process_execute = run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("skipping creation", stdout)

    def test_no_interactive_with_all_required_resources_provided(self):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True,
            env_name=env_name,
            pipeline_user="arn:aws:iam::123:user/user-name",  # pipeline user
            pipeline_execution_role="arn:aws:iam::123:role/role-name",  # Pipeline execution role
            cloudformation_execution_role="arn:aws:iam::123:role/role-name",  # CloudFormation execution role
            artifacts_bucket="arn:aws:s3:::bucket-name",  # Artifacts bucket
            image_repository="arn:aws:ecr:::repository/repo-name",  # ecr repo
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("skipping creation", stdout)

    @parameterized.expand([("confirm_changeset",), (False,)])
    def test_no_interactive_with_some_required_resources_provided(self, confirm_changeset):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True,
            env_name=env_name,
            pipeline_user="arn:aws:iam::123:user/user-name",  # pipeline user
            pipeline_execution_role="arn:aws:iam::123:role/role-name",  # Pipeline execution role
            # CloudFormation execution role missing
            artifacts_bucket="arn:aws:s3:::bucket-name",  # Artifacts bucket
            image_repository="arn:aws:ecr:::repository/repo-name",  # ecr repo
            no_confirm_changeset=not confirm_changeset,
        )

        inputs = [
            "y",  # proceed
        ]

        bootstrap_process_execute = run_command_with_inputs(bootstrap_command_list, inputs if confirm_changeset else [])

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("Successfully created!", stdout)
        self.assertSetEqual({"CloudFormationExecutionRole"}, self._extract_created_resource_logical_ids(stack_name))

    def test_interactive_cancelled_by_user(self):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            env_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "",  # Pipeline execution role
            "",  # CloudFormation execution role
            "",  # Artifacts bucket
            "1",  # Should we create ECR repo, 1 - No
            "N",  # cancel
        ]

        bootstrap_process_execute = run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertTrue(stdout.strip().endswith("Should we proceed with the creation? [y/N]:"))
        self.assertFalse(self._stack_exists(stack_name))

    def test_interactive_with_some_required_resources_provided(self):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            env_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "arn:aws:iam::123:role/role-name",  # Pipeline execution role
            "",  # CloudFormation execution role
            "arn:aws:s3:::bucket-name",  # Artifacts bucket
            "3",  # Should we create ECR repo, 3 - specify one
            "arn:aws:ecr:::repository/repo-name",  # ecr repo
            "y",  # proceed
        ]

        bootstrap_process_execute = run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("Successfully created!", stdout)
        # make sure the not provided resource is the only resource created.
        self.assertSetEqual({"CloudFormationExecutionRole"}, self._extract_created_resource_logical_ids(stack_name))

    def test_interactive_pipeline_user_only_created_once(self):
        """
        Create 3 environments, only the first environment resource stack creates
        a pipeline user, and the remaining two share the same pipeline user.
        """
        env_names = []
        for suffix in ["1", "2", "3"]:
            env_name, stack_name = self._get_env_and_stack_name(suffix)
            env_names.append(env_name)
            self.stack_names.append(stack_name)

        bootstrap_command_list = self.get_bootstrap_command_list()

        for i, env_name in enumerate(env_names):
            inputs = [
                env_name,
                *([""] if i == 0 else []),  # pipeline user
                "arn:aws:iam::123:role/role-name",  # Pipeline execution role
                "arn:aws:iam::123:role/role-name",  # CloudFormation execution role
                "arn:aws:s3:::bucket-name",  # Artifacts bucket
                "1",  # Should we create ECR repo, 1 - No, 2 - Yes
                "y",  # proceed
            ]

            bootstrap_process_execute = run_command_with_input(
                bootstrap_command_list, ("\n".join(inputs) + "\n").encode()
            )

            self.assertEqual(bootstrap_process_execute.process.returncode, 0)
            stdout = bootstrap_process_execute.stdout.decode()

            # Only first environment creates pipeline user
            if i == 0:
                self.assertIn("We have created the following resources", stdout)
                self.assertSetEqual(
                    {"PipelineUser", "PipelineUserAccessKey"},
                    self._extract_created_resource_logical_ids(self.stack_names[i]),
                )
            else:
                self.assertIn("skipping creation", stdout)

    @parameterized.expand([("ArtifactsBucket",), ("ArtifactsLoggingBucket",)])
    def test_bootstrapped_buckets_accept_ssl_requests_only(self, bucket_logical_id):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            env_name=env_name, no_interactive=True, no_confirm_changeset=True
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)

        stack_resources = self.cf_client.describe_stack_resources(StackName=stack_name)
        bucket = next(
            resource
            for resource in stack_resources["StackResources"]
            if resource["LogicalResourceId"] == bucket_logical_id
        )
        bucket_name = bucket["PhysicalResourceId"]
        bucket_key = "any/testing/key.txt"
        testing_data = b"any testing binary data"

        s3_ssl_client = boto3.client("s3")
        s3_non_ssl_client = boto3.client("s3", use_ssl=False)

        # Assert SSL requests are accepted
        s3_ssl_client.put_object(Body=testing_data, Bucket=bucket_name, Key=bucket_key)
        res = s3_ssl_client.get_object(Bucket=bucket_name, Key=bucket_key)
        retrieved_data = res["Body"].read()
        self.assertEqual(retrieved_data, testing_data)

        # Assert non SSl requests are denied
        with self.assertRaises(ClientError) as error:
            s3_non_ssl_client.get_object(Bucket=bucket_name, Key=bucket_key)
        self.assertEqual(
            str(error.exception), "An error occurred (AccessDenied) when calling the GetObject operation: Access Denied"
        )

    def test_bootstrapped_artifacts_bucket_has_server_access_log_enabled(self):
        env_name, stack_name = self._get_env_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            env_name=env_name, no_interactive=True, no_confirm_changeset=True
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)

        stack_resources = self.cf_client.describe_stack_resources(StackName=stack_name)
        artifacts_bucket = next(
            resource
            for resource in stack_resources["StackResources"]
            if resource["LogicalResourceId"] == "ArtifactsBucket"
        )
        artifacts_bucket_name = artifacts_bucket["PhysicalResourceId"]
        artifacts_logging_bucket = next(
            resource
            for resource in stack_resources["StackResources"]
            if resource["LogicalResourceId"] == "ArtifactsLoggingBucket"
        )
        artifacts_logging_bucket_name = artifacts_logging_bucket["PhysicalResourceId"]

        s3_client = boto3.client("s3")
        res = s3_client.get_bucket_logging(Bucket=artifacts_bucket_name)
        self.assertEqual(artifacts_logging_bucket_name, res["LoggingEnabled"]["TargetBucket"])
