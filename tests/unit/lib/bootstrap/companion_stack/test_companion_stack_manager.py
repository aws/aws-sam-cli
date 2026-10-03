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
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.parse_s3_url")
    def test_create_companion_stack(
        self,
        parse_s3_url_mock,
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
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.parse_s3_url")
    def test_update_companion_stack(
        self,
        parse_s3_url_mock,
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

    def test_create_companion_stack_with_role_arn(
        self,
    ):
        self._test_companion_stack_with_role_arn(exists=False)

    def test_update_companion_stack_with_role_arn(
        self,
    ):
        self._test_companion_stack_with_role_arn(exists=True)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.mktempfile")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.S3Uploader")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.parse_s3_url")
    def _test_companion_stack_with_role_arn(
        self,
        parse_s3_url_mock,
        s3_uploader_mock,
        mktempfile_mock,
        exists,
    ):
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        role_ecr_client = Mock()
        self.sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        self.boto3_client_mock.side_effect = [
            self.cfn_client,
            self.ecr_client,
            self.s3_client,
            self.sts_client,
            role_ecr_client,
        ]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        # construction does not assume the role: the assume is lazy so
        # deployments whose service role trust policy only covers
        # cloudformation.amazonaws.com keep working.
        self.sts_client.assume_role.assert_not_called()
        self.assertIs(manager._ecr_client, self.ecr_client)

        cfn_waiter = Mock()
        self.cfn_client.get_waiter.return_value = cfn_waiter

        manager.does_companion_stack_exist = lambda: exists
        manager.update_companion_stack()

        stack_call = self.cfn_client.update_stack if exists else self.cfn_client.create_stack
        stack_call.assert_called_once_with(
            StackName=self.companion_stack_name, TemplateURL=ANY, Capabilities=ANY, RoleARN=role_arn
        )
        self.cfn_client.get_waiter.assert_called_once_with(
            "stack_update_complete" if exists else "stack_create_complete"
        )
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

    def test_delete_unreferenced_repos_with_role_arn_uses_assumed_role_client(self):
        # With --role-arn set, direct ECR calls (delete_unreferenced_repos)
        # must go through the assumed-role client, not the caller's.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        role_ecr_client = Mock()
        self.sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        self.boto3_client_mock.side_effect = [
            self.cfn_client,
            self.ecr_client,
            self.s3_client,
            self.sts_client,
            role_ecr_client,
        ]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        # the assume is lazy: no STS call until a direct ECR call happens
        self.sts_client.assume_role.assert_not_called()

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        manager.delete_unreferenced_repos()

        self.sts_client.assume_role.assert_called_once_with(RoleArn=role_arn, RoleSessionName="sam-cli-companion-stack")
        role_ecr_client.delete_repository.assert_called_once_with(repositoryName="ECRRepoStale", force=True)
        self.ecr_client.delete_repository.assert_not_called()

    def test_assume_role_failure_falls_back_to_caller_credentials(self):
        # A CloudFormation service role's trust policy generally only trusts
        # cloudformation.amazonaws.com, so the deploying principal usually
        # cannot assume it. That must not abort the deploy: the assume is
        # lazy and a failure falls back to caller credentials.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        error = ClientError({"Error": {"Code": "AccessDenied", "Message": "not authorized"}}, "AssumeRole")
        self.sts_client.assume_role.side_effect = error
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]

        # construction succeeds even though the role cannot be assumed
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)
        self.sts_client.assume_role.assert_not_called()

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        manager.delete_unreferenced_repos()
        manager.delete_unreferenced_repos()

        # the assume was attempted lazily, exactly once, then fell back to
        # the caller's credentials
        self.sts_client.assume_role.assert_called_once_with(RoleArn=role_arn, RoleSessionName="sam-cli-companion-stack")
        self.assertEqual(self.ecr_client.delete_repository.call_count, 2)

    def test_assume_role_param_validation_error_falls_back_to_caller_credentials(self):
        # --role-arn is an unvalidated free-form string; botocore validates it
        # client-side and raises ParamValidationError (a BotoCoreError, not a
        # ClientError). That must also translate into the documented fallback
        # to caller credentials instead of aborting the deploy with a raw
        # botocore traceback.
        from botocore.exceptions import ParamValidationError

        role_arn = "not-an-arn"
        self.sts_client.assume_role.side_effect = ParamValidationError(report="Invalid RoleArn")
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]

        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        manager.delete_unreferenced_repos()

        self.sts_client.assume_role.assert_called_once_with(RoleArn=role_arn, RoleSessionName="sam-cli-companion-stack")
        self.ecr_client.delete_repository.assert_called_once_with(repositoryName="ECRRepoStale", force=True)

    def test_delete_unreferenced_repos_without_stale_repos_skips_assume_role(self):
        # Zero stale repos is the steady state; the lazy assume-role attempt
        # must not fire (and must not appear in CloudTrail) when there is
        # nothing to delete.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)
        manager.get_unreferenced_repos = lambda: []

        manager.delete_unreferenced_repos()

        self.sts_client.assume_role.assert_not_called()
        self.ecr_client.delete_repository.assert_not_called()

    def test_malformed_assume_role_response_falls_back_to_caller_credentials(self):
        # A malformed AssumeRole response (e.g. a Credentials dict missing
        # the access keys) raises KeyError when the response is consumed.
        # That must translate into the documented fallback to caller
        # credentials, not abort the deploy.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        self.sts_client.assume_role.return_value = {"Credentials": {}}
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]

        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        manager.delete_unreferenced_repos()

        self.sts_client.assume_role.assert_called_once_with(RoleArn=role_arn, RoleSessionName="sam-cli-companion-stack")
        self.ecr_client.delete_repository.assert_called_once_with(repositoryName="ECRRepoStale", force=True)

    def test_role_client_access_denied_on_delete_retries_with_caller_credentials(self):
        # A CloudFormation service role may be assumable yet lack
        # ecr:DeleteRepository. The resulting AccessDenied ClientError on the
        # assumed-role client must fall back to the caller's client instead
        # of aborting the deploy.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        role_ecr_client = Mock()
        role_ecr_client.exceptions.RepositoryNotFoundException = type("RepositoryNotFoundException", (Exception,), {})
        access_denied = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "not authorized"}}, "DeleteRepository"
        )
        role_ecr_client.delete_repository.side_effect = access_denied
        self.sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "<redacted>",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        self.boto3_client_mock.side_effect = [
            self.cfn_client,
            self.ecr_client,
            self.s3_client,
            self.sts_client,
            role_ecr_client,
        ]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        manager.delete_unreferenced_repos()

        role_ecr_client.delete_repository.assert_called_once_with(repositoryName="ECRRepoStale", force=True)
        self.ecr_client.delete_repository.assert_called_once_with(repositoryName="ECRRepoStale", force=True)

    def test_role_client_non_access_denied_error_still_raises(self):
        # Only the AccessDenied permission failure deserves the caller-
        # credential retry; any other ClientError from the assumed-role
        # client must keep propagating.
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        role_ecr_client = Mock()
        role_ecr_client.exceptions.RepositoryNotFoundException = type("RepositoryNotFoundException", (Exception,), {})
        role_ecr_client.delete_repository.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException", "Message": "bad param"}}, "DeleteRepository"
        )
        self.sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "<redacted>",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        self.boto3_client_mock.side_effect = [
            self.cfn_client,
            self.ecr_client,
            self.s3_client,
            self.sts_client,
            role_ecr_client,
        ]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)

        repo = Mock()
        repo.physical_id = "ECRRepoStale"
        manager.get_unreferenced_repos = lambda: [repo]

        with self.assertRaises(ClientError):
            manager.delete_unreferenced_repos()
        self.ecr_client.delete_repository.assert_not_called()

    def test_delete_companion_stack_with_role_arn(self):
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"
        self.boto3_client_mock.side_effect = [self.cfn_client, self.ecr_client, self.s3_client, self.sts_client]
        manager = CompanionStackManager(self.stack_name, "region", "s3_bucket", "s3_prefix", role_arn=role_arn)
        cfn_waiter = Mock()
        self.cfn_client.get_waiter.return_value = cfn_waiter

        manager._delete_companion_stack()

        self.cfn_client.delete_stack.assert_called_once_with(StackName=self.companion_stack_name, RoleARN=role_arn)
        self.cfn_client.get_waiter.assert_called_once_with("stack_delete_complete")
        cfn_waiter.wait.assert_called_once_with(StackName=self.companion_stack_name, WaiterConfig=ANY)

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

        manager_mock.assert_called_once_with("stack-name", "region", "s3-bucket", "s3-prefix", role_arn=None)
        function_provider_mock.assert_called_once_with(stacks, ignore_code_extraction_warnings=True)
        manager_mock.return_value.sync_repos.assert_called_once_with()

        self.assertEqual(result, {"Function1": "uri1", "Function2": "uri2"})

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.CompanionStackManager")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamLocalStackProvider")
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_manager.SamFunctionProvider")
    def test_sync_ecr_stack_with_role_arn(self, function_provider_mock, stack_provider_mock, manager_mock):
        image_repositories = {"Function1": "uri1"}
        stacks = MagicMock()
        stack_provider_mock.get_stacks.return_value = (stacks, None)
        manager_mock.return_value.get_repository_mapping.return_value = {"Function2": "uri2"}
        role_arn = "arn:aws:iam::123456789012:role/CloudFormationServiceRole"

        result = sync_ecr_stack(
            "template.yaml", "stack-name", "region", "s3-bucket", "s3-prefix", image_repositories, role_arn=role_arn
        )

        manager_mock.assert_called_once_with("stack-name", "region", "s3-bucket", "s3-prefix", role_arn=role_arn)
        function_provider_mock.assert_called_once_with(stacks, ignore_code_extraction_warnings=True)
        manager_mock.return_value.sync_repos.assert_called_once_with()

        self.assertEqual(result, {"Function1": "uri1", "Function2": "uri2"})
