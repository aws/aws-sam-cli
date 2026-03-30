from pathlib import Path
from unittest import TestCase, mock
from unittest.mock import mock_open, call, patch, Mock, MagicMock

import tomlkit
from parameterized import parameterized, parameterized_class

from samcli.commands.sync.sync_context import (
    SyncState,
    ResourceSyncState,
    datetime,
    timezone,
    _sync_state_to_toml_document,
    HASH,
    SYNC_TIME,
    SYNC_STATE,
    DEPENDENCY_LAYER,
    RESOURCE_SYNC_STATES,
    LATEST_INFRA_SYNC_TIME,
    _toml_document_to_sync_state,
    SyncContext,
)
from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR

MOCK_RESOURCE_SYNC_TIME = datetime(2023, 2, 8, 12, 12, 12, tzinfo=timezone.utc)
MOCK_INFRA_SYNC_TIME = datetime.now(timezone.utc)


class TestSyncState(TestCase):
    @parameterized.expand(
        [
            (True, MOCK_INFRA_SYNC_TIME, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME)}),
            (False, None, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME)}),
            (
                True,
                None,
                {"Parent/Child/MockResourceId": ResourceSyncState("nested-mock-hash", MOCK_RESOURCE_SYNC_TIME)},
            ),
            (
                False,
                MOCK_INFRA_SYNC_TIME,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("nested-mock-hash", MOCK_RESOURCE_SYNC_TIME),
                },
            ),
        ]
    )
    def test_sync_state(self, dependency_layer, latest_infra_sync_time, resource_sync_states):
        sync_state = SyncState(
            dependency_layer=dependency_layer,
            latest_infra_sync_time=latest_infra_sync_time,
            resource_sync_states=resource_sync_states,
        )
        self.assertEqual(sync_state.dependency_layer, dependency_layer)
        self.assertEqual(sync_state.latest_infra_sync_time, latest_infra_sync_time)
        self.assertEqual(sync_state.resource_sync_states, resource_sync_states)

    @parameterized.expand(
        [
            (True, "MockResourceId", "mock-hash"),
            (False, "Parent/Child/MockResourceId", "mock-nested-hash"),
        ]
    )
    @mock.patch("samcli.commands.sync.sync_context.datetime")
    def test_sync_state_update_sync_state_methods(self, dependency_layer, resource_id, resource_hash, datetime_mock):
        datetime_mock.now.return_value = MOCK_INFRA_SYNC_TIME
        sync_state = SyncState(dependency_layer=dependency_layer, latest_infra_sync_time=None, resource_sync_states={})
        self.assertEqual(sync_state.dependency_layer, dependency_layer)
        self.assertEqual(sync_state.latest_infra_sync_time, None)
        self.assertEqual(sync_state.resource_sync_states, {})

        sync_state.update_resource_sync_state(resource_id, resource_hash)
        self.assertEqual(sync_state.resource_sync_states[resource_id].hash_value, resource_hash)
        self.assertEqual(sync_state.resource_sync_states[resource_id].sync_time, MOCK_INFRA_SYNC_TIME)

        sync_state.update_infra_sync_time()
        self.assertEqual(sync_state.latest_infra_sync_time, MOCK_INFRA_SYNC_TIME)


class TestResourceSyncState(TestCase):
    @parameterized.expand(
        [
            ("mockhash", MOCK_RESOURCE_SYNC_TIME),
        ]
    )
    def test_sync_state(self, hash_str, sync_time):
        sync_state = ResourceSyncState(hash_value=hash_str, sync_time=sync_time)
        self.assertEqual(sync_state.hash_value, hash_str)
        self.assertEqual(sync_state.sync_time, sync_time)


