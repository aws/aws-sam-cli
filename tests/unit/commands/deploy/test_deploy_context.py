"""Test sam deploy command"""

import json
from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import ANY, patch, MagicMock, Mock
import tempfile

from samcli.lib.deploy.deployer import Deployer
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.deploy.exceptions import DeployBucketRequiredError, DeployFailedError, ChangeEmptyError
from samcli.lib.deploy.utils import FailureMode
from samcli.commands.deploy.exceptions import DeployFailedError
from samcli.lib.observability.util import OutputOption


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
            max_wait_duration=60,
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
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_json_output_emits_success_document(self, mock_client, mock_session):
        # In JSON mode the successful execute path writes a single SUCCESS result document to stdout.
        # region is read off the s3 client config, so give the mock a real (serializable) value.
        mock_client.return_value._client_config.region_name = "us-east-1"
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.output = "json"
            self.deploy_command_context._output_mode = OutputOption.json

            stdout = StringIO()
            with redirect_stdout(stdout):
                self.deploy_command_context.run()

            emitted = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertEqual(emitted["type"], "result")
            self.assertEqual(emitted["status"], "success")
            self.assertEqual(emitted["region"], "us-east-1")
            # Non-express deploy is fully settled.
            self.assertFalse(emitted["express"])

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_json_output_success_carries_express_flag(self, mock_client, mock_session):
        # --express deploys may still be stabilizing; the SUCCESS document must carry express=True so a
        # consumer can tell it apart from a settled deploy (text mode prints a warning it cannot read).
        mock_client.return_value._client_config.region_name = "us-east-1"
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.output = "json"
            self.deploy_command_context._output_mode = OutputOption.json
            self.deploy_command_context.express = True

            stdout = StringIO()
            with redirect_stdout(stdout):
                self.deploy_command_context.run()

            emitted = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertEqual(emitted["status"], "success")
            self.assertTrue(emitted["express"])

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(
        Deployer,
        "create_and_wait_for_changeset",
        MagicMock(side_effect=DeployFailedError(stack_name="stack-name", msg="boom")),
    )
    def test_json_output_deploy_failure_emits_no_result_line_from_context(self, mock_client, mock_session):
        # DeployFailedError propagates to do_cli, which emits the single terminal FAILED line. The
        # context must NOT also emit one, or the stream would carry a duplicate result (regression:
        # a broad do_cli handler on top of a per-handler emit double-counted the failure).
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.output = "json"
            self.deploy_command_context._output_mode = OutputOption.json

            stdout = StringIO()
            with redirect_stdout(stdout):
                with self.assertRaises(DeployFailedError):
                    self.deploy_command_context.run()

            self.assertEqual(stdout.getvalue().strip(), "")

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_json_output_no_execute_changeset_emits_changeset_created(self, mock_client, mock_session):
        # --no-execute-changeset in JSON mode reports CHANGESET_CREATED and does not execute.
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name
            self.deploy_command_context.no_execute_changeset = True
            self.deploy_command_context.output = "json"
            self.deploy_command_context._output_mode = OutputOption.json

            stdout = StringIO()
            with redirect_stdout(stdout):
                self.deploy_command_context.run()

            emitted = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertEqual(emitted["status"], "changeset_created")
            self.assertEqual(self.deploy_command_context.deployer.execute_changeset.call_count, 0)

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
                ANY,
                parameter_overrides={"a": "b"},
                global_parameter_overrides={"AWS::Region": "any-aws-region"},
                language_extensions_enabled=False,
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
            max_wait_duration=60,
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

            with self.assertRaises(DeployFailedError):
                self.deploy_command_context.run()

            self.assertEqual(self.deploy_command_context.deployer.rollback_delete_stack.call_count, 1)

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "get_last_event_time", MagicMock(return_value=1000))
    def test_on_failure_do_nothing(self, mock_session, mock_client):
        with tempfile.NamedTemporaryFile(delete=False) as template_file:
            template_file.write(b"{}")
            template_file.flush()
            self.deploy_command_context.template_file = template_file.name

            self.deploy_command_context.on_failure = FailureMode.DO_NOTHING

            self.deploy_command_context.run()

            self.deploy_command_context.deployer.wait_for_execute.assert_called_with(
                ANY, "CREATE", False, FailureMode.DO_NOTHING, 1000, 60
            )


class TestDeployContextLanguageExtensions(TestCase):
    """Test cases for language extensions support in DeployContext"""

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.deploy.deploy_context.auth_per_resource")
    @patch("samcli.commands.deploy.deploy_context.SamLocalStackProvider.get_stacks")
    @patch.object(Deployer, "create_and_wait_for_changeset", MagicMock(return_value=({"Id": "test"}, "CREATE")))
    @patch.object(Deployer, "execute_changeset", MagicMock())
    @patch.object(Deployer, "wait_for_execute", MagicMock())
    def test_deploy_preserves_foreach_structure(
        self, patched_get_stacks, patched_auth_required, mock_client, mock_session
    ):
        """Test that sam deploy passes the original template with Fn::ForEach intact to CloudFormation"""
        patched_get_stacks.return_value = (Mock(), [])
        patched_auth_required.return_value = []

        # Template with Fn::ForEach structure
        template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform:
  - AWS::LanguageExtensions
  - AWS::Serverless-2016-10-31
