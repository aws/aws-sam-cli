"""
Unit tests for file observer
"""
from unittest import TestCase
from unittest.mock import Mock, patch, call

from samcli.lib.utils.file_observer import FileObserver, FileObserverException, calculate_checksum


class FileObserver_watch(TestCase):
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock):
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        self.watcher_mock = Mock()
        self.watchdog_observer_mock.schedule.return_value = self.watcher_mock
        ObserverMock.return_value = self.watchdog_observer_mock

        self._PatternMatchingEventHandlerMock = PatternMatchingEventHandlerMock
        self.handler_mock = Mock()
        self._PatternMatchingEventHandlerMock.return_value = self.handler_mock

        self.observer = FileObserver(self.on_change)

    def test_init_successfully(self):
        self.assertEqual(self.observer._observed_paths, {})
        self.assertEqual(self.observer._observed_watches, {})
        self.assertEqual(self.observer._watch_dog_observed_paths, {})
        self.assertEqual(self.observer._observer, self.watchdog_observer_mock)
        self._PatternMatchingEventHandlerMock.assert_called_with(
            patterns=["*"], ignore_patterns=[], ignore_directories=False
        )
        self.assertEqual(self.observer._code_change_handler, self.handler_mock)
        self.assertEqual(self.observer._input_on_change, self.on_change)

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_path_get_watched_successfully(self, calculate_checksum_mock, PathMock):
        path_str = "path"
        parent_path = "parent_path"
        check_sum = "1234565432"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.parent = parent_path

        path_mock.exists.return_value = True

        calculate_checksum_mock.return_value = check_sum

        self.observer.watch(path_str)

        self.assertEqual(self.observer._observed_paths, {path_str: check_sum})
        self.assertEqual(
            self.observer._watch_dog_observed_paths,
            {parent_path: [path_str]},
        )
        self.assertEqual(
            self.observer._observed_watches,
            {parent_path: self.watcher_mock},
        )
        self.watchdog_observer_mock.schedule.assert_called_with(self.handler_mock, parent_path, recursive=True)

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_parent_path_get_watched_only_one_time(self, calculate_checksum_mock, PathMock):
        path1_str = "path1"
        path2_str = "path2"
        parent_path = "parent_path"
        check_sum = "1234565432"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.parent = parent_path

        path_mock.exists.return_value = True

        calculate_checksum_mock.return_value = check_sum

        self.observer.watch(path1_str)
        self.observer.watch(path2_str)

        self.assertEqual(
            self.observer._observed_paths,
            {
                path1_str: check_sum,
                path2_str: check_sum,
            },
        )

        self.assertEqual(
            self.observer._watch_dog_observed_paths,
            {parent_path: [path1_str, path2_str]},
        )
        self.assertEqual(
            self.observer._observed_watches,
            {parent_path: self.watcher_mock},
        )
        self.assertEqual(
            self.watchdog_observer_mock.schedule.call_args_list,
            [
                call(self.handler_mock, parent_path, recursive=True),
            ],
        )

    @patch("samcli.lib.utils.file_observer.Path")
    def test_raise_FileObserverException_if_watched_path_is_not_exist(self, PathMock):
        path_str = "path"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.exists.return_value = False

        with self.assertRaises(FileObserverException):
            self.observer.watch(path_str)


