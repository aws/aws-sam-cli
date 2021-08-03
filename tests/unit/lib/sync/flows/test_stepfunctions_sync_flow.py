from unittest import TestCase
from unittest.mock import ANY, MagicMock, mock_open, patch

from samcli.lib.sync.flows.stepfunctions_sync_flow import StepFunctionsSyncFlow
from samcli.lib.sync.exceptions import UriNotFoundException


class TestStepFunctionsSyncFlow(TestCase):
    def create_sync_flow(self):
        sync_flow = StepFunctionsSyncFlow(
            "StateMachine1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        sync_flow._get_resource_api_calls = MagicMock()
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        session_mock.return_value.client.assert_any_call("stepfunctions")

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_sync_direct(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalId1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        with patch("builtins.open", mock_open(read_data='{"key": "value"}')) as mock_file:
            sync_flow.gather_resources()

        sync_flow._stepfunctions_client.update_state_machine.return_value = {"Response": "success"}

        sync_flow.sync()

        sync_flow._stepfunctions_client.update_state_machine.assert_called_once_with(
            stateMachineArn="PhysicalId1", definition='{"key": "value"}'
        )

    @patch("samcli.lib.sync.flows.stepfunctions_sync_flow.get_resource_by_id")
    def test_get_definition_file(self, get_resource_mock):
        sync_flow = self.create_sync_flow()

        get_resource_mock.return_value = {"Properties": {"DefinitionUri": "test_uri"}}
        result_uri = sync_flow._get_definition_file("test")

        self.assertEqual(result_uri, "test_uri")

        get_resource_mock.return_value = {"Properties": {}}
        result_uri = sync_flow._get_definition_file("test")

        self.assertEqual(result_uri, None)

    def test_process_definition_file(self):
        sync_flow = self.create_sync_flow()
        sync_flow._definition_uri = "path"
        with patch("builtins.open", mock_open(read_data='{"key": "value"}')) as mock_file:
            data = sync_flow._process_definition_file()
            self.assertEqual(data, '{"key": "value"}')

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_failed_gather_resources(self, session_mock):
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        sync_flow._definition_uri = None

        with patch("builtins.open", mock_open(read_data='{"key": "value"}')) as mock_file:
            with self.assertRaises(UriNotFoundException):
                sync_flow.sync()
