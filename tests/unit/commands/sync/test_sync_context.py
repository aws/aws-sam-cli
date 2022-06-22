from pathlib import Path
from unittest import TestCase, mock
from unittest.mock import mock_open, call, patch, Mock, MagicMock

import tomlkit
from parameterized import parameterized, parameterized_class

from samcli.commands.sync.sync_context import (
    SyncState,
    _sync_state_to_toml_document,
    SYNC_STATE,
    DEPENDENCY_LAYER,
    _toml_document_to_sync_state,
    SyncContext,
)
from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR


class TestSyncState(TestCase):
    @parameterized.expand([(True,), (False,)])
    def test_sync_state(self, dependency_layer):
        sync_state = SyncState(dependency_layer)
        self.assertEqual(sync_state.dependency_layer, dependency_layer)


TOML_TEMPLATE = """
[sync_state]
dependency_layer = {dependency_layer}"""


class TestSyncStateToTomlSerde(TestCase):
    @parameterized.expand([(True,), (False,)])
    def test_sync_state_to_toml(self, dependency_layer):
        sync_state = SyncState(dependency_layer)

        toml_document = _sync_state_to_toml_document(sync_state)
        self.assertIsNotNone(toml_document)

        sync_state_toml_table = toml_document.get(SYNC_STATE)
        self.assertIsNotNone(sync_state_toml_table)

        dependency_layer_toml_field = sync_state_toml_table.get(DEPENDENCY_LAYER)
        self.assertEqual(dependency_layer_toml_field, dependency_layer)

    @parameterized.expand([(True,), (False,)])
    def test_toml_to_sync_state(self, dependency_layer):
        toml_doc = tomlkit.loads(TOML_TEMPLATE.format(dependency_layer=str(dependency_layer).lower()))

        sync_state = _toml_document_to_sync_state(toml_doc)
        self.assertEqual(sync_state.dependency_layer, dependency_layer)

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

    @patch("samcli.commands.sync.sync_context.rmtree_if_exists")
    def test_sync_context_has_no_previous_state_if_file_doesnt_exist(self, patched_rmtree_if_exists):
        with mock.patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = [OSError("File does not exist"), MagicMock()]
            with self.sync_context:
                pass
            self.assertIsNone(self.sync_context._previous_state)
            self.assertIsNotNone(self.sync_context._current_state)
            patched_rmtree_if_exists.assert_not_called()