TOML_TEMPLATE = """
[sync_state]
dependency_layer = {dependency_layer}
latest_infra_sync_time = {latest_infra_sync_time}

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
            (True, MOCK_INFRA_SYNC_TIME, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME)}),
            (
                True,
                MOCK_INFRA_SYNC_TIME,
                {"Parent/Child/MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME)},
            ),
            (
                False,
                MOCK_INFRA_SYNC_TIME,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME),
                },
            ),
        ]
    )
    def test_sync_state_to_toml(self, dependency_layer, latest_infra_sync_time, resource_sync_states):
        sync_state = SyncState(
            dependency_layer=dependency_layer,
            latest_infra_sync_time=latest_infra_sync_time,
            resource_sync_states=resource_sync_states,
        )

        toml_document = _sync_state_to_toml_document(sync_state)
        self.assertIsNotNone(toml_document)

        sync_state_toml_table = toml_document.get(SYNC_STATE)
        self.assertIsNotNone(sync_state_toml_table)

        dependency_layer_toml_field = sync_state_toml_table.get(DEPENDENCY_LAYER)
        self.assertEqual(dependency_layer_toml_field, dependency_layer)

        latest_infra_sync_time_toml_field = sync_state_toml_table.get(LATEST_INFRA_SYNC_TIME)
        self.assertEqual(latest_infra_sync_time_toml_field, latest_infra_sync_time.timestamp())

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
                resource_sync_states[resource_sync_state_resource_id].sync_time.timestamp(),
                resource_sync_state_toml_table.get(SYNC_TIME),
            )

    @parameterized.expand(
        [
            (True, {"MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME)}),
            (
                False,
                {
                    "MockResourceId": ResourceSyncState("mock-hash", MOCK_RESOURCE_SYNC_TIME),
                    "Parent/Child/MockResourceId": ResourceSyncState("mock-nested-hash", MOCK_RESOURCE_SYNC_TIME),
                },
            ),
        ]
    )
    def test_toml_to_sync_state(self, dependency_layer, resource_sync_states):
        toml_template_str = TOML_TEMPLATE.format(
            dependency_layer=str(dependency_layer).lower(), latest_infra_sync_time=MOCK_INFRA_SYNC_TIME.isoformat()
        )
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
        self.assertEqual(sync_state.latest_infra_sync_time, MOCK_INFRA_SYNC_TIME)
        self.assertEqual(sync_state.resource_sync_states, resource_sync_states)

    def test_none_toml_doc_should_return_none(self):
        self.assertIsNone(_toml_document_to_sync_state(None))

    def test_none_toml_table_should_return_none(self):
        self.assertIsNone(_toml_document_to_sync_state(tomlkit.document()))


@parameterized_class(
    [
        {"dependency_layer": True, "skip_deploy_sync": True},
        {"dependency_layer": False, "skip_deploy_sync": False},
    ]
)
class TestSyncContext(TestCase):
    dependency_layer: bool
    skip_deploy_sync: bool

    def setUp(self) -> None:
        self.build_dir = "build_dir"
        self.cache_dir = "cache_dir"
        self.sync_context = SyncContext(self.dependency_layer, self.build_dir, self.cache_dir, self.skip_deploy_sync)

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.commands.sync.sync_context.rmtree_if_exists")
    def test_sync_context_dependency_layer(self, previous_dependency_layer_value, patched_rmtree_if_exists):
        previous_session_state = TOML_TEMPLATE.format(
            dependency_layer=str(previous_dependency_layer_value).lower(),
            latest_infra_sync_time=MOCK_INFRA_SYNC_TIME.isoformat(),
        )
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
        previous_session_state = TOML_TEMPLATE.format(
            dependency_layer=str(previous_dependency_layer_value).lower(),
            latest_infra_sync_time=MOCK_INFRA_SYNC_TIME.isoformat(),
        )
        with mock.patch("builtins.open", mock_open(read_data=previous_session_state)) as mock_file:
            with self.sync_context as sync_context:
                self.assertIsNone(sync_context.get_resource_latest_sync_hash(resource_id))
                sync_context.update_resource_sync_state(resource_id, resource_hash)
                self.assertEqual(sync_context.get_resource_latest_sync_hash(resource_id), resource_hash)
                self.assertEqual(sync_context.get_latest_infra_sync_time(), MOCK_INFRA_SYNC_TIME)

    @parameterized.expand(
        [(True, "MockResourceId", "mock-hash"), (False, "Parent/Child/MockResourceId", "nested-mock-hash")]
    )
    @mock.patch("samcli.commands.sync.sync_context.datetime")
    def test_sync_context_update_infra_sync_state_methods(
        self, previous_dependency_layer_value, resource_id, resource_hash, datetime_mock
    ):
        datetime_mock.now.return_value = MOCK_INFRA_SYNC_TIME
        template = """
        [sync_state]
        dependency_layer = {dependency_layer}
        """
        previous_session_state = template.format(dependency_layer=str(previous_dependency_layer_value).lower())
        with mock.patch("builtins.open", mock_open(read_data=previous_session_state)) as mock_file:
            with self.sync_context as sync_context:
                self.assertIsNone(sync_context.get_resource_latest_sync_hash(resource_id))
                sync_context.update_resource_sync_state(resource_id, resource_hash)
                self.assertEqual(sync_context.get_resource_latest_sync_hash(resource_id), resource_hash)

                self.assertIsNone(sync_context.get_latest_infra_sync_time())
                sync_context.update_infra_sync_time()
                self.assertEqual(sync_context.get_latest_infra_sync_time(), MOCK_INFRA_SYNC_TIME)

    @patch("samcli.commands.sync.sync_context.rmtree_if_exists")
    def test_sync_context_has_no_previous_state_if_file_doesnt_exist(self, patched_rmtree_if_exists):
        with mock.patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = [OSError("File does not exist"), MagicMock()]
            with self.sync_context:
                pass
            self.assertIsNone(self.sync_context._previous_state)
            self.assertIsNotNone(self.sync_context._current_state)
            patched_rmtree_if_exists.assert_not_called()


class TestTimestampParsing(TestCase):
    """Tests for timestamp parsing with various formats and error handling"""

    @parameterized.expand(
        [
            # Valid timestamp formats
            (
                "timezone_naive",
                "2025-12-03T22:10:11.916279",
                {"Resource1": ("hash1", "2025-12-03T22:10:35.345701")},
                True,
                ["Resource1"],
                [],
            ),
            (
                "timezone_aware",
                "2025-12-03T22:10:11.916279+00:00",
                {"Resource1": ("hash1", "2025-12-03T22:10:35.345701+00:00")},
                True,
                ["Resource1"],
                [],
            ),
            (
                "z_suffix",
                "2024-05-08T15:16:43Z",
                {"Resource1": ("hash1", "2024-05-08T15:16:43Z")},
                True,
                ["Resource1"],
                [],
            ),
            ("epoch_format", 1733267411.916279, {"Resource1": ("hash1", 1733267435.345701)}, True, ["Resource1"], []),
            (
                "mixed_formats",
                "2024-05-08T15:16:43Z",
                {"Resource1": ("hash1", "2025-12-03T22:10:35+00:00"), "Resource2": ("hash2", 1733267440.123456)},
                True,
                ["Resource1", "Resource2"],
                [],
            ),
            (
                "nested_resource",
                "2024-05-08T15:16:43Z",
                {"Parent/Child/Resource": ("hash", "2024-05-08T15:16:43Z")},
                True,
                ["Parent/Child/Resource"],
                [],
            ),
            # Invalid timestamp formats
            (
                "invalid_resource",
                1733267411.916279,
                {"Valid": ("hash1", 1733267435.345701), "Invalid": ("hash2", "bad-timestamp")},
                True,
                ["Valid"],
                ["Invalid"],
            ),
            ("invalid_infra", "not-timestamp", {"Valid": ("hash1", 1733267435.345701)}, False, ["Valid"], []),
            (
                "multiple_invalid",
                1733267411.916279,
                {
                    "Valid1": ("h1", 1733267435.345701),
                    "Invalid1": ("h2", "bad1"),
                    "Valid2": ("h3", 1733267440.123456),
                    "Invalid2": ("h4", "bad2"),
                },
                True,
                ["Valid1", "Valid2"],
                ["Invalid1", "Invalid2"],
            ),
            ("all_invalid", "bad-infra", {"Invalid": ("hash", "bad-resource")}, False, [], ["Invalid"]),
        ]
    )
    def test_timestamp_parsing(
        self, test_name, infra_sync_time, resources, has_valid_infra, expected_resources, missing_resources
    ):
        """Test timestamp parsing for various formats and error handling"""
        # Build TOML string
        if isinstance(infra_sync_time, str):
            infra_value = f'"{infra_sync_time}"'
        else:
            infra_value = str(infra_sync_time)

        toml_str = f"""
