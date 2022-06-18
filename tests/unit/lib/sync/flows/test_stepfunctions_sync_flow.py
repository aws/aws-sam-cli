from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch
from pathlib import Path
from samcli.lib.providers.provider import Stack

from samcli.lib.sync.flows.stepfunctions_sync_flow import StepFunctionsSyncFlow
from samcli.lib.sync.exceptions import InfraSyncRequiredError
from samcli.lib.providers.exceptions import MissingLocalDefinition


class TestStepFunctionsSyncFlow(TestCase):
    def setUp(self) -> None:
        get_resource_patch = patch("samcli.lib.sync.flows.stepfunctions_sync_flow.get_resource_by_id")
        self.get_resource_mock = get_resource_patch.start()
        self.get_resource_mock.return_value = {"Properties": {"DefinitionUri": "test_uri"}}
        self.addCleanup(get_resource_patch.stop)

    def create_sync_flow(self):
        patch("samcli.lib.sync.flows.stepfunctions_sync_flow.get_resource_by_id")
        sync_flow = StepFunctionsSyncFlow(
            "StateMachine1",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            physical_id_mapping={},
            stacks=[MagicMock()],
        )
        return sync_flow

    @patch("samcli.lib.sync.sync_flow.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.sync.sync_flow.Session")
    def test_set_up(self, session_mock, client_provider_mock):
        sync_flow = self.create_sync_flow()
        sync_flow.set_up()
        client_provider_mock.return_value.assert_any_call("stepfunctions")

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

    @patch("samcli.lib.sync.flows.stepfunctions_sync_flow.get_definition_path")
    def test_get_definition_file(self, get_path_mock):
        sync_flow = self.create_sync_flow()

        sync_flow._build_context.use_base_dir = False
        sync_flow._build_context.base_dir = "base_dir"
        sync_flow._resource = {"Properties": {"DefinitionUri": "test_uri"}}
        get_path_mock.return_value = Path("base_dir").joinpath("test_uri")

        result_uri = sync_flow._get_definition_file(sync_flow._state_machine_identifier)

        get_path_mock.assert_called_with(
            {"Properties": {"DefinitionUri": "test_uri"}},
            sync_flow._state_machine_identifier,
            False,
            "base_dir",
            sync_flow._stacks,
        )
        self.assertEqual(result_uri, Path("base_dir").joinpath("test_uri"))

        sync_flow._resource = {}
        result_uri = sync_flow._get_definition_file(sync_flow._state_machine_identifier)

        self.assertEqual(result_uri, None)

    @patch("samcli.lib.sync.flows.stepfunctions_sync_flow.get_definition_path")
    def test_get_definition_file_with_base_dir(self, get_path_mock):
        sync_flow = self.create_sync_flow()

        sync_flow._build_context.use_base_dir = True
        sync_flow._build_context.base_dir = "base_dir"
        sync_flow._resource = {"Properties": {"DefinitionUri": "test_uri"}}
        get_path_mock.return_value = Path("base_dir").joinpath("test_uri")

        result_uri = sync_flow._get_definition_file(sync_flow._state_machine_identifier)

        get_path_mock.assert_called_with(
            {"Properties": {"DefinitionUri": "test_uri"}},
            sync_flow._state_machine_identifier,
            True,
            "base_dir",
            sync_flow._stacks,
        )
        self.assertEqual(result_uri, Path("base_dir").joinpath("test_uri"))

    def test_process_definition_file(self):
        sync_flow = self.create_sync_flow()
        sync_flow._definition_uri = "path"
        with patch("builtins.open", mock_open(read_data='{"key": "value"}')) as mock_file:
            data = sync_flow._process_definition_file()
            self.assertEqual(data, '{"key": "value"}')

    @patch("samcli.lib.sync.sync_flow.Session")
    def test_failed_gather_resources_definition_substitution(self, session_mock):
        self.get_resource_mock.return_value = {"Properties": {"DefinitionSubstitutions": {"a": "b"}}}
        sync_flow = self.create_sync_flow()

        sync_flow.get_physical_id = MagicMock()
        sync_flow.get_physical_id.return_value = "PhysicalApi1"

        sync_flow._get_definition_file = MagicMock()
        sync_flow._get_definition_file.return_value = "file.yaml"

        sync_flow.set_up()
        sync_flow._definition_uri = None

        with patch("builtins.open", mock_open(read_data='{"key": "value"}')) as mock_file:
            with self.assertRaises(InfraSyncRequiredError):
                sync_flow.gather_resources()

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
            with self.assertRaises(MissingLocalDefinition):
                sync_flow.sync()

    def test_gather_dependencies(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow.gather_dependencies(), [])

    def test_compare_remote(self):
        sync_flow = self.create_sync_flow()
        self.assertFalse(sync_flow.compare_remote())

    def test_get_resource_api_calls(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._get_resource_api_calls(), [])

    def test_equality_keys(self):
        sync_flow = self.create_sync_flow()
        self.assertEqual(sync_flow._equality_keys(), sync_flow._state_machine_identifier)
