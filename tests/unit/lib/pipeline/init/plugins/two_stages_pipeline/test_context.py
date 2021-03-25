from unittest import TestCase
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.context import Context  # type: ignore


ANY_TESTING_PROFILE = "ANY_TESTING_PROFILE"
ANY_TESTING_REGION = "ANY_TESTING_REGION"
ANY_TESTING_STACK_NAME = "ANY_TESTING_STACK_NAME"
ANY_TESTING_DEPLOYER_ROLE = "ANY:TESTING:DEPLOYER_ROLE"
ANY_TESTING_CFN_DEPLOYMENT_ROLE = "ANY:TESTING:CFN_DEPLOYMENT_ROLE"
ANY_TESTING_ARTIFACTS_BUCKET = "ANY:TESTING:ARTIFACTS_BUCKET"
ANY_PROD_PROFILE = "ANY_PROD_PROFILE"
ANY_PROD_REGION = "ANY_PROD_REGION"
ANY_PROD_STACK_NAME = "ANY_PROD_STACK_NAME"
ANY_PROD_DEPLOYER_ROLE = "ANY:PROD:DEPLOYER_ROLE"
ANY_PROD_CFN_DEPLOYMENT_ROLE = "ANY:PROD:CFN_DEPLOYMENT_ROLE"
ANY_PROD_ARTIFACTS_BUCKET = "ANY:PROD:ARTIFACTS_BUCKET"
ANY_DEPLOYER_ARN = "ANY:DEPLOYER_ARN"
ANY_DEPLOYER_AWS_ACCESS_KEY_ID_VARIABLE_NAME = "ANY_DEPLOYER_AWS_ACCESS_KEY_ID_VARIABLE_NAME"
ANY_DEPLOYER_AWS_SECRET_ACCESS_KEY_VARIABLE_NAME = "ANY_DEPLOYER_AWS_SECRET_ACCESS_KEY_VARIABLE_NAME"

ANY_CONTEXT = {
    "testing_profile": ANY_TESTING_PROFILE,
    "testing_region": ANY_TESTING_REGION,
    "testing_stack_name": ANY_TESTING_STACK_NAME,
    "testing_deployer_role": ANY_TESTING_DEPLOYER_ROLE,
    "testing_cfn_deployment_role": ANY_TESTING_CFN_DEPLOYMENT_ROLE,
    "testing_artifacts_bucket": ANY_TESTING_ARTIFACTS_BUCKET,
    "prod_profile": ANY_PROD_PROFILE,
    "prod_region": ANY_PROD_REGION,
    "prod_stack_name": ANY_PROD_STACK_NAME,
    "prod_deployer_role": ANY_PROD_DEPLOYER_ROLE,
    "prod_cfn_deployment_role": ANY_PROD_CFN_DEPLOYMENT_ROLE,
    "prod_artifacts_bucket": ANY_PROD_ARTIFACTS_BUCKET,
    "deployer_arn": ANY_DEPLOYER_ARN,
    "deployer_aws_access_key_id_variable_name": ANY_DEPLOYER_AWS_ACCESS_KEY_ID_VARIABLE_NAME,
    "deployer_aws_secret_access_key_variable_name": ANY_DEPLOYER_AWS_SECRET_ACCESS_KEY_VARIABLE_NAME,
}


