from botocore.exceptions import ClientError
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import CompanionStackManager, sync_ecr_stack
from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, patch


class TestCompanionStackManager(TestCase):
    def setUp(self):
        self.stack_name = "StackA"
        self.companion_stack_name = "CompanionStackA"

        self.boto3_client_patch = patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.boto3.client")
        self.boto3_client_mock = self.boto3_client_patch.start()

        self.companion_stack_patch = patch(
            "samcli.lib.bootstrap.companion_stack.companion_stack_manager.CompanionStack"
        )
        self.companion_stack_mock = self.companion_stack_patch.start()

        self.companion_stack_builder_patch = patch(
            "samcli.lib.bootstrap.companion_stack.companion_stack_manager.CompanionStackBuilder"
        )
        self.companion_stack_builder_mock = self.companion_stack_builder_patch.start()

        self.cfn_client = Mock()
        self.ecr_client = Mock()
        self.s3_client = Mock()
        self.sts_client = Mock()

        self.companion_stack_mock.return_value.stack_name = self.companion_stack_name
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]
        self.manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix")

    def tearDown(self):
        self.boto3_client_patch.stop()
        self.companion_stack_patch.stop()
        self.companion_stack_builder_patch.stop()

    def test_set_functions(self):
        function_a = "FunctionA"
        function_b = "FunctionB"

        self.manager.set_functions([function_a, function_b])

        self.companion_stack_builder_mock.return_value.clear_functions.assert_called_once()
        self.companion_stack_builder_mock.return_value.add_function.assert_any_call(function_a)
        self.companion_stack_builder_mock.return_value.add_function.assert_any_call(function_b)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.mktempfile")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.S3Uploader")
    def test_create_companion_stack(
        self,
        s3_uploader_mock,
        mktempfile_mock,
    ):
        cfn_waiter = Mock()
        self.cfn_client.get_waiter.return_value = cfn_waiter

        self.manager.does_companion_stack_exist = lambda: False

        self.manager.update_companion_stack()

        self.companion_stack_builder_mock.return_value.build.assert_called_once()
        s3_uploader_mock.return_value.upload_with_dedup.assert_called_once()
        self.cfn_client.create_stack.assert_called_once_with(
            StackName=self.companion_stack_name, TemplateURL=ANY, Capabilities=ANY
        )
        self.cfn_client.get_waiter.assert_called_once_with("stack_create_complete")
        cfn_waiter.wait.assert_called_once_with(StackName=self.companion_stack_name, WaiterConfig=ANY)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.mktempfile")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.S3Uploader")
    def test_update_companion_stack(
        self,
        s3_uploader_mock,
        mktempfile_mock,
    ):
        cfn_waiter = Mock()
        self.cfn_client.get_waiter.return_value = cfn_waiter

        self.manager.does_companion_stack_exist = lambda: True

        self.manager.update_companion_stack()

        self.companion_stack_builder_mock.return_value.build.assert_called_once()
        s3_uploader_mock.return_value.upload_with_dedup.assert_called_once()
        self.cfn_client.update_stack.assert_called_once_with(
            StackName=self.companion_stack_name, TemplateURL=ANY, Capabilities=ANY
        )
        self.cfn_client.get_waiter.assert_called_once_with("stack_update_complete")
        cfn_waiter.wait.assert_called_once_with(StackName=self.companion_stack_name, WaiterConfig=ANY)

    def test_delete_companion_stack(self):
        cfn_waiter = Mock()
        self.cfn_client.get_waiter.return_value = cfn_waiter

        self.manager._delete_companion_stack()

        self.cfn_client.delete_stack.assert_called_once_with(StackName=self.companion_stack_name)
        self.cfn_client.get_waiter.assert_called_once_with("stack_delete_complete")
        cfn_waiter.wait.assert_called_once_with(StackName=self.companion_stack_name, WaiterConfig=ANY)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.ECRRepo")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.boto3.resource")
    def test_list_deployed_repos(self, boto3_resource_mock, ecr_repo_mock):
        repo_a = "ECRRepoA"
        repo_b = "ECRRepoB"

        resource_a = Mock()
        resource_a.resource_type = "AWS::ECR::Repository"
        resource_a.logical_resource_id = repo_a
        resource_b = Mock()
        resource_b.resource_type = "AWS::ECR::Repository"
        resource_b.logical_resource_id = repo_b
        resource_c = Mock()
        resource_c.resource_type = "RandomResource"
        resources = [resource_a, resource_b, resource_c]
        boto3_resource_mock.return_value.Stack.return_value.resource_summaries.all.return_value = resources

        self.manager.does_companion_stack_exist = lambda: True

        repos = self.manager.list_deployed_repos()
        self.assertTrue(len(repos) == 2)
        ecr_repo_mock.assert_any_call(logical_id=repo_a, physical_id=ANY)
        ecr_repo_mock.assert_any_call(logical_id=repo_b, physical_id=ANY)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.ECRRepo")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.boto3.resource")
    def test_list_deployed_repos_does_not_exist(self, boto3_resource_mock, ecr_repo_mock):
        repo_a = "ECRRepoA"
        repo_b = "ECRRepoB"

        resource_a = Mock()
        resource_a.resource_type = "AWS::ECR::Repository"
        resource_a.logical_resource_id = repo_a
        resource_b = Mock()
        resource_b.resource_type = "AWS::ECR::Repository"
        resource_b.logical_resource_id = repo_b
        resource_c = Mock()
        resource_c.resource_type = "RandomResource"
        resources = [resource_a, resource_b, resource_c]
        boto3_resource_mock.return_value.Stack.return_value.resource_summaries.all.return_value = resources

        self.manager.does_companion_stack_exist = lambda: False

        repos = self.manager.list_deployed_repos()
        self.assertEqual(repos, [])

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.ECRRepo")
    def test_get_unreferenced_repos(self, ecr_repo_mock):
        repo_a_id = "ECRRepoA"
        repo_b_id = "ECRRepoB"

        current_repo_a = Mock()
        current_repo_a.logical_id = repo_a_id
        current_repos = {"FunctionA": current_repo_a}

        repo_a = Mock()
        repo_a.logical_id = repo_a_id
        repo_b = Mock()
        repo_b.logical_id = repo_b_id
        deployed_repos = [repo_a, repo_b]

        self.manager.does_companion_stack_exist = lambda: True
        self.manager.list_deployed_repos = lambda: deployed_repos
        self.companion_stack_builder_mock.return_value.repo_mapping = current_repos

        unreferenced_repos = self.manager.get_unreferenced_repos()
        self.assertEqual(len(unreferenced_repos), 1)
        self.assertEqual(unreferenced_repos[0].logical_id, repo_b_id)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.ECRRepo")
    def test_get_unreferenced_repos_does_not_exist(self, ecr_repo_mock):
        repo_a_id = "ECRRepoA"
        repo_b_id = "ECRRepoB"

        current_repo_a = Mock()
        current_repo_a.logical_id = repo_a_id
        current_repos = {"FunctionA": current_repo_a}

        repo_a = Mock()
        repo_a.logical_id = repo_a_id
        repo_b = Mock()
        repo_b.logical_id = repo_b_id
        deployed_repos = [repo_a, repo_b]

        self.manager.does_companion_stack_exist = lambda: False
        self.manager.list_deployed_repos = lambda: deployed_repos
        self.companion_stack_builder_mock.return_value.repo_mapping = current_repos

        unreferenced_repos = self.manager.get_unreferenced_repos()
        self.assertEqual(unreferenced_repos, [])

    def test_delete_unreferenced_repos(self):
        repo_a_id = "ECRRepoA"
        repo_b_id = "ECRRepoB"

        repo_a = Mock()
        repo_a.physical_id = repo_a_id
        repo_b = Mock()
        repo_b.physical_id = repo_b_id
        unreferenced_repos = [repo_a, repo_b]

        self.manager.get_unreferenced_repos = lambda: unreferenced_repos

        self.manager.delete_unreferenced_repos()

        self.ecr_client.delete_repository.assert_any_call(repositoryName=repo_a_id, force=True)
        self.ecr_client.delete_repository.assert_any_call(repositoryName=repo_b_id, force=True)

    def test_sync_repos_exists(self):
        self.manager.does_companion_stack_exist = lambda: True
        self.manager.get_repository_mapping = lambda: {"a": ""}
        self.manager.delete_unreferenced_repos = Mock()
        self.manager.update_companion_stack = Mock()
        self.manager._delete_companion_stack = Mock()

        self.manager.sync_repos()
        self.manager.delete_unreferenced_repos.assert_called_once()
        self.manager._delete_companion_stack.assert_not_called()
        self.manager.update_companion_stack.assert_called_once()

    def test_sync_repos_exists_with_no_repo(self):
        self.manager.does_companion_stack_exist = lambda: True
        self.manager.get_repository_mapping = lambda: {}
        self.manager.delete_unreferenced_repos = Mock()
        self.manager.update_companion_stack = Mock()
        self.manager._delete_companion_stack = Mock()

        self.manager.sync_repos()
        self.manager.delete_unreferenced_repos.assert_called_once()
        self.manager._delete_companion_stack.assert_called_once()
        self.manager.update_companion_stack.assert_not_called()

    def test_sync_repos_does_not_exist(self):
        self.manager.does_companion_stack_exist = lambda: False
        self.manager.get_repository_mapping = lambda: {"a": ""}
        self.manager.delete_unreferenced_repos = Mock()
        self.manager.update_companion_stack = Mock()
        self.manager._delete_companion_stack = Mock()

        self.manager.sync_repos()
        self.manager.delete_unreferenced_repos.assert_not_called()
        self.manager._delete_companion_stack.assert_not_called()
        self.manager.update_companion_stack.assert_called_once()

    def test_does_companion_stack_exist_true(self):
        self.cfn_client.describe_stacks.return_value = {"a": "a"}
        self.assertTrue(self.manager.does_companion_stack_exist())

    def test_does_companion_stack_exist_false(self):
        error = ClientError({}, Mock())
        error_message = f"Stack with id {self.companion_stack_name} does not exist"
        error.response = {"Error": {"Message": error_message}}
        self.cfn_client.describe_stacks.side_effect = error
        self.assertFalse(self.manager.does_companion_stack_exist())

    def test_does_companion_stack_exist_error(self):
        error = ClientError({}, Mock())
        self.cfn_client.describe_stacks.side_effect = error
        with self.assertRaises(ClientError):
            self.assertFalse(self.manager.does_companion_stack_exist())

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.CompanionStackManager")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamLocalStackProvider")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamFunctionProvider")
    def test_sync_ecr_stack(self, function_provider_mock, stack_provider_mock, manager_mock):
        image_repositories = {"Function1": "uri1"}
        stacks = MagicMock()
        stack_provider_mock.get_stacks.return_value = (stacks, None)
        manager_mock.return_value.get_repository_mapping.return_value = {"Function2": "uri2"}

        result = sync_ecr_stack("template.yaml", "stack-name", "region", "s3-bucket", "s3-prefix", image_repositories)

        manager_mock.assert_called_once_with("stack-name", "region", "s3-bucket", "s3-prefix")
        function_provider_mock.assert_called_once_with(stacks, ignore_code_extraction_warnings=True)
        manager_mock.return_value.sync_repos.assert_called_once_with()

        self.assertEqual(result, {"Function1": "uri1", "Function2": "uri2"})