[sync_state]
dependency_layer = true
latest_infra_sync_time = {infra_value}

[resource_sync_states]
"""
        for resource_id, (resource_hash, resource_sync_time) in resources.items():
            if isinstance(resource_sync_time, str):
                sync_time_value = f'"{resource_sync_time}"'
            else:
                sync_time_value = str(resource_sync_time)

            resource_id_toml = resource_id.replace("/", "-")
            toml_str += f"""
[resource_sync_states.{resource_id_toml}]
hash = "{resource_hash}"
sync_time = {sync_time_value}
"""

        toml_doc = tomlkit.loads(toml_str)

        # Mock logger if we expect invalid timestamps
        if missing_resources or not has_valid_infra:
            with patch("samcli.commands.sync.sync_context.LOG") as mock_log:
                sync_state = _toml_document_to_sync_state(toml_doc)
                mock_log.warning.assert_called()
        else:
            sync_state = _toml_document_to_sync_state(toml_doc)

        # Verify infra sync time
        if has_valid_infra:
            self.assertIsNotNone(sync_state.latest_infra_sync_time)
            self.assertEqual(sync_state.latest_infra_sync_time.tzinfo, timezone.utc)
            # Verify datetime comparison works
            time_diff = datetime.now(timezone.utc) - sync_state.latest_infra_sync_time
            self.assertIsNotNone(time_diff)
        else:
            self.assertIsNone(sync_state.latest_infra_sync_time)

        # Verify expected resources were loaded with correct timezone
        for resource_id in expected_resources:
            self.assertIn(resource_id, sync_state.resource_sync_states)
            self.assertEqual(sync_state.resource_sync_states[resource_id].sync_time.tzinfo, timezone.utc)

        # Verify missing resources were skipped
        for resource_id in missing_resources:
            self.assertNotIn(resource_id, sync_state.resource_sync_states)


class TestEpochTimestampHandling(TestCase):
    """Tests for epoch timestamp format (new format with backward compatibility)"""

    def test_epoch_format_read(self):
        """Test reading epoch timestamps (new format)"""
        toml_str = """
