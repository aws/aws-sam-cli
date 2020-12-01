"""Test sam deploy command"""
from unittest import TestCase
from unittest.mock import patch, MagicMock
import tempfile

from samcli.lib.deploy.deployer import Deployer
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.deploy.exceptions import DeployBucketRequiredError, DeployFailedError, ChangeEmptyError


class TestSamDeployCommand(TestCase):
    def setUp(self):
        self.deploy_command_context = DeployContext(
            template_file="template-file",
            stack_name="stack-name",
            s3_bucket="s3-bucket",
            image_repository="image-repo",
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
        )

    def test_template_improper(self):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            with self.assertRaises(DeployFailedError):
                self.deploy_command_context.template_file = template_file.name
                self.deploy_command_context.run()

    def test_template_size_large_no_s3_bucket(self):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b" " * 51200)
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.s3_bucket = None
            with self.assertRaises(DeployBucketRequiredError):
                self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_size_large_and_s3_bucket(self, patched_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b" " * 51200)
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.run()

    @patch("boto3.Session")
    def test_template_valid(self, patched_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.deploy = MagicMock()
            self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch.object(
        Deployer, "create_and_wait_for_changeset", MagicMock(side_effect=ChangeEmptyError(stack_name="stack-name"))
    )
    def test_template_valid_change_empty(self, patched_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.fail_on_empty_changeset = True
            self.deploy_command_context.template_file = template_file.name

            with self.assertRaises(ChangeEmptyError):
                self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch.object(
        Deployer, "create_and_wait_for_changeset", MagicMock(side_effect=ChangeEmptyError(stack_name="stack-name"))
    )
    def test_template_valid_change_empty_no_fail_on_empty_changeset(self, patched_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.run()

    @patch("boto3.Session")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_execute_changeset(self, patched_boto):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.run()
            self.assertEqual(self.deploy_command_context.deployer.create_and_wait_for_changeset.call_count, 1)
            self.assertEqual(self.deploy_command_context.deployer.execute_changeset.call_count, 1)
            self.assertEqual(self.deploy_command_context.deployer.wait_for_execute.call_count, 1)

    @patch("boto3.Session")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_no_execute_changeset(self, patched_boto):
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
    @patch("samcli.commands.deploy.deploy_context.auth_per_resource")
    @patch("samcli.commands.deploy.deploy_context.get_template_data")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_template_valid_execute_changeset_with_parameters(
        self, patched_template_data, patched_auth_required, patched_boto
    ):
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
