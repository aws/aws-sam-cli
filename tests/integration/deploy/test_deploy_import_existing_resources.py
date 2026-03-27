import uuid

import boto3

from tests.integration.deploy.deploy_integ_base import DeployIntegBase


class TestDeployImportExistingResources(DeployIntegBase):
    def setUp(self):
        super().setUp()
        self.ssm_client = boto3.client("ssm")
        self.parameter_name = f"/sam-cli-integ/import-test-{uuid.uuid4().hex[:8]}"

        # Create the SSM parameter as a pre-existing resource
        self.ssm_client.put_parameter(
            Name=self.parameter_name,
            Value="import-test",
            Type="String",
        )

    def tearDown(self):
        # Clean up the SSM parameter (retained by stack delete)
        try:
            self.ssm_client.delete_parameter(Name=self.parameter_name)
        except self.ssm_client.exceptions.ParameterNotFound:
            pass
        super().tearDown()

    def test_deploy_with_import_existing_resources(self):
        template_path = self.test_data_path.joinpath("aws-ssm-parameter-import.yaml")

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.s3_bucket.name,
            s3_prefix=self.s3_prefix,
            parameter_overrides=f"ParameterName={self.parameter_name}",
            import_existing_resources=True,
            confirm_changeset=False,
            no_execute_changeset=False,
        )

        deploy_process_execute = self.run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        # Verify the changeset output mentions Import
        self.assertIn("Import", deploy_process_execute.stdout.decode())
