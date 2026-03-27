import uuid

import boto3

from tests.integration.deploy.deploy_integ_base import DeployIntegBase


class TestDeployImportExistingResources(DeployIntegBase):
    def setUp(self):
        super().setUp()
        self.sns_client = boto3.client("sns")
        self.topic_name = f"sam-cli-integ-import-test-{uuid.uuid4().hex[:8]}"

        # Create the SNS topic as a pre-existing resource
        response = self.sns_client.create_topic(Name=self.topic_name)
        self.topic_arn = response["TopicArn"]

    def tearDown(self):
        # Clean up the SNS topic (retained by stack delete)
        try:
            self.sns_client.delete_topic(TopicArn=self.topic_arn)
        except Exception:
            pass
        super().tearDown()

    def test_deploy_with_import_existing_resources(self):
        template_path = self.test_data_path.joinpath("aws-sns-topic-import.yaml")

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.s3_bucket.name,
            s3_prefix=self.s3_prefix,
            parameter_overrides=f"TopicName={self.topic_name}",
            import_existing_resources=True,
            confirm_changeset=False,
            no_execute_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # Verify the changeset output mentions Import
        self.assertIn("Import", deploy_process_execute.stdout.decode())