class TestContext(TestCase):
    def test_init_with_all_keys_provided(self):
        context: Context = Context(ANY_CONTEXT)
        testing_stage = context.get_stage(Context.TESTING_STAGE_NAME)
        prod_stage = context.get_stage(Context.PROD_STAGE_NAME)

        self.assertEqual(testing_stage.name, Context.TESTING_STAGE_NAME)
        self.assertEqual(testing_stage.aws_profile, ANY_TESTING_PROFILE)
        self.assertEqual(testing_stage.aws_region, ANY_TESTING_REGION)
        self.assertEqual(testing_stage.stack_name, ANY_TESTING_STACK_NAME)
        self.assertEqual(testing_stage.deployer_role.arn, ANY_TESTING_DEPLOYER_ROLE)
        self.assertEqual(testing_stage.deployer_role.name(), "DEPLOYER_ROLE")
        self.assertTrue(testing_stage.deployer_role.is_user_provided)
        self.assertEqual(testing_stage.cfn_deployment_role.arn, ANY_TESTING_CFN_DEPLOYMENT_ROLE)
        self.assertEqual(testing_stage.cfn_deployment_role.name(), "CFN_DEPLOYMENT_ROLE")
        self.assertTrue(testing_stage.cfn_deployment_role.is_user_provided)
        self.assertEqual(testing_stage.artifacts_bucket.arn, ANY_TESTING_ARTIFACTS_BUCKET)
        self.assertEqual(testing_stage.artifacts_bucket.name(), "ARTIFACTS_BUCKET")
        self.assertTrue(testing_stage.artifacts_bucket.is_user_provided)
        self.assertIsNone(testing_stage.artifacts_bucket.kms_key_arn)

        self.assertEqual(prod_stage.name, Context.PROD_STAGE_NAME)
        self.assertEqual(prod_stage.aws_profile, ANY_PROD_PROFILE)
        self.assertEqual(prod_stage.aws_region, ANY_PROD_REGION)
        self.assertEqual(prod_stage.stack_name, ANY_PROD_STACK_NAME)
        self.assertEqual(prod_stage.deployer_role.arn, ANY_PROD_DEPLOYER_ROLE)
        self.assertEqual(prod_stage.deployer_role.name(), "DEPLOYER_ROLE")
        self.assertTrue(prod_stage.deployer_role.is_user_provided)
        self.assertEqual(prod_stage.cfn_deployment_role.arn, ANY_PROD_CFN_DEPLOYMENT_ROLE)
        self.assertEqual(prod_stage.cfn_deployment_role.name(), "CFN_DEPLOYMENT_ROLE")
        self.assertTrue(prod_stage.cfn_deployment_role.is_user_provided)
        self.assertEqual(prod_stage.artifacts_bucket.arn, ANY_PROD_ARTIFACTS_BUCKET)
        self.assertEqual(prod_stage.artifacts_bucket.name(), "ARTIFACTS_BUCKET")
        self.assertTrue(prod_stage.artifacts_bucket.is_user_provided)
        self.assertIsNone(prod_stage.artifacts_bucket.kms_key_arn)

        self.assertEqual(context.deployer.arn, ANY_DEPLOYER_ARN)
        self.assertEqual(context.deployer.name(), "DEPLOYER_ARN")
        self.assertTrue(context.deployer.is_user_provided)
        self.assertIsNone(context.deployer.access_key_id)
        self.assertIsNone(context.deployer.secret_access_key)

        self.assertEqual(context.deployer_aws_access_key_id_variable_name, ANY_DEPLOYER_AWS_ACCESS_KEY_ID_VARIABLE_NAME)
        self.assertEqual(
            context.deployer_aws_secret_access_key_variable_name, ANY_DEPLOYER_AWS_SECRET_ACCESS_KEY_VARIABLE_NAME
        )
        self.assertIsNone(context.build_image)

    def test_init_with_no_keys_provided(self):
        context: Context = Context({})
        testing_stage = context.get_stage(Context.TESTING_STAGE_NAME)
        prod_stage = context.get_stage(Context.PROD_STAGE_NAME)

        self.assertEqual(testing_stage.name, Context.TESTING_STAGE_NAME)
        self.assertIsNone(testing_stage.aws_profile)
        self.assertIsNone(testing_stage.aws_region)
        self.assertIsNone(testing_stage.stack_name)
        self.assertIsNone(testing_stage.deployer_role.arn)
        self.assertIsNone(testing_stage.deployer_role.name())
        self.assertFalse(testing_stage.deployer_role.is_user_provided)
        self.assertIsNone(testing_stage.cfn_deployment_role.arn)
        self.assertIsNone(testing_stage.cfn_deployment_role.name())
        self.assertFalse(testing_stage.cfn_deployment_role.is_user_provided)
        self.assertIsNone(testing_stage.artifacts_bucket.arn)
        self.assertIsNone(testing_stage.artifacts_bucket.name())
        self.assertFalse(testing_stage.artifacts_bucket.is_user_provided)
        self.assertIsNone(testing_stage.artifacts_bucket.kms_key_arn)

        self.assertEqual(prod_stage.name, Context.PROD_STAGE_NAME)
        self.assertIsNone(prod_stage.aws_profile)
        self.assertIsNone(prod_stage.aws_region)
        self.assertIsNone(prod_stage.stack_name)
        self.assertIsNone(prod_stage.deployer_role.arn)
        self.assertIsNone(prod_stage.deployer_role.name())
        self.assertFalse(prod_stage.deployer_role.is_user_provided)
        self.assertIsNone(prod_stage.cfn_deployment_role.arn)
        self.assertIsNone(prod_stage.cfn_deployment_role.name())
        self.assertFalse(prod_stage.cfn_deployment_role.is_user_provided)
        self.assertIsNone(prod_stage.artifacts_bucket.arn)
        self.assertIsNone(prod_stage.artifacts_bucket.name())
        self.assertFalse(prod_stage.artifacts_bucket.is_user_provided)
        self.assertIsNone(prod_stage.artifacts_bucket.kms_key_arn)

        self.assertIsNone(context.deployer.arn)
        self.assertIsNone(context.deployer.name())
        self.assertFalse(context.deployer.is_user_provided)
        self.assertIsNone(context.deployer.access_key_id)
        self.assertIsNone(context.deployer.secret_access_key)

        self.assertIsNone(context.deployer_aws_access_key_id_variable_name)
        self.assertIsNone(context.deployer_aws_secret_access_key_variable_name)
        self.assertIsNone(context.build_image)

    def test_init_with_none_context_raises_exception(self):
        with self.assertRaises(AttributeError):
            context: Context = Context(None)

    def test_get_stage(self):
        context: Context = Context({})
        testing_stage = context.get_stage(Context.TESTING_STAGE_NAME)
        prod_stage = context.get_stage(Context.PROD_STAGE_NAME)
        none_stage1 = context.get_stage("non-existing-stage")
        none_stage2 = context.get_stage(None)
        self.assertEqual(testing_stage.name, Context.TESTING_STAGE_NAME)
        self.assertEqual(prod_stage.name, Context.PROD_STAGE_NAME)
        self.assertIsNone(none_stage1)
        self.assertIsNone(none_stage2)

    def test_deployer_permissions(self):
        context: Context = Context(ANY_CONTEXT)
        permissions: str = context.deployer_permissions()
        # assert the deployer has assume-rule access to the deployer roles
        self.assertIn("sts:AssumeRole", permissions)
        self.assertIn(ANY_TESTING_DEPLOYER_ROLE, permissions)
        self.assertIn(ANY_PROD_DEPLOYER_ROLE, permissions)

    def test_deployer_permissions_with_empty_context(self):
        context: Context = Context({})
        permissions: str = context.deployer_permissions()
        self.assertIn("sts:AssumeRole", permissions)
        self.assertNotIn(ANY_TESTING_DEPLOYER_ROLE, permissions)
        self.assertNotIn(ANY_PROD_DEPLOYER_ROLE, permissions)
