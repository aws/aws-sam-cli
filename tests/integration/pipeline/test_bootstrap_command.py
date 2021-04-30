from unittest import skipIf

from parameterized import parameterized

from samcli.lib.pipeline.bootstrap.stage import Stage
from tests.integration.pipeline.bootstrap_integ_base import BootstrapIntegBase
from tests.testing_utils import run_command_with_input, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# bootstrap tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_DEPLOY_TESTS, "Skip bootstrap tests in CI/CD only")
class TestBootstrap(BootstrapIntegBase):
    @parameterized.expand([("create_ecr_repo",), (False,)])
    def test_interactive_with_no_resources_provided(self, create_ecr_repo: bool):
        stage_name = self._method_to_stage_name(self.id())
        self.stack_names = [Stage._get_stack_name(stage_name)]

        bootstrap_command_list = self.get_bootstrap_command_list(interactive=True)

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

        bootstrap_process_execute = run_command_with_input(bootstrap_command_list, ("\n".join(inputs) + "\n").encode())

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("We have created the following resources", stdout)
        # make sure pipeline user's credential is printed
        self.assertIn("ACCESS_KEY_ID", stdout)
        self.assertIn("SECRET_ACCESS_KEY", stdout)
        if create_ecr_repo:
            self.assertIn("arn:aws:ecr:", stdout)
            self.assertEqual(5, self._count_created_resources(stdout))
        else:
            self.assertNotIn("arn:aws:ecr:", stdout)
            self.assertEqual(4, self._count_created_resources(stdout))

    def test_interactive_with_all_required_resources_provided(self):
        stage_name = self._method_to_stage_name(self.id())
        self.stack_names = [Stage._get_stack_name(stage_name)]

        bootstrap_command_list = self.get_bootstrap_command_list(interactive=True)

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

        bootstrap_process_execute = run_command_with_input(bootstrap_command_list, ("\n".join(inputs) + "\n").encode())

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("skipping creation", stdout)

    def test_interactive_cancelled_by_user(self):
        stage_name = self._method_to_stage_name(self.id())
        self.stack_names = [Stage._get_stack_name(stage_name)]

        bootstrap_command_list = self.get_bootstrap_command_list(interactive=True)

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

        bootstrap_process_execute = run_command_with_input(bootstrap_command_list, ("\n".join(inputs) + "\n").encode())

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertTrue(stdout.strip().endswith("Should we proceed with the creation? [y/N]:"))

    def test_interactive_with_some_required_resources_provided(self):
        stage_name = self._method_to_stage_name(self.id())
        self.stack_names = [Stage._get_stack_name(stage_name)]

        bootstrap_command_list = self.get_bootstrap_command_list(interactive=True)

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

        bootstrap_process_execute = run_command_with_input(bootstrap_command_list, ("\n".join(inputs) + "\n").encode())

        self.assertEqual(bootstrap_process_execute.process.returncode, 0)
        stdout = bootstrap_process_execute.stdout.decode()
        self.assertIn("Successfully created!", stdout)
        # make sure the not provided resource is the only resource created.
        self.assertIn("aws-sam-cli-managed-test-CloudFormationExecution", stdout)
        self.assertEqual(1, self._count_created_resources(stdout))

    def test_interactive_pipeline_user_only_created_once(self):
        """
        Create 3 stages, only the first stage resource stack creates
        a pipeline user, and the remaining two share the same pipeline user.
        """
        stage_names = [
            self._method_to_stage_name(self.id() + "1"),
            self._method_to_stage_name(self.id() + "2"),
            self._method_to_stage_name(self.id() + "3"),
        ]
        self.stack_names = [Stage._get_stack_name(stage_name) for stage_name in stage_names]

        bootstrap_command_list = self.get_bootstrap_command_list(interactive=True)

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
                self.assertIn("PipelineUser", str(self._extract_created_resources(stdout)))
                self.assertEqual(1, self._count_created_resources(stdout))
            else:
                self.assertNotIn("PipelineUser", str(self._extract_created_resources(stdout)))
                self.assertEqual(0, self._count_created_resources(stdout))