Resources:
  Fn::ForEach::Functions:
    - Name
    - [Alpha, Beta]
    - ${Name}Function:
        Type: AWS::Serverless::Function
        Properties:
          CodeUri: s3://bucket/code.zip
          Handler: ${Name}.handler
          Runtime: python3.9
"""

        deploy_context = DeployContext(
            template_file="template-file",
            stack_name="stack-name",
            s3_bucket="s3-bucket",
            image_repository=None,
            image_repositories=None,
            force_upload=True,
            no_progressbar=False,
            s3_prefix="s3-prefix",
            kms_key_id=None,
            parameter_overrides={},
            capabilities="CAPABILITY_IAM",
            no_execute_changeset=False,
            role_arn=None,
            notification_arns=[],
            fail_on_empty_changeset=False,
            tags={},
            region="us-east-1",
            profile=None,
            confirm_changeset=False,
            signing_profiles=None,
            use_changeset=True,
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
            max_wait_duration=60,
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as template_file:
            template_file.write(template_content)
            template_file.flush()
            deploy_context.template_file = template_file.name

            deploy_context.run()

            # Verify that create_and_wait_for_changeset was called with the original template
            # containing Fn::ForEach (not expanded)
            call_args = deploy_context.deployer.create_and_wait_for_changeset.call_args
            cfn_template = call_args[1]["cfn_template"]

            # The template should contain Fn::ForEach::Functions (not expanded)
            self.assertIn("Fn::ForEach::Functions", cfn_template)
            self.assertIn("${Name}Function", cfn_template)
            self.assertIn("${Name}.handler", cfn_template)

            # The template should NOT contain expanded function names
            self.assertNotIn("AlphaFunction:", cfn_template)
            self.assertNotIn("BetaFunction:", cfn_template)

    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.deploy.deploy_context.auth_per_resource")
    @patch("samcli.commands.deploy.deploy_context.SamLocalStackProvider.get_stacks")
    @patch.object(Deployer, "sync", MagicMock())
    def test_sync_preserves_foreach_structure(
        self, patched_get_stacks, patched_auth_required, mock_client, mock_session
    ):
        """Test that sam sync passes the original template with Fn::ForEach intact to CloudFormation"""
        patched_get_stacks.return_value = (Mock(), [])
        patched_auth_required.return_value = []

        # Template with Fn::ForEach structure
        template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform:
  - AWS::LanguageExtensions
  - AWS::Serverless-2016-10-31
Resources:
  Fn::ForEach::Functions:
    - Name
    - [Alpha, Beta]
    - ${Name}Function:
        Type: AWS::Serverless::Function
        Properties:
          CodeUri: s3://bucket/code.zip
          Handler: ${Name}.handler
          Runtime: python3.9
"""

        sync_context = DeployContext(
            template_file="template-file",
            stack_name="stack-name",
            s3_bucket="s3-bucket",
            image_repository=None,
            image_repositories=None,
            force_upload=True,
            no_progressbar=False,
            s3_prefix="s3-prefix",
            kms_key_id=None,
            parameter_overrides={},
            capabilities="CAPABILITY_IAM",
            no_execute_changeset=False,
            role_arn=None,
            notification_arns=[],
            fail_on_empty_changeset=False,
            tags={},
            region="us-east-1",
            profile=None,
            confirm_changeset=False,
            signing_profiles=None,
            use_changeset=False,  # Use sync instead of changeset
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
            max_wait_duration=60,
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as template_file:
            template_file.write(template_content)
            template_file.flush()
            sync_context.template_file = template_file.name

            sync_context.run()

            # Verify that sync was called with the original template
            # containing Fn::ForEach (not expanded)
            call_args = sync_context.deployer.sync.call_args
            cfn_template = call_args[1]["cfn_template"]

            # The template should contain Fn::ForEach::Functions (not expanded)
            self.assertIn("Fn::ForEach::Functions", cfn_template)
            self.assertIn("${Name}Function", cfn_template)
            self.assertIn("${Name}.handler", cfn_template)

            # The template should NOT contain expanded function names
            self.assertNotIn("AlphaFunction:", cfn_template)
            self.assertNotIn("BetaFunction:", cfn_template)


class TestDeployContextLanguageExtensionsFlag(TestCase):
    """Test cases for language_extensions kwarg support in DeployContext"""

    def _ctx(self, **kwargs):
        from samcli.commands.deploy.deploy_context import DeployContext

        defaults = dict(
            template_file="template.yaml",
            stack_name="s",
            s3_bucket=None,
            image_repository=None,
            image_repositories=None,
            force_upload=False,
            no_progressbar=False,
            s3_prefix="",
            kms_key_id=None,
            parameter_overrides={},
            capabilities=(),
            no_execute_changeset=False,
            role_arn=None,
            notification_arns=(),
            fail_on_empty_changeset=False,
            tags={},
            region=None,
            profile=None,
            confirm_changeset=False,
            signing_profiles={},
            use_changeset=True,
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
            max_wait_duration=60,
        )
        defaults.update(kwargs)
        return DeployContext(**defaults)

    def test_default_is_false(self):
        assert self._ctx().language_extensions_enabled is False

    def test_explicit_true(self):
        assert self._ctx(language_extensions=True).language_extensions_enabled is True
