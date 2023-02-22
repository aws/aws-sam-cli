from unittest import TestCase
from unittest.mock import MagicMock, patch
from samcli.lib.sync.infra_sync_executor import InfraSyncExecutor
from botocore.exceptions import ClientError
from parameterized import parameterized


class TestInfraSyncExecutor(TestCase):
    def setUp(self):
        self.template_dict = {
            "Resources": {
                "ServerlessFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "local/"}}
            }
        }
        self.build_context = MagicMock()
        self.package_context = MagicMock()
        self.deploy_context = MagicMock()

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.sync.infra_sync_executor.InfraSyncExecutor._compare_templates")
    @patch("samcli.lib.sync.infra_sync_executor.Session")
    def test_execute_infra_sync(self, compare_templates, session_mock, compare_templates_mock):

        infra_sync_executor = InfraSyncExecutor(self.build_context, self.package_context, self.deploy_context)
        compare_templates_mock.return_value = compare_templates

        executed = infra_sync_executor.execute_infra_sync()

        self.build_context.set_up.assert_called_once()
        self.build_context.run.assert_called_once()

        if not compare_templates:
            self.package_context.run.assert_called_once()
            self.deploy_context.run.assert_called_once()

        self.assertEqual(executed, not compare_templates)
