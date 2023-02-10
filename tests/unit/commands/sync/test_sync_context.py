from pathlib import Path
from unittest import TestCase, mock
from unittest.mock import mock_open, call, patch, Mock, MagicMock

import tomlkit
from parameterized import parameterized, parameterized_class

from samcli.commands.sync.sync_context import (
    SyncState,
    ResourceSyncState,
    datetime,
    _sync_state_to_toml_document,
    HASH,
    SYNC_TIME,
    SYNC_STATE,
    DEPENDENCY_LAYER,
    RESOURCE_SYNC_STATES,
    _toml_document_to_sync_state,
    SyncContext,
)
from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR

MOCK_TIME = datetime(2023, 2, 8, 12, 12, 12)


class TestSyncState(TestCase):
    @parameterized.expand(
        [
            (True, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME)}),
            (False, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME)}),
            (True, {"Parent/Child/MockResourceId": ResourceSyncState("nested-mock-hash", MOCK_TIME)}),
            (
                False,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("nested-mock-hash", MOCK_TIME),
                },
            ),
        ]
    )
    def test_sync_state(self, dependency_layer, resource_sync_states):
        sync_state = SyncState(dependency_layer=dependency_layer, resource_sync_states=resource_sync_states)
        self.assertEqual(sync_state.dependency_layer, dependency_layer)
        self.assertEqual(sync_state.resource_sync_states, resource_sync_states)

    @parameterized.expand(
        [
            (True, "MockResourceId", "mock-hash"),
            (False, "Parent/Child/MockResourceId", "mock-nested-hash"),
        ]
    )
    def test_sync_state_update_resource_sync_state(self, dependency_layer, resource_id, resource_hash):
        sync_state = SyncState(dependency_layer=dependency_layer, resource_sync_states={})
        self.assertEqual(sync_state.dependency_layer, dependency_layer)
        self.assertEqual(sync_state.resource_sync_states, {})

        sync_state.update_resource_sync_state(resource_id, resource_hash)
        self.assertEqual(sync_state.resource_sync_states[resource_id].hash_value, resource_hash)


class TestResourceSyncState(TestCase):
    @parameterized.expand(
        [
            ("mockhash", MOCK_TIME),
        ]
    )
    def test_sync_state(self, hash_str, sync_time):
        sync_state = ResourceSyncState(hash_value=hash_str, sync_time=sync_time)
        self.assertEqual(sync_state.hash_value, hash_str)
        self.assertEqual(sync_state.sync_time, sync_time)


TOML_TEMPLATE = """
[sync_state]
dependency_layer = {dependency_layer}

[resource_sync_states]
"""

RESOURCE_SYNC_STATE_TEMPLATE = """
[resource_sync_states.{resource_id_toml}]
hash = "{resource_hash}"
sync_time = "{resource_sync_time}"
"""


