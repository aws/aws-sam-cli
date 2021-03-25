from unittest import TestCase
from unittest.mock import ANY, Mock, patch
from samcli.local.common.runtime_template import RUNTIME_TO_BUILD_IMAGE
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.config import PLUGIN_NAME  # type: ignore
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.context import Context  # type: ignore
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor import Preprocessor  # type: ignore
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.stage import Stage  # type: ignore
from .test_context import (
    ANY_TESTING_DEPLOYER_ROLE,
    ANY_TESTING_CFN_DEPLOYMENT_ROLE,
    ANY_TESTING_ARTIFACTS_BUCKET,
    ANY_DEPLOYER_ARN,
)

# Let the user provide the deployer and the testing-stage resources and the plugin creates the prod-resources
plugin_context_with_deployer_and_testing_resources_but_no_prod_resources = {
    "testing_deployer_role": ANY_TESTING_DEPLOYER_ROLE,
    "testing_cfn_deployment_role": ANY_TESTING_CFN_DEPLOYMENT_ROLE,
    "testing_artifacts_bucket": ANY_TESTING_ARTIFACTS_BUCKET,
    "deployer_arn": ANY_DEPLOYER_ARN,
}
ANY_SAM_TEMPLATE = "any/sam/template.yaml"
context = {"sam_template": ANY_SAM_TEMPLATE}
context.update(plugin_context_with_deployer_and_testing_resources_but_no_prod_resources)
preprocessor: Preprocessor = Preprocessor()


