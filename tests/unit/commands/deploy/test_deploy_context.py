"""Test sam deploy command"""
from unittest import TestCase
from unittest.mock import ANY, patch, MagicMock, Mock
import tempfile

from samcli.lib.deploy.deployer import Deployer
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.deploy.exceptions import DeployBucketRequiredError, DeployFailedError, ChangeEmptyError
from samcli.lib.deploy.utils import FailureMode
from samcli.commands.deploy.exceptions import DeployFailedError


class TestSamDeployCommand(TestCase):
    def setUp(self):
        self.deploy_command_context = DeployContext(
            template_file="template-file",
            stack_name="stack-name",
            s3_bucket="s3-bucket",
            image_repository="image-repo",
            image_repositories=None,
            force_upload=True,
            no_progressbar=False,
            s3_prefix="s3-prefix",
            kms_key_id="kms-key-id",
            parameter_overrides={"a": "b"},
            capabilities="CAPABILITY_IAM",
            no_execute_changeset=False,
            role_arn="role-arn",
            notification_arns=[],
            fail_on_empty_changeset=False,
            tags={"a": "b"},
            region="any-aws-region",
            profile=None,
            confirm_changeset=False,
            signing_profiles=None,
            use_changeset=True,
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
        )

    @patch("boto3.client")
    @patch("boto3.Session")
    def test_template_improper(self, mock_session, mock_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            with self.assertRaises(DeployFailedError):
                self.deploy_command_context.template_file = template_file.name
                self.deploy_command_context.run()

    @patch("boto3.client")
    @patch("boto3.Session")
    def test_template_size_large_no_s3_bucket(self, mock_session, mock_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b" " * 51200)
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.s3_bucket = None
            with self.assertRaises(DeployBucketRequiredError):
                self.deploy_command_context.run()

    @patch("boto3.client")
    @patch("boto3.Session")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_size_large_and_s3_bucket(self, mock_session, mock_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b" " * 51200)
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch("boto3.client")
    def test_template_valid(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.deploy = MagicMock()
            self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(
        Deployer, "create_and_wait_for_changeset", MagicMock(side_effect=ChangeEmptyError(stack_name="stack-name"))
    )
    def test_template_valid_change_empty(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.fail_on_empty_changeset = True
            self.deploy_command_context.template_file = template_file.name

            with self.assertRaises(ChangeEmptyError):
                self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(
        Deployer, "create_and_wait_for_changeset", MagicMock(side_effect=ChangeEmptyError(stack_name="stack-name"))
    )
    def test_template_valid_change_empty_no_fail_on_empty_changeset(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_execute_changeset(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.run()
            self.assertEqual(self.deploy_command_context.deployer.create_and_wait_for_changeset.call_count, 1)
            self.assertEqual(self.deploy_command_context.deployer.execute_changeset.call_count, 1)
            self.assertEqual(self.deploy_command_context.deployer.wait_for_execute.call_count, 1)

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_no_execute_changeset(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.no_execute_changeset = True

            self.deploy_command_context.run()
            self.assertEqual(self.deploy_command_context.deployer.create_and_wait_for_changeset.call_count, 1)
            self.assertEqual(self.deploy_command_context.deployer.execute_changeset.call_count, 0)
            self.assertEqual(self.deploy_command_context.deployer.wait_for_execute.call_count, 0)

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.deploy.deploy_context.auth_per_resource")
    @patch("samcli.commands.deploy.deploy_context.SamLocalStackProvider.get_stacks")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_execute_changeset_with_parameters(
        self, patched_get_buildable_stacks, patched_auth_required, mock_session, mock_client
    ):
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_auth_required.return_value = [("HelloWorldFunction", False)]
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b'{"Parameters": {"a":"b","c":"d"}}')
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.run()
            self.assertEqual(self.deploy_command_context.deployer.create_and_wait_for_changeset.call_count, 1)
            self.assertEqual(
                self.deploy_command_context.deployer.create_and_wait_for_changeset.call_args[1]["parameter_values"],
                [{"ParameterKey": "a", "ParameterValue": "b"}, {"ParameterKey": "c", "UsePreviousValue": True}],
            )
            patched_get_buildable_stacks.assert_called_once_with(
                ANY, parameter_overrides={"a": "b"}, global_parameter_overrides={"AWS::Region": "any-aws-region"}
            )

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.deploy.deploy_context.auth_per_resource")
    @patch("samcli.commands.deploy.deploy_context.SamLocalStackProvider.get_stacks")
    @patch.object(Deployer, "sync", MagicMock())
    def test_sync(self, patched_get_buildable_stacks, patched_auth_required, mock_client, mock_session):
        sync_context = DeployContext(
            template_file="template-file",
            stack_name="stack-name",
            s3_bucket="s3-bucket",
            image_repository="image-repo",
            image_repositories=None,
            force_upload=True,
            no_progressbar=False,
            s3_prefix="s3-prefix",
            kms_key_id="kms-key-id",
            parameter_overrides={"a": "b"},
            capabilities="CAPABILITY_IAM",
            no_execute_changeset=False,
            role_arn="role-arn",
            notification_arns=[],
            fail_on_empty_changeset=False,
            tags={"a": "b"},
            region=None,
            profile=None,
            confirm_changeset=False,
            signing_profiles=None,
            use_changeset=False,
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
        )
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_auth_required.return_value = [("HelloWorldFunction", False)]
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b'{"Parameters": {"a":"b","c":"d"}}')
            template_file.flush()
            sync_context.template_file = template_file.name
            sync_context.run()

            self.assertEqual(sync_context.deployer.sync.call_count, 1)
            print(sync_context.deployer.sync.call_args[1])
            self.assertEqual(
                sync_context.deployer.sync.call_args[1]["stack_name"],
                "stack-name",
            )
            self.assertEqual(
                sync_context.deployer.sync.call_args[1]["capabilities"],
                "CAPABILITY_IAM",
            )
            self.assertEqual(
                sync_context.deployer.sync.call_args[1]["cfn_template"],
                '{"Parameters": {"a":"b","c":"d"}}',
            )
            self.assertEqual(
                sync_context.deployer.sync.call_args[1]["notification_arns"],
                [],
            )
            self.assertEqual(
                sync_context.deployer.sync.call_args[1]["role_arn"],
                "role-arn",
            )

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "rollback_delete_stack", MagicMock())
    @patch.object(
        Deployer, "execute_changeset", MagicMock(side_effect=DeployFailedError("stack-name", "failed to deploy"))
    )
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_on_failure_delete_rollback_stack(self, mock_client, mock_session):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.on_failure = FailureMode.DELETE

            self.deploy_command_context.run()

            self.assertEqual(self.deploy_command_context.deployer.rollback_delete_stack.call_count, 1)

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    def test_on_failure_do_nothing(self, mock_session, mock_client):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.on_failure = FailureMode.DO_NOTHING

            self.deploy_command_context.run()

            self.deploy_command_context.deployer.wait_for_execute.assert_called_with(
                ANY, "CREATE", True, FailureMode.DO_NOTHING
            )