class FileObserver_unwatch(TestCase):
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock):
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        self.observer = FileObserver(self.on_change)

        self.observer._watch_dog_observed_paths = {
            "parent_path1": ["path1", "path2"],
            "parent_path2": ["path3"],
        }

        self.observer._observed_paths = {
            "path1": "1234",
            "path2": "4567",
            "path3": "7890",
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._observed_watches = {
            "parent_path1": self._parent1_watcher_mock,
            "parent_path2": self._parent2_watcher_mock,
        }

    @patch("samcli.lib.utils.file_observer.Path")
    def test_path_get_unwatched_successfully(self, PathMock):
        path_str = "path1"
        parent_path = "parent_path1"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.parent = parent_path

        path_mock.exists.return_value = True

        self.observer.unwatch(path_str)

        self.assertEqual(
            self.observer._observed_paths,
            {
                "path2": "4567",
                "path3": "7890",
            },
        )
        self.assertEqual(
            self.observer._watch_dog_observed_paths,
            {
                "parent_path1": ["path2"],
                "parent_path2": ["path3"],
            },
        )
        self.assertEqual(
            self.observer._observed_watches,
            {
                "parent_path1": self._parent1_watcher_mock,
                "parent_path2": self._parent2_watcher_mock,
            },
        )
        self.watchdog_observer_mock.unschedule.assert_not_called()

    @patch("samcli.lib.utils.file_observer.Path")
    def test_parent_path_get_unwatched_successfully(self, PathMock):
        path_str = "path3"
        parent_path = "parent_path2"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.parent = parent_path

        path_mock.exists.return_value = True

        self.observer.unwatch(path_str)

        self.assertEqual(
            self.observer._observed_paths,
            {
                "path1": "1234",
                "path2": "4567",
            },
        )
        self.assertEqual(
            self.observer._watch_dog_observed_paths,
            {
                "parent_path1": ["path1", "path2"],
            },
        )
        self.assertEqual(
            self.observer._observed_watches,
            {
                "parent_path1": self._parent1_watcher_mock,
            },
        )
        self.watchdog_observer_mock.unschedule.assert_called_with(self._parent2_watcher_mock)

    @patch("samcli.lib.utils.file_observer.Path")
    def test_raise_FileObserverException_if_unwatched_path_is_not_exist(self, PathMock):
        path_str = "path"

        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.exists.return_value = False

        with self.assertRaises(FileObserverException):
            self.observer.unwatch(path_str)


class FileObserver_on_change(TestCase):
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock):
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        self.observer = FileObserver(self.on_change)

        self.observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._observed_paths = {
            "parent_path1/path1": "1234",
            "parent_path1/path2": "4567",
            "parent_path2/path3": "7890",
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._observed_watches = {
            "parent_path1": self._parent1_watcher_mock,
            "parent_path2": self._parent2_watcher_mock,
        }

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_modification_event_got_fired_for_sub_path_and_check_sum_changed(self, calculate_checksum_mock, PathMock):
        event = Mock()
        event.src_path = "parent_path1/path1/sub_path"

        path_mock = Mock()
        PathMock.return_value = path_mock

        calculate_checksum_mock.side_effect = ["1234", "123456543"]

        path_mock.exists.return_value = True

        self.observer.on_change(event)

        self.assertEqual(
            self.observer._observed_paths,
            {
                "parent_path1/path1": "1234",
                "parent_path1/path2": "123456543",
                "parent_path2/path3": "7890",
            },
        )
        self.on_change.assert_called_once_with(["parent_path1/path2"])

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_modification_event_got_fired_for_sub_path_and_check_sum_is_not_changed(
        self, calculate_checksum_mock, PathMock
    ):
        event = Mock()
        event.src_path = "parent_path1/path1/sub_path"

        path_mock = Mock()
        PathMock.return_value = path_mock

        calculate_checksum_mock.side_effect = ["1234", "4567"]

        path_mock.exists.return_value = True

        self.observer.on_change(event)

        self.assertEqual(
            self.observer._observed_paths,
            {
                "parent_path1/path1": "1234",
                "parent_path1/path2": "4567",
                "parent_path2/path3": "7890",
            },
        )
        self.on_change.assert_not_called()

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_modification_event_got_fired_for_path_got_deleted(self, calculate_checksum_mock, PathMock):
        event = Mock()
        event.src_path = "parent_path1/path1/sub_path"

        path_mock = Mock()
        PathMock.return_value = path_mock

        calculate_checksum_mock.return_value = "4567"

        path_mock.exists.side_effect = [False, True]

        self.observer.on_change(event)

        self.assertEqual(
            self.observer._observed_paths,
            {
                "parent_path1/path2": "4567",
                "parent_path2/path3": "7890",
            },
        )
        self.on_change.assert_called_once_with(["parent_path1/path1"])


class FileObserver_start(TestCase):
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock):
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        self.observer = FileObserver(self.on_change)

        self.observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._observed_paths = {
            "parent_path1/path1": "1234",
            "parent_path1/path2": "4567",
            "parent_path2/path3": "7890",
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._observed_watches = {
            "parent_path1": self._parent1_watcher_mock,
            "parent_path2": self._parent2_watcher_mock,
        }

    def test_start_non_started_observer_successfully(self):
        self.watchdog_observer_mock.is_alive.return_value = False
        self.observer.start()
        self.watchdog_observer_mock.start.assert_called_with()

    def test_start_started_observer_does_not_call_watchdog_observer(self):
        self.watchdog_observer_mock.is_alive.return_value = True
        self.observer.start()
        self.watchdog_observer_mock.start.assert_not_called()


class FileObserver_stop(TestCase):
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock):
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        self.observer = FileObserver(self.on_change)

        self.observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._observed_paths = {
            "parent_path1/path1": "1234",
            "parent_path1/path2": "4567",
            "parent_path2/path3": "7890",
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._observed_watches = {
            "parent_path1": self._parent1_watcher_mock,
            "parent_path2": self._parent2_watcher_mock,
        }

    def test_stop_started_observer_successfully(self):
        self.watchdog_observer_mock.is_alive.return_value = True
        self.observer.stop()
        self.watchdog_observer_mock.stop.assert_called_with()

    def test_stop_non_started_observer_does_not_call_watchdog_observer(self):
        self.watchdog_observer_mock.is_alive.return_value = False
        self.observer.stop()
        self.watchdog_observer_mock.stop.assert_not_called()


class TestCalculateChecksum(TestCase):
    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.file_checksum")
    def test_calculate_check_sum_for_file(self, file_checksum_mock, PathMock):
        path = "path"
        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.is_file.return_value = True
        file_checksum_mock.return_value = "1234"
        self.assertEqual(calculate_checksum(path), "1234")

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.dir_checksum")
    def test_calculate_check_sum_for_dir(self, dir_checksum_mock, PathMock):
        path = "path"
        path_mock = Mock()
        PathMock.return_value = path_mock
        path_mock.is_file.return_value = False
        dir_checksum_mock.return_value = "1234"
        self.assertEqual(calculate_checksum(path), "1234")