class TestPreprocessor(TestCase):
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.get_template_function_runtimes")
    def test_used_build_image_when_sam_template_has_no_runtimes(self, get_template_function_runtimes_mock):
        # setup
        get_template_function_runtimes_mock.return_value = []
        # trigger
        build_image = preprocessor._get_build_image(sam_template_file=ANY_SAM_TEMPLATE)
        # verify
        self.assertEqual(build_image, Preprocessor.BASIC_PROVIDED_BUILD_IMAGE)

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.get_template_function_runtimes")
    def test_used_build_image_when_sam_template_has_one_supported_runtime(self, get_template_function_runtimes_mock):
        # setup
        get_template_function_runtimes_mock.return_value = ["python3.8"]
        # trigger
        build_image = preprocessor._get_build_image(sam_template_file=ANY_SAM_TEMPLATE)
        # verify
        self.assertEqual(build_image, RUNTIME_TO_BUILD_IMAGE["python3.8"])

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.get_template_function_runtimes")
    def test_used_build_image_when_sam_template_has_one_unsupported_runtime(
        self, get_template_function_runtimes_mock, click_mock
    ):
        # setup
        click_mock.prompt.return_value = "user-provided-build-image"
        get_template_function_runtimes_mock.return_value = ["any-unsupported-runtime"]
        # trigger
        build_image = preprocessor._get_build_image(sam_template_file=ANY_SAM_TEMPLATE)
        # verify
        click_mock.prompt.assert_called_once()
        self.assertEqual(build_image, "user-provided-build-image")

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.get_template_function_runtimes")
    def test_used_build_image_when_sam_template_has_multiple_runtimes(
        self, get_template_function_runtimes_mock, click_mock
    ):
        # setup
        click_mock.prompt.return_value = "user-provided-build-image"
        get_template_function_runtimes_mock.return_value = ["python3.8", "python3.7", "any-unsupported-runtime"]
        # trigger
        build_image = preprocessor._get_build_image(sam_template_file=ANY_SAM_TEMPLATE)
        # verify
        click_mock.prompt.assert_called_once()
        self.assertEqual(build_image, "user-provided-build-image")

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_deployer(self, manage_cloudformation_stack_mock, click_mock):
        # setup
        stage_mock = Mock()
        stage_mock.profile.return_value = "any-profile"
        stage_mock.region.return_value = "any-region"
        stage_mock.stack_name.return_value = "any-stack-name"
        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "Deployer", "OutputValue": "any-deployer-arn"},
            {"OutputKey": "AccessKeyId", "OutputValue": "any-access-key-id"},
            {"OutputKey": "SecretAccessKey", "OutputValue": "any-secret-access-key"},
        ]

        # trigger
        (
            deployer_arn,
            access_key_id_arn,
            secret_access_key_arn,
        ) = preprocessor._create_deployer_at(stage=stage_mock)

        # verify
        self.assertEqual(deployer_arn, "any-deployer-arn")
        self.assertEqual(access_key_id_arn, "any-access-key-id")
        self.assertEqual(secret_access_key_arn, "any-secret-access-key")

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_missing_stage_resources_when_all_resources_are_missed(
        self, manage_cloudformation_stack_mock, click_mock
    ):
        # setup
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn=None,
            cfn_deployment_role_arn=None,
            artifacts_bucket_arn=None,
        )

        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "DeployerRole", "OutputValue": "new-deployer-role-arn"},
            {"OutputKey": "CFNDeploymentRole", "OutputValue": "new-cfn-deployment-role-arn"},
            {"OutputKey": "ArtifactsBucket", "OutputValue": "new-artifacts-bucket-arn"},
            {"OutputKey": "ArtifactsBucketKey", "OutputValue": "new-artifacts-bucket-key-arn"},
        ]

        # trigger
        (
            deployer_role_arn,
            cfn_deployment_role_arn,
            artifacts_bucket_arn,
            artifacts_bucket_key_arn,
        ) = preprocessor._create_missing_stage_resources(stage=stage, deployer_arn="any-deployer-arn")

        # verify
        self.assertEqual(deployer_role_arn, "new-deployer-role-arn")
        self.assertEqual(cfn_deployment_role_arn, "new-cfn-deployment-role-arn")
        self.assertEqual(artifacts_bucket_arn, "new-artifacts-bucket-arn")
        self.assertEqual(artifacts_bucket_key_arn, "new-artifacts-bucket-key-arn")
        manage_cloudformation_stack_mock.assert_called_once_with(
            stack_name="aws-sam-cli-managed-any-stack-name-pipeline-resources",
            region="any-region",
            profile="any-profile",
            template_body=ANY,
            parameter_overrides={
                "DeployerArn": "any-deployer-arn",
                "DeployerRoleArn": None,
                "CFNDeploymentRoleArn": None,
                "ArtifactsBucketArn": None,
            },
        )

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_missing_stage_resources_when_only_deployer_role_is_missed(
        self, manage_cloudformation_stack_mock, click_mock
    ):
        # setup
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn=None,
            cfn_deployment_role_arn="existing-cfn-deployment-role-arn",
            artifacts_bucket_arn="existing-artifacts-bucket-arn",
        )

        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "DeployerRole", "OutputValue": "new-deployer-role-arn"},
            {"OutputKey": "CFNDeploymentRole", "OutputValue": "existing-cfn-deployment-role-arn"},
            {"OutputKey": "ArtifactsBucket", "OutputValue": "existing-artifacts-bucket-arn"},
        ]

        # trigger
        (
            deployer_role_arn,
            cfn_deployment_role_arn,
            artifacts_bucket_arn,
            artifacts_bucket_key_arn,
        ) = preprocessor._create_missing_stage_resources(stage=stage, deployer_arn="any-deployer-arn")

        # verify
        self.assertEqual(deployer_role_arn, "new-deployer-role-arn")
        self.assertEqual(cfn_deployment_role_arn, "existing-cfn-deployment-role-arn")
        self.assertEqual(artifacts_bucket_arn, "existing-artifacts-bucket-arn")
        # if we didn't create the artifacts bucket then we don't know about the user's bucket encryption method
        self.assertIsNone(artifacts_bucket_key_arn)
        manage_cloudformation_stack_mock.assert_called_once_with(
            stack_name="aws-sam-cli-managed-any-stack-name-pipeline-resources",
            region="any-region",
            profile="any-profile",
            template_body=ANY,
            parameter_overrides={
                "DeployerArn": "any-deployer-arn",
                "DeployerRoleArn": None,
                "CFNDeploymentRoleArn": "existing-cfn-deployment-role-arn",
                "ArtifactsBucketArn": "existing-artifacts-bucket-arn",
            },
        )

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_missing_stage_resources_when_only_cfn_deployment_role_is_missed(
        self, manage_cloudformation_stack_mock, click_mock
    ):
        # setup
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn="existing-deployer-role-arn",
            cfn_deployment_role_arn=None,
            artifacts_bucket_arn="existing-artifacts-bucket-arn",
        )

        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "DeployerRole", "OutputValue": "existing-deployer-role-arn"},
            {"OutputKey": "CFNDeploymentRole", "OutputValue": "new-cfn-deployment-role-arn"},
            {"OutputKey": "ArtifactsBucket", "OutputValue": "existing-artifacts-bucket-arn"},
        ]

        # trigger
        (
            deployer_role_arn,
            cfn_deployment_role_arn,
            artifacts_bucket_arn,
            artifacts_bucket_key_arn,
        ) = preprocessor._create_missing_stage_resources(stage=stage, deployer_arn="any-deployer-arn")

        # verify
        self.assertEqual(deployer_role_arn, "existing-deployer-role-arn")
        self.assertEqual(cfn_deployment_role_arn, "new-cfn-deployment-role-arn")
        self.assertEqual(artifacts_bucket_arn, "existing-artifacts-bucket-arn")
        # if we didn't create the artifacts bucket then we don't know about the user's bucket encryption method
        self.assertIsNone(artifacts_bucket_key_arn)
        manage_cloudformation_stack_mock.assert_called_once_with(
            stack_name="aws-sam-cli-managed-any-stack-name-pipeline-resources",
            region="any-region",
            profile="any-profile",
            template_body=ANY,
            parameter_overrides={
                "DeployerArn": "any-deployer-arn",
                "DeployerRoleArn": "existing-deployer-role-arn",
                "CFNDeploymentRoleArn": None,
                "ArtifactsBucketArn": "existing-artifacts-bucket-arn",
            },
        )

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_missing_stage_resources_when_only_artifacts_bucket_is_missed(
        self, manage_cloudformation_stack_mock, click_mock
    ):
        # setup
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn="existing-deployer-role-arn",
            cfn_deployment_role_arn="existing-cfn-deployment-role-arn",
            artifacts_bucket_arn=None,
        )

        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "DeployerRole", "OutputValue": "existing-deployer-role-arn"},
            {"OutputKey": "CFNDeploymentRole", "OutputValue": "existing-cfn-deployment-role-arn"},
            {"OutputKey": "ArtifactsBucket", "OutputValue": "new-artifacts-bucket-arn"},
            {"OutputKey": "ArtifactsBucketKey", "OutputValue": "new-artifacts-bucket-key-arn"},
        ]

        # trigger
        (
            deployer_role_arn,
            cfn_deployment_role_arn,
            artifacts_bucket_arn,
            artifacts_bucket_key_arn,
        ) = preprocessor._create_missing_stage_resources(stage=stage, deployer_arn="any-deployer-arn")

        # verify
        self.assertEqual(deployer_role_arn, "existing-deployer-role-arn")
        self.assertEqual(cfn_deployment_role_arn, "existing-cfn-deployment-role-arn")
        self.assertEqual(artifacts_bucket_arn, "new-artifacts-bucket-arn")
        self.assertEqual(artifacts_bucket_key_arn, "new-artifacts-bucket-key-arn")
        manage_cloudformation_stack_mock.assert_called_once_with(
            stack_name="aws-sam-cli-managed-any-stack-name-pipeline-resources",
            region="any-region",
            profile="any-profile",
            template_body=ANY,
            parameter_overrides={
                "DeployerArn": "any-deployer-arn",
                "DeployerRoleArn": "existing-deployer-role-arn",
                "CFNDeploymentRoleArn": "existing-cfn-deployment-role-arn",
                "ArtifactsBucketArn": None,
            },
        )

    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.click")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_create_missing_stage_resources_when_all_resources_are_provided(
        self, manage_cloudformation_stack_mock, click_mock
    ):
        # setup
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn="existing-deployer-role-arn",
            cfn_deployment_role_arn="existing-cfn-deployment-role-arn",
            artifacts_bucket_arn="existing-artifacts-bucket-arn",
        )

        # trigger
        (
            deployer_role_arn,
            cfn_deployment_role_arn,
            artifacts_bucket_arn,
            artifacts_bucket_key_arn,
        ) = preprocessor._create_missing_stage_resources(stage=stage, deployer_arn="any-deployer-arn")

        # verify
        manage_cloudformation_stack_mock.assert_not_called()
        self.assertEqual(deployer_role_arn, "existing-deployer-role-arn")
        self.assertEqual(cfn_deployment_role_arn, "existing-cfn-deployment-role-arn")
        self.assertEqual(artifacts_bucket_arn, "existing-artifacts-bucket-arn")
        # if we didn't create the artifacts bucket then we don't know about the user's bucket encryption method
        self.assertIsNone(artifacts_bucket_key_arn)

    @patch.object(Preprocessor, "_get_build_image")
    @patch.object(Preprocessor, "_create_deployer_at")
    @patch.object(Preprocessor, "_create_missing_stage_resources")
    def test_run_creates_the_missing_deployer_at_the_testing_stage_aws_account(
        self, create_missing_stage_resources_mock, create_deployer_at_mock, get_build_image_mock
    ):
        # setup
        context_without_deployer = context.copy()
        del context_without_deployer["deployer_arn"]
        create_deployer_at_mock.return_value = ["ANY", "ANY", "ANY"]
        create_missing_stage_resources_mock.return_value = ["ANY", "ANY", "ANY", "ANY"]

        # trigger
        preprocessor.run(context=context_without_deployer)

        # verify
        create_deployer_at_mock.assert_called_once()
        _, kwargs = create_deployer_at_mock.call_args
        stage = kwargs["stage"]
        self.assertEqual(Context.TESTING_STAGE_NAME, stage.name)

    @patch.object(Preprocessor, "_get_build_image")
    @patch.object(Preprocessor, "_create_deployer_at")
    @patch.object(Preprocessor, "_create_missing_stage_resources")
    def test_run_will_not_create_deployer_if_already_provided(
        self, create_missing_stage_resources_mock, create_deployer_at_mock, get_build_image_mock
    ):
        # setup
        create_deployer_at_mock.return_value = ["ANY", "ANY", "ANY"]
        create_missing_stage_resources_mock.return_value = ["ANY", "ANY", "ANY", "ANY"]

        # trigger
        self.assertIn("deployer_arn", context)
        preprocessor.run(context=context)

        # verify
        create_deployer_at_mock.assert_not_called()

    @patch.object(Preprocessor, "_get_build_image")
    @patch.object(Preprocessor, "_create_deployer_at")
    @patch("samcli.lib.pipeline.init.plugins.two_stages_pipeline.preprocessor.manage_cloudformation_stack")
    def test_run_will_not_recreate_provided_resources(
        self, manage_cloudformation_stack_mock, create_deployer_at_mock, get_build_image_mock
    ):
        # setup
        context["prod_stack_name"] = "PROD-STACK"
        create_deployer_at_mock.return_value = ["ANY", "ANY", "ANY"]
        manage_cloudformation_stack_mock.return_value = [
            {"OutputKey": "DeployerRole", "OutputValue": "new-deployer-role-arn"},
            {"OutputKey": "CFNDeploymentRole", "OutputValue": "new-cfn-deployment-role-arn"},
            {"OutputKey": "ArtifactsBucket", "OutputValue": "new-artifacts-bucket-arn"},
            {"OutputKey": "ArtifactsBucketKey", "OutputValue": "new-artifacts-bucket-key-arn"},
        ]

        # trigger
        self.assertIn("deployer_arn", context)
        self.assertIn("testing_deployer_role", context)
        self.assertIn("testing_cfn_deployment_role", context)
        self.assertIn("testing_artifacts_bucket", context)
        self.assertNotIn("prod_deployer_role", context)
        self.assertNotIn("prod_cfn_deployment_role", context)
        self.assertNotIn("prod_artifacts_bucket", context)
        preprocessor.run(context=context)

        # verify
        create_deployer_at_mock.assert_not_called()
        manage_cloudformation_stack_mock.assert_called_once()  # for prod stage only
        _, kwargs = manage_cloudformation_stack_mock.call_args
        self.assertEqual(kwargs["stack_name"], "aws-sam-cli-managed-PROD-STACK-pipeline-resources")
        actual_parameter_overrides = kwargs["parameter_overrides"]
        expected_parameter_overrides = {
            "DeployerArn": ANY_DEPLOYER_ARN,
            "DeployerRoleArn": None,
            "CFNDeploymentRoleArn": None,
            "ArtifactsBucketArn": None,
        }
        self.assertEqual(actual_parameter_overrides, expected_parameter_overrides)

    @patch.object(Preprocessor, "_get_build_image")
    @patch.object(Preprocessor, "_create_deployer_at")
    @patch.object(Preprocessor, "_create_missing_stage_resources")
    def test_run_creates_and_mutate_new_copy_of_the_context(
        self, create_missing_stage_resources_mock, create_deployer_at_mock, get_build_image_mock
    ):
        # setup
        context = {"sam_template": ANY_SAM_TEMPLATE}
        create_missing_stage_resources_mock.return_value = ["ANY", "ANY", "ANY", "ANY"]
        create_deployer_at_mock.return_value = ["ANY", "ANY", "ANY"]

        # triggert
        mutated_context = preprocessor.run(context=context)

        # verify
        self.assertIsNot(context, mutated_context)

        self.assertNotIn(PLUGIN_NAME, context)
        self.assertNotIn("build_image", context)
        self.assertNotIn("testing_deployer_role", context)
        self.assertNotIn("testing_cfn_deployment_role", context)
        self.assertNotIn("testing_artifacts_bucket", context)
        self.assertNotIn("prod_deployer_role", context)
        self.assertNotIn("prod_cfn_deployment_role", context)
        self.assertNotIn("prod_artifacts_bucket", context)

        self.assertIn(PLUGIN_NAME, mutated_context)
        self.assertIn("build_image", mutated_context)
        self.assertIn("testing_deployer_role", mutated_context)
        self.assertIn("testing_cfn_deployment_role", mutated_context)
        self.assertIn("testing_artifacts_bucket", mutated_context)
        self.assertIn("prod_deployer_role", mutated_context)
        self.assertIn("prod_cfn_deployment_role", mutated_context)
        self.assertIn("prod_artifacts_bucket", mutated_context)
