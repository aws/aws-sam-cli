from unittest import skipIf

from parameterized import parameterized

from tests.integration.pipeline.base import BootstrapIntegBase
from tests.testing_utils import (
    run_command_with_input,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    run_command,
)

# bootstrap tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_BOOTSTRAP_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_BOOTSTRAP_TESTS, "Skip bootstrap tests in CI/CD only")
class TestBootstrap(BootstrapIntegBase):
    @parameterized.expand([("create_ecr_repo",), (False,)])
    def test_interactive_with_no_resources_provided(self, create_ecr_repo: bool):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            stage_name,
            "",  # pipeline user
            "",  # Pipeline execution role
            "",  # CloudFormation execution role
            "",  # Artifacts bucket
            "2" if create_ecr_repo else "1",  # Should we create ECR repo, 1 - No, 2 - Yes
            "",  # Pipeline IP address range
            "y",  # proceed
        ]

        bootstrap_process_execute = self.run_command_with_inputs(bootstrap_command_list, inputs)

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
        if create_ecr_repo:
            self.assertIn("arn:aws:ecr:", stdout)
            self.assertSetEqual(
                {
                    *common_resources,
                    "ECRRepo",
                },
                self._extract_created_resource_logical_ids(stack_name),
            )
        else:
            self.assertNotIn("arn:aws:ecr:", stdout)
            self.assertSetEqual(common_resources, self._extract_created_resource_logical_ids(stack_name))

    @parameterized.expand([("create_ecr_repo",), (False,)])
    def test_non_interactive_with_no_resources_provided(self, create_ecr_repo: bool):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True, create_ecr_repo=create_ecr_repo, no_confirm_changeset=True
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 2)
        stderr = bootstrap_process_execute.stderr.decode()
        self.assertIn("Missing required parameter", stderr)

    def test_interactive_with_all_required_resources_provided(self):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            stage_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "arn:aws:iam::123:role/role-name",  # Pipeline execution role
            "arn:aws:iam::123:role/role-name",  # CloudFormation execution role
            "arn:aws:s3:::bucket-name",  # Artifacts bucket
            "3",  # Should we create ECR repo, 3 - specify one
            "arn:aws:ecr:::repository/repo-name",  # ecr repo
            "1.2.3.4/24",  # Pipeline IP address range
            "y",  # proceed
        ]

        bootstrap_process_execute = self.run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("skipping creation", stdout)

    def test_no_interactive_with_all_required_resources_provided(self, confirm_changeset):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True,
            stage_name=stage_name,
            pipeline_user="arn:aws:iam::123:user/user-name",  # pipeline user
            pipeline_execution_role="arn:aws:iam::123:role/role-name",  # Pipeline execution role
            cloudformation_execution_role="arn:aws:iam::123:role/role-name",  # CloudFormation execution role
            artifacts_bucket="arn:aws:s3:::bucket-name",  # Artifacts bucket
            ecr_repo="arn:aws:ecr:::repository/repo-name",  # ecr repo
            pipeline_ip_range="1.2.3.4/24",  # Pipeline IP address range
        )

        bootstrap_process_execute = run_command(bootstrap_command_list)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("skipping creation", stdout)

    @parameterized.expand([("confirm_changeset",), (False,)])
    def test_no_interactive_with_some_required_resources_provided(self, confirm_changeset):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list(
            no_interactive=True,
            stage_name=stage_name,
            pipeline_user="arn:aws:iam::123:user/user-name",  # pipeline user
            pipeline_execution_role="arn:aws:iam::123:role/role-name",  # Pipeline execution role
            # CloudFormation execution role missing
            artifacts_bucket="arn:aws:s3:::bucket-name",  # Artifacts bucket
            ecr_repo="arn:aws:ecr:::repository/repo-name",  # ecr repo
            pipeline_ip_range="1.2.3.4/24",  # Pipeline IP address range
            no_confirm_changeset=not confirm_changeset,
        )

        inputs = [
            "y",  # proceed
        ]

        bootstrap_process_execute = self.run_command_with_inputs(
            bootstrap_command_list, inputs if confirm_changeset else []
        )

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("Successfully created!", stdout)
        self.assertSetEqual({"CloudFormationExecutionRole"}, self._extract_created_resource_logical_ids(stack_name))

    def test_interactive_cancelled_by_user(self):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            stage_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "",  # Pipeline execution role
            "",  # CloudFormation execution role
            "",  # Artifacts bucket
            "1",  # Should we create ECR repo, 1 - No
            "",  # Pipeline IP address range
            "N",  # cancel
        ]

        bootstrap_process_execute = self.run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertTrue(stdout.strip().endswith("Should we proceed with the creation? [y/N]:"))

    def test_interactive_with_some_required_resources_provided(self):
        stage_name, stack_name = self._get_stage_and_stack_name()
        self.stack_names = [stack_name]

        bootstrap_command_list = self.get_bootstrap_command_list()

        inputs = [
            stage_name,
            "arn:aws:iam::123:user/user-name",  # pipeline user
            "arn:aws:iam::123:role/role-name",  # Pipeline execution role
            "",  # CloudFormation execution role
            "arn:aws:s3:::bucket-name",  # Artifacts bucket
            "3",  # Should we create ECR repo, 3 - specify one
            "arn:aws:ecr:::repository/repo-name",  # ecr repo
            "1.2.3.4/24",  # Pipeline IP address range
            "y",  # proceed
        ]

        bootstrap_process_execute = self.run_command_with_inputs(bootstrap_command_list, inputs)

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("Successfully created!", stdout)
        # make sure the not provided resource is the only resource created.
        self.assertSetEqual({"CloudFormationExecutionRole"}, self._extract_created_resource_logical_ids(stack_name))

    def test_interactive_pipeline_user_only_created_once(self):
        """
        Create 3 stages, only the first stage resource stack creates
        a pipeline user, and the remaining two share the same pipeline user.
        """
        stage_names = []
        for suffix in ["1", "2", "3"]:
            stage_name, stack_name = self._get_stage_and_stack_name(suffix)
            stage_names.append(stage_name)
            self.stack_names.append(stack_name)

        bootstrap_command_list = self.get_bootstrap_command_list()

        for i, stage_name in enumerate(stage_names):
            inputs = [
                stage_name,
                *([""] if i == 0 else []),  # pipeline user
                "arn:aws:iam::123:role/role-name",  # Pipeline execution role
                "arn:aws:iam::123:role/role-name",  # CloudFormation execution role
                "arn:aws:s3:::bucket-name",  # Artifacts bucket
                "1",  # Should we create ECR repo, 1 - No, 2 - Yes
                "",  # Pipeline IP address range
                "y",  # proceed
            ]

            bootstrap_process_execute = run_command_with_input(
                bootstrap_command_list, ("\n".join(inputs) + "\n").encode()
            )

            self.assertEqual(bootstrap_process_execute.process.returncode, 0)
            stdout = bootstrap_process_execute.stdout.decode()

            # only first stage creates pipeline user
            if i == 0:
                self.assertIn("We have created the following resources", stdout)
                self.assertSetEqual(
                    {"PipelineUser", "PipelineUserAccessKey"},
                    self._extract_created_resource_logical_ids(self.stack_names[i]),
                )
            else:
                self.assertIn("skipping creation", stdout)
