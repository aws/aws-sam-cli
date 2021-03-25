from unittest import TestCase
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.stage import Stage  # type: ignore


class TestStage(TestCase):
    def test_init_stage(self):
        stage = Stage(
            name="any-name",
            aws_profile="any-profile",
            aws_region="any-region",
            stack_name="any-stack-name",
            deployer_role_arn="any-deployer-role-arn",
            cfn_deployment_role_arn=None,
            artifacts_bucket_arn=None,
        )
        self.assertEqual(stage.name, "any-name")
        self.assertEqual(stage.aws_profile, "any-profile")
        self.assertEqual(stage.aws_region, "any-region")
        self.assertEqual(stage.stack_name, "any-stack-name")
        self.assertEqual(stage.deployer_role.arn, "any-deployer-role-arn")
        self.assertTrue(stage.deployer_role.is_user_provided)
        self.assertIsNone(stage.cfn_deployment_role.arn)
        self.assertFalse(stage.cfn_deployment_role.is_user_provided)
        self.assertIsNone(stage.artifacts_bucket.arn)
        self.assertFalse(stage.artifacts_bucket.is_user_provided)

    def test_did_user_provide_all_required_resources(self):
        stage = Stage(
            name="any",
            aws_profile="any",
            aws_region="any",
            stack_name="any",
            deployer_role_arn=None,
            cfn_deployment_role_arn=None,
            artifacts_bucket_arn=None,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())

        stage = Stage(
            name="any",
            aws_profile="any",
            aws_region="any",
            stack_name="any",
            deployer_role_arn="any-deployer-role-arn",
            cfn_deployment_role_arn=None,
            artifacts_bucket_arn=None,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())

        stage = Stage(
            name="any",
            aws_profile="any",
            aws_region="any",
            stack_name="any",
            deployer_role_arn="any-deployer-role-arn",
            cfn_deployment_role_arn="any-cfn-deployment-role-arn",
            artifacts_bucket_arn=None,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())

        stage = Stage(
            name="any",
            aws_profile="any",
            aws_region="any",
            stack_name="any",
            deployer_role_arn="any-deployer-role-arn",
            cfn_deployment_role_arn="any-cfn-deployment-role-arn",
            artifacts_bucket_arn="any-artifacts-bucket-arn",
        )
        self.assertTrue(stage.did_user_provide_all_required_resources())