[sync_state]
dependency_layer = true
latest_infra_sync_time = 1733267411.916279

[resource_sync_states]

[resource_sync_states.MockResourceId]
hash = "mock-hash"
sync_time = 1733267435.345701
"""
        toml_doc = tomlkit.loads(toml_str)
        sync_state = _toml_document_to_sync_state(toml_doc)

        # Verify both are timezone-aware UTC
        self.assertEqual(sync_state.latest_infra_sync_time.tzinfo, timezone.utc)
        self.assertEqual(sync_state.resource_sync_states["MockResourceId"].sync_time.tzinfo, timezone.utc)

    def test_epoch_format_write(self):
        """Test that writing always produces epoch, not ISO strings"""
        sync_state = SyncState(
            dependency_layer=True,
            resource_sync_states={"TestResource": ResourceSyncState("hash123", datetime.now(timezone.utc))},
            latest_infra_sync_time=datetime.now(timezone.utc),
        )

        toml_doc = _sync_state_to_toml_document(sync_state)

        # Verify written values are numeric (epoch), not strings (ISO)
        self.assertIsInstance(toml_doc["sync_state"]["latest_infra_sync_time"], (int, float))
        self.assertIsInstance(toml_doc["resource_sync_states"]["TestResource"]["sync_time"], (int, float))

    def test_backward_compatibility_mixed_formats(self):
        """Test that old ISO and new epoch can coexist during migration"""
        toml_str = """
[sync_state]
dependency_layer = true
latest_infra_sync_time = 1733267411.916279

[resource_sync_states]

[resource_sync_states.OldResource]
hash = "old-hash"
sync_time = "2025-12-03T22:10:35.345701"

[resource_sync_states.NewResource]
hash = "new-hash"
sync_time = 1733267435.345701
"""
        toml_doc = tomlkit.loads(toml_str)
        sync_state = _toml_document_to_sync_state(toml_doc)

        # Both should work and be timezone-aware
        self.assertEqual(sync_state.resource_sync_states["OldResource"].sync_time.tzinfo, timezone.utc)
        self.assertEqual(sync_state.resource_sync_states["NewResource"].sync_time.tzinfo, timezone.utc)

        # Verify datetime comparison works
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - sync_state.latest_infra_sync_time
        self.assertIsNotNone(time_diff)
