import os
import uuid

import boto3

from tests.integration.deploy.deploy_integ_base import DeployIntegBase

# Auto-import requires a static custom name (no !Ref or intrinsic functions)
# and a primaryIdentifier that is settable in the template (not read-only).
# AWS::Logs::LogGroup meets both requirements (primaryIdentifier is LogGroupName).
# See: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/import-resources-automatically.html
TEMPLATE = """\
AWSTemplateFormatVersion: '2010-09-09'
Description: Template for testing --import-existing-resources flag.
Resources:
  TestLogGroup:
    DeletionPolicy: Retain
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: {log_group_name}
"""


class TestDeployImportExistingResources(DeployIntegBase):
    def setUp(self):
        super().setUp()
        self.logs_client = boto3.client("logs")
        self.log_group_name = f"/sam-cli/integ-import-test-{uuid.uuid4().hex[:8]}"

        # Create the log group as a pre-existing resource
        self.logs_client.create_log_group(logGroupName=self.log_group_name)

        # Write template with static name (required for auto-import)
        self.template_path = os.path.join(self.test_data_path, "aws-logs-loggroup-import.yaml")
        with open(self.template_path, "w") as f:
            f.write(TEMPLATE.format(log_group_name=self.log_group_name))

    def tearDown(self):
        try:
            self.logs_client.delete_log_group(logGroupName=self.log_group_name)
        except Exception:
            pass
        super().tearDown()

    def test_deploy_with_import_existing_resources(self):
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=self.template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.s3_bucket.name,
            s3_prefix=self.s3_prefix,
            import_existing_resources=True,
            confirm_changeset=False,
            no_execute_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.assertIn("Import", deploy_process_execute.stdout.decode())