class TestSyncStateToTomlSerde(TestCase):
    @parameterized.expand(
        [
            (True, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME)}),
            (True, {"Parent/Child/MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME)}),
            (
                False,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME),
                },
            ),
        ]
    )
    def test_sync_state_to_toml(self, dependency_layer, resource_sync_states):
        sync_state = SyncState(dependency_layer, resource_sync_states)

        toml_document = _sync_state_to_toml_document(sync_state)
        self.assertIsNotNone(toml_document)

        sync_state_toml_table = toml_document.get(SYNC_STATE)
        self.assertIsNotNone(sync_state_toml_table)

        dependency_layer_toml_field = sync_state_toml_table.get(DEPENDENCY_LAYER)
        self.assertEqual(dependency_layer_toml_field, dependency_layer)

        resource_sync_states_toml_field = toml_document.get(RESOURCE_SYNC_STATES)
        self.assertIsNotNone(resource_sync_states_toml_field)

        for resource_id in resource_sync_states_toml_field:
            resource_sync_state_toml_table = resource_sync_states_toml_field.get(resource_id)
            resource_sync_state_resource_id = resource_id.replace("-", "/")

            self.assertEqual(
                resource_sync_states[resource_sync_state_resource_id].hash_value,
                resource_sync_state_toml_table.get(HASH),
            )
            self.assertEqual(
                resource_sync_states[resource_sync_state_resource_id].sync_time.isoformat(),
                resource_sync_state_toml_table.get(SYNC_TIME),
            )

    @parameterized.expand(
        [
            (True, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME)}),
            (
                False,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("mock-nested-hash", MOCK_TIME),
                },
            ),
        ]
    )
    def test_toml_to_sync_state(self, dependency_layer, resource_sync_states):
        toml_template_str = TOML_TEMPLATE.format(dependency_layer=str(dependency_layer).lower())
        for resource_id in resource_sync_states:
            resource_sync_state = resource_sync_states.get(resource_id)
            resource_id_toml = resource_id.replace("/", "-")

            resource_sync_state_template = RESOURCE_SYNC_STATE_TEMPLATE.format(
                resource_id_toml=resource_id_toml,
                resource_hash=resource_sync_state.hash_value,
                resource_sync_time=resource_sync_state.sync_time.isoformat(),
            )

            toml_template_str += resource_sync_state_template

        toml_doc = tomlkit.loads(toml_template_str)
        sync_state = _toml_document_to_sync_state(toml_doc)
        self.assertEqual(sync_state.dependency_layer, dependency_layer)
        self.assertEqual(sync_state.resource_sync_states, resource_sync_states)

    def test_none_toml_doc_should_return_none(self):
        self.assertIsNone(_toml_document_to_sync_state(None))

    def test_none_toml_table_should_return_none(self):
        self.assertIsNone(_toml_document_to_sync_state(tomlkit.document()))


@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncContext(TestCase):

    dependency_layer: bool

    def setUp(self) -> None:
        self.build_dir = "build_dir"
        self.cache_dir = "cache_dir"
        self.sync_context = SyncContext(self.dependency_layer, self.build_dir, self.cache_dir)

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.commands.sync.sync_context.rmtree_if_exists")
    def test_sync_context_dependency_layer(self, previous_dependency_layer_value, patched_rmtree_if_exists):
        previous_session_state = TOML_TEMPLATE.format(dependency_layer=str(previous_dependency_layer_value).lower())
        with mock.patch("builtins.open", mock_open(read_data=previous_session_state)) as mock_file:
            with self.sync_context:
                pass

            mock_file.assert_has_calls(
                [call().write(tomlkit.dumps(_sync_state_to_toml_document(self.sync_context._current_state)))]
            )

            if previous_dependency_layer_value != self.dependency_layer:
                patched_rmtree_if_exists.assert_has_calls(
                    [
                        call(self.sync_context._build_dir),
                        call(self.sync_context._cache_dir),
                        call(Path(DEFAULT_DEPENDENCIES_DIR)),
                    ]
                )

    @parameterized.expand(
        [(True, "MockResourceId", "mock-hash"), (False, "Parent/Child/MockResourceId", "nested-mock-hash")]
    )
    def test_sync_context_resource_sync_state_methods(
        self, previous_dependency_layer_value, resource_id, resource_hash
    ):
        previous_session_state = TOML_TEMPLATE.format(dependency_layer=str(previous_dependency_layer_value).lower())
        with mock.patch("builtins.open", mock_open(read_data=previous_session_state)) as mock_file:
            with self.sync_context as sync_context:
                self.assertIsNone(sync_context.get_resource_latest_sync_hash(resource_id))
                sync_context.update_resource_sync_state(resource_id, resource_hash)
                self.assertEqual(sync_context.get_resource_latest_sync_hash(resource_id), resource_hash)

    @patch("samcli.commands.sync.sync_context.rmtree_if_exists")
    def test_sync_context_has_no_previous_state_if_file_doesnt_exist(self, patched_rmtree_if_exists):
        with mock.patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = [OSError("File does not exist"), MagicMock()]
            with self.sync_context:
                pass
            self.assertIsNone(self.sync_context._previous_state)
            self.assertIsNotNone(self.sync_context._current_state)
            patched_rmtree_if_exists.assert_not_called()
