from unittest import TestCase
from unittest.mock import Mock
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.config import PLUGIN_NAME  # type: ignore
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.context import Context as PluginContext  # type: ignore
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.postprocessor import Postprocessor  # type: ignore
from .test_context import (
    ANY_DEPLOYER_ARN,
    ANY_TESTING_DEPLOYER_ROLE,
    ANY_TESTING_CFN_DEPLOYMENT_ROLE,
    ANY_TESTING_ARTIFACTS_BUCKET,
    ANY_PROD_DEPLOYER_ROLE,
    ANY_PROD_CFN_DEPLOYMENT_ROLE,
    ANY_PROD_ARTIFACTS_BUCKET,
)


class TestPostprocessor(TestCase):
    def test_the_postprocessoer_correctly_categorize_the_resources_into_reused_and_created_resources(self):
        # setup
        deployer = Mock()
        deployer.is_user_provided = False
        deployer.arn = ANY_DEPLOYER_ARN

        testing_deployer_role = Mock()
        testing_deployer_role.is_user_provided = True
        testing_deployer_role.arn = ANY_TESTING_DEPLOYER_ROLE

        testing_cfn_deployment_role = Mock()
        testing_cfn_deployment_role.is_user_provided = True
        testing_cfn_deployment_role.arn = ANY_TESTING_CFN_DEPLOYMENT_ROLE

        testing_artifacts_bucket = Mock()
        testing_artifacts_bucket.is_user_provided = True
        testing_artifacts_bucket.arn = ANY_TESTING_ARTIFACTS_BUCKET

        testing_stage = Mock()
        testing_stage.deployer_role = testing_deployer_role
        testing_stage.cfn_deployment_role = testing_cfn_deployment_role
        testing_stage.artifacts_bucket = testing_artifacts_bucket

        prod_deployer_role = Mock()
        prod_deployer_role.is_user_provided = False
        prod_deployer_role.arn = ANY_PROD_DEPLOYER_ROLE

        prod_cfn_deployment_role = Mock()
        prod_cfn_deployment_role.is_user_provided = False
        prod_cfn_deployment_role.arn = ANY_PROD_CFN_DEPLOYMENT_ROLE

        prod_artifacts_bucket = Mock()
        prod_artifacts_bucket.is_user_provided = False
        prod_artifacts_bucket.arn = ANY_PROD_ARTIFACTS_BUCKET

        prod_stage = Mock()
        prod_stage.deployer_role = prod_deployer_role
        prod_stage.cfn_deployment_role = prod_cfn_deployment_role
        prod_stage.artifacts_bucket = prod_artifacts_bucket

        plugin_context = Mock()
        plugin_context.deployer = deployer
        plugin_context.stages = [testing_stage, prod_stage]

        context = {PLUGIN_NAME: plugin_context}
        postprocessor = Postprocessor()

        self.assertEqual(0, len(postprocessor.resources_reused))
        self.assertEqual(0, len(postprocessor.resources_created))

        # trigger
        mutated_context = postprocessor.run(context=context)

        # verify
        reused_resources_arns = list(map(lambda r: r["arn"], postprocessor.resources_reused))
        self.assertEqual(3, len(reused_resources_arns))
        self.assertIn(ANY_TESTING_DEPLOYER_ROLE, reused_resources_arns)
        self.assertIn(ANY_TESTING_CFN_DEPLOYMENT_ROLE, reused_resources_arns)
        self.assertIn(ANY_TESTING_ARTIFACTS_BUCKET, reused_resources_arns)

        created_resources_arns = list(map(lambda r: r["arn"], postprocessor.resources_created))
        self.assertEqual(4, len(created_resources_arns))
        self.assertIn(ANY_DEPLOYER_ARN, created_resources_arns)
        self.assertIn(ANY_PROD_DEPLOYER_ROLE, created_resources_arns)
        self.assertIn(ANY_PROD_CFN_DEPLOYMENT_ROLE, created_resources_arns)
        self.assertIn(ANY_PROD_ARTIFACTS_BUCKET, created_resources_arns)

    def test_the_plugin_context_is_required(self):
        postprocessor: Postprocessor = Postprocessor()
        with (self.assertRaises(KeyError)):
            postprocessor.run(context={})

    def test_the_postprocessoer_return_a_new_copy_of_the_context_without_modifications(self):
        # setup
        plugin_context = PluginContext({})
        context = {PLUGIN_NAME: plugin_context}
        postprocessor: Postprocessor = Postprocessor()

        # trigger
        mutated_context = postprocessor.run(context=context)

        # verify
        self.assertIsNot(context, mutated_context)
        self.assertEqual(context, mutated_context)
