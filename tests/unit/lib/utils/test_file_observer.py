"""
Unit tests for file observer
"""

from unittest import TestCase
from unittest.mock import Mock, patch, call

from docker.errors import ImageNotFound

from samcli.lib.providers.provider import LayerVersion
from samcli.lib.utils.file_observer import (
    FileObserver,
    FileObserverException,
    calculate_checksum,
    ImageObserver,
    ImageObserverException,
    LambdaFunctionObserver,
    SingletonFileObserver,
)
from samcli.lib.utils.packagetype import ZIP, IMAGE


class FileObserver_watch(TestCase):
    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock, uuidMock):
        self.group1 = "1234"
        uuidMock.side_effect = [self.group1]
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        self.watcher_mock = Mock()
        self.watchdog_observer_mock.schedule.return_value = self.watcher_mock
        ObserverMock.return_value = self.watchdog_observer_mock

        self._PatternMatchingEventHandlerMock = PatternMatchingEventHandlerMock
        self.handler_mock = Mock()
        self._PatternMatchingEventHandlerMock.return_value = self.handler_mock

        SingletonFileObserver._Singleton__instance = None
        self.observer = FileObserver(self.on_change)

    def test_init_successfully(self):
        self.assertEqual(self.observer._single_file_observer._observed_paths_per_group, {self.group1: {}})
        self.assertEqual(self.observer._single_file_observer._observed_watches, {})
        self.assertEqual(self.observer._single_file_observer._watch_dog_observed_paths, {})
        self.assertEqual(self.observer._single_file_observer._observer, self.watchdog_observer_mock)
        self._PatternMatchingEventHandlerMock.assert_called_with(
            patterns=["*"], ignore_patterns=[], ignore_directories=False
        )
        self.assertEqual(self.observer._single_file_observer._code_modification_handler, self.handler_mock)
        self.assertEqual(self.observer._single_file_observer._code_deletion_handler, self.handler_mock)
        self.assertEqual(
            self.observer._single_file_observer._code_modification_handler.on_modified,
            self.observer._single_file_observer.on_change,
        )
        self.assertEqual(
            self.observer._single_file_observer._code_deletion_handler.on_deleted,
            self.observer._single_file_observer.on_change,
        )
        self.assertEqual(self.observer._single_file_observer._observed_groups_handlers, {self.group1: self.on_change})

    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    def test_Exception_raised_if_observed_same_type_more_than_one_time(self, uuidMock):
        uuidMock.side_effect = [self.group1]
        with self.assertRaises(Exception):
            FileObserver(self.on_change)

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

        self.assertEqual(
            self.observer._single_file_observer._observed_paths_per_group, {self.group1: {path_str: check_sum}}
        )
        self.assertEqual(
            self.observer._single_file_observer._watch_dog_observed_paths,
            {f"{parent_path}_False": [path_str], f"{path_str}_True": [path_str]},
        )
        self.assertEqual(
            self.observer._single_file_observer._observed_watches,
            {
                f"{parent_path}_False": self.watcher_mock,
                f"{path_str}_True": self.watcher_mock,
            },
        )
        self.assertEqual(
            self.watchdog_observer_mock.schedule.call_args_list,
            [
                call(self.handler_mock, path_str, recursive=True),
                call(self.handler_mock, parent_path, recursive=False),
            ],
        )

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
        self.observer.watch(path1_str)

        self.assertEqual(
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    path1_str: check_sum,
                    path2_str: check_sum,
                }
            },
        )

        self.assertEqual(
            self.observer._single_file_observer._watch_dog_observed_paths,
            {
                f"{parent_path}_False": [path1_str, path2_str],
                f"{path1_str}_True": [path1_str],
                f"{path2_str}_True": [path2_str],
            },
        )
        self.assertEqual(
            self.observer._single_file_observer._observed_watches,
            {
                f"{parent_path}_False": self.watcher_mock,
                f"{path1_str}_True": self.watcher_mock,
                f"{path2_str}_True": self.watcher_mock,
            },
        )
        self.assertEqual(
            self.watchdog_observer_mock.schedule.call_args_list,
            [
                call(self.handler_mock, path1_str, recursive=True),
                call(self.handler_mock, parent_path, recursive=False),
                call(self.handler_mock, path2_str, recursive=True),
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
    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock, uuidMock):
        self.group1 = "1234"
        uuidMock.side_effect = [self.group1]
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        SingletonFileObserver._Singleton__instance = None
        self.observer = FileObserver(self.on_change)

        self.observer._single_file_observer._watch_dog_observed_paths = {
            "parent_path1_False": ["path1", "path2"],
            "parent_path2_False": ["path3"],
        }

        self.observer._single_file_observer._observed_paths_per_group = {
            self.group1: {
                "path1": "1234",
                "path2": "4567",
                "path3": "7890",
            }
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._single_file_observer._observed_watches = {
            "parent_path1_False": self._parent1_watcher_mock,
            "parent_path2_False": self._parent2_watcher_mock,
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
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    "path2": "4567",
                    "path3": "7890",
                }
            },
        )
        self.assertEqual(
            self.observer._single_file_observer._watch_dog_observed_paths,
            {
                "parent_path1_False": ["path2"],
                "parent_path2_False": ["path3"],
            },
        )
        self.assertEqual(
            self.observer._single_file_observer._observed_watches,
            {
                "parent_path1_False": self._parent1_watcher_mock,
                "parent_path2_False": self._parent2_watcher_mock,
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
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    "path1": "1234",
                    "path2": "4567",
                }
            },
        )
        self.assertEqual(
            self.observer._single_file_observer._watch_dog_observed_paths,
            {
                "parent_path1_False": ["path1", "path2"],
            },
        )
        self.assertEqual(
            self.observer._single_file_observer._observed_watches,
            {
                "parent_path1_False": self._parent1_watcher_mock,
            },
        )
        self.watchdog_observer_mock.unschedule.assert_called_with(self._parent2_watcher_mock)


class FileObserver_on_change(TestCase):
    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock, uuidMock):
        self.group1 = "1234"
        uuidMock.side_effect = [self.group1]
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        SingletonFileObserver._Singleton__instance = None
        self.observer = FileObserver(self.on_change)

        self.observer._single_file_observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._single_file_observer._observed_paths_per_group = {
            self.group1: {
                "parent_path1/path1": "1234",
                "parent_path1/path2": "4567",
                "parent_path2/path3": "7890",
            }
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._single_file_observer._observed_watches = {
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

        calculate_checksum_mock.side_effect = ["123456543"]

        path_mock.exists.return_value = True

        self.observer._single_file_observer.on_change(event)

        self.assertEqual(
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    "parent_path1/path1": "123456543",
                    "parent_path1/path2": "4567",
                    "parent_path2/path3": "7890",
                }
            },
        )
        self.on_change.assert_called_once_with(["parent_path1/path1"])

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

        self.observer._single_file_observer.on_change(event)

        self.assertEqual(
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    "parent_path1/path1": "1234",
                    "parent_path1/path2": "4567",
                    "parent_path2/path3": "7890",
                }
            },
        )
        self.on_change.assert_not_called()

    @patch("samcli.lib.utils.file_observer.Path")
    @patch("samcli.lib.utils.file_observer.calculate_checksum")
    def test_modification_event_got_fired_for_path_got_deleted(self, calculate_checksum_mock, PathMock):
        event = Mock()
        event.event_type == "deleted"
        event.src_path = "parent_path1/path1/sub_path"

        path_mock = Mock()
        PathMock.return_value = path_mock

        calculate_checksum_mock.return_value = "4567"

        path_mock.exists.side_effect = [False, True]

        self.observer._single_file_observer.on_change(event)

        self.assertEqual(
            self.observer._single_file_observer._observed_paths_per_group,
            {
                self.group1: {
                    "parent_path1/path2": "4567",
                    "parent_path2/path3": "7890",
                }
            },
        )
        self.on_change.assert_called_once_with(["parent_path1/path1"])


class FileObserver_start(TestCase):
    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock, uuidMock):
        self.group1 = "1234"
        uuidMock.side_effect = [self.group1]
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        SingletonFileObserver._Singleton__instance = None
        self.observer = FileObserver(self.on_change)

        self.observer._single_file_observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._single_file_observer._observed_paths_per_group = {
            self.group1: {
                "parent_path1/path1": "1234",
                "parent_path1/path2": "4567",
                "parent_path2/path3": "7890",
            }
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._single_file_observer._observed_watches = {
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
    @patch("samcli.lib.utils.file_observer.uuid.uuid4")
    @patch("samcli.lib.utils.file_observer.Observer")
    @patch("samcli.lib.utils.file_observer.PatternMatchingEventHandler")
    def setUp(self, PatternMatchingEventHandlerMock, ObserverMock, uuidMock):
        self.group1 = "1234"
        uuidMock.side_effect = [self.group1]
        self.on_change = Mock()
        self.watchdog_observer_mock = Mock()
        ObserverMock.return_value = self.watchdog_observer_mock

        self.handler_mock = Mock()
        PatternMatchingEventHandlerMock.return_value = self.handler_mock

        SingletonFileObserver._Singleton__instance = None
        self.observer = FileObserver(self.on_change)

        self.observer._single_file_observer._watch_dog_observed_paths = {
            "parent_path1": ["parent_path1/path1", "parent_path1/path2"],
            "parent_path2": ["parent_path2/path3"],
        }

        self.observer._single_file_observer._observed_paths_per_group = {
            self.group1: {
                "parent_path1/path1": "1234",
                "parent_path1/path2": "4567",
                "parent_path2/path3": "7890",
            }
        }

        self._parent1_watcher_mock = Mock()
        self._parent2_watcher_mock = Mock()

        self.observer._single_file_observer._observed_watches = {
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


class ImageObserver_init(TestCase):
    @patch("samcli.lib.utils.file_observer.threading")
    @patch("samcli.lib.utils.file_observer.docker")
    def test_image_observer_initiated_successfully(self, docker_mock, threading_mock):
        on_change = Mock()
        docker_client_mock = Mock()
        docker_mock.from_env.return_value = docker_client_mock
        events_mock = Mock()
        docker_client_mock.events.return_value = events_mock
        lock_mock = Mock()
        threading_mock.Lock.return_value = lock_mock
        image_observer = ImageObserver(on_change)
        self.assertEqual(image_observer._observed_images, {})
        self.assertEqual(image_observer._input_on_change, on_change)
        self.assertEqual(image_observer.docker_client, docker_client_mock)
        self.assertEqual(image_observer.events, events_mock)
        self.assertEqual(image_observer._images_observer_thread, None)
        self.assertEqual(image_observer._lock, lock_mock)


class ImageObserver_watch(TestCase):
    @patch("samcli.lib.utils.file_observer.docker")
    def setUp(self, docker_mock):
        self.on_change = Mock()
        self.docker_client_mock = Mock()
        docker_mock.from_env.return_value = self.docker_client_mock
        self.events_mock = Mock()
        self.docker_client_mock.events.return_value = self.events_mock
        self.image_observer = ImageObserver(self.on_change)

    def test_successfully_watch_exist_image(self):
        image_name = "test_image:test_version"
        image_mock = Mock()
        id_mock = Mock()
        image_mock.id = id_mock
        self.docker_client_mock.images.get.return_value = image_mock
        self.image_observer.watch(image_name)
        self.assertEqual(
            {
                image_name: id_mock,
            },
            self.image_observer._observed_images,
        )
        self.docker_client_mock.images.get.assert_called_with(image_name)

    def test_ImageObserverException_raised_for_not_exist_image(self):
        image_name = "test_image:test_version"
        self.docker_client_mock.images.get.side_effect = ImageNotFound("")

        with self.assertRaises(ImageObserverException):
            self.image_observer.watch(image_name)
        self.docker_client_mock.images.get.assert_called_with(image_name)


class ImageObserver_unwatch(TestCase):
    @patch("samcli.lib.utils.file_observer.docker")
    def setUp(self, docker_mock):
        self.on_change = Mock()
        self.docker_client_mock = Mock()
        docker_mock.from_env.return_value = self.docker_client_mock
        self.events_mock = Mock()
        self.docker_client_mock.events.return_value = self.events_mock
        self.image_observer = ImageObserver(self.on_change)

        self.image_name = "test_image:test_version"
        image_mock = Mock()
        self.id_mock = Mock()
        image_mock.id = self.id_mock
        self.docker_client_mock.images.get.return_value = image_mock
        self.image_observer.watch(self.image_name)

    def test_successfully_unwatch_observed_image(self):
        self.image_observer.unwatch(self.image_name)
        self.assertEqual({}, self.image_observer._observed_images)

    def test_no_exception_unwatch_non_observed_image(self):
        self.image_observer.unwatch("any_image")
        self.assertEqual(
            {
                self.image_name: self.id_mock,
            },
            self.image_observer._observed_images,
        )


class ImageObserver_start(TestCase):
    @patch("samcli.lib.utils.file_observer.docker")
    def setUp(self, docker_mock):
        self.on_change = Mock()
        self.docker_client_mock = Mock()
        docker_mock.from_env.return_value = self.docker_client_mock
        self.events_mock = Mock()
        self.docker_client_mock.events.return_value = self.events_mock
        self.image_observer = ImageObserver(self.on_change)

    @patch("samcli.lib.utils.file_observer.threading")
    def test_successfully_start_observing(self, threading_mock):
        thread_mock = Mock()
        threading_mock.Thread.return_value = thread_mock
        self.image_observer.start()
        threading_mock.Thread.assert_called_once_with(target=self.image_observer._watch_images_events, daemon=True)
        thread_mock.start.assert_called_once_with()

    @patch("samcli.lib.utils.file_observer.threading")
    def test_observing_thread_start_one_time_only(self, threading_mock):
        thread_mock = Mock()
        threading_mock.Thread.return_value = thread_mock
        self.image_observer.start()
        self.image_observer.start()
        threading_mock.Thread.assert_called_once_with(target=self.image_observer._watch_images_events, daemon=True)
        thread_mock.start.assert_called_once_with()


class ImageObserver_stop(TestCase):
    @patch("samcli.lib.utils.file_observer.threading")
    @patch("samcli.lib.utils.file_observer.docker")
    def setUp(self, docker_mock, threading_mock):
        self.on_change = Mock()
        self.docker_client_mock = Mock()
        docker_mock.from_env.return_value = self.docker_client_mock
        self.events_mock = Mock()
        self.docker_client_mock.events.return_value = self.events_mock
        self.image_observer = ImageObserver(self.on_change)
        self.thread_mock = Mock()
        threading_mock.Thread.return_value = self.thread_mock
        self.image_observer.start()

    def test_successfully_stop_observing(self):
        self.thread_mock.is_alive.side_effect = [True, False, False]
        self.image_observer.stop()
        self.events_mock.close.assert_called_once_with()
        self.assertEqual(self.thread_mock.is_alive.call_count, 2)


class ImageObserver_watch_images_events(TestCase):
    @patch("samcli.lib.utils.file_observer.docker")
    def setUp(self, docker_mock):
        self.on_change = Mock()
        self.docker_client_mock = Mock()
        docker_mock.from_env.return_value = self.docker_client_mock
        self.mocked_events_list = []
        self.events_mock = iter(self.mocked_events_list)
        self.docker_client_mock.events.return_value = self.events_mock
        self.image_observer = ImageObserver(self.on_change)

        self.image_name = "test_image:test_version"
        image_mock = Mock()
        self.id_mock = Mock()
        image_mock.id = self.id_mock
        self.docker_client_mock.images.get.return_value = image_mock
        self.image_observer.watch(self.image_name)

    def test_invoke_input_on_change_handler_if_image_id_changed(self):
        new_id_mock = Mock()
        self.mocked_events_list += [
            {"Action": "tag", "id": new_id_mock, "Actor": {"Attributes": {"name": self.image_name}}}
        ]
        self.image_observer._watch_images_events()
        self.assertEqual({self.image_name: new_id_mock}, self.image_observer._observed_images)
        self.on_change.assert_called_once_with([self.image_name])

    def test_input_on_change_handler_not_invoked_if_image_id_not_changed(self):
        self.mocked_events_list += [
            {"Action": "tag", "id": self.id_mock, "Actor": {"Attributes": {"name": self.image_name}}}
        ]
        self.image_observer._watch_images_events()
        self.assertEqual({self.image_name: self.id_mock}, self.image_observer._observed_images)
        self.on_change.assert_not_called()

    def test_skip_non_observed_images(self):
        image_name = "any_image"
        self.mocked_events_list += [
            {"Action": "tag", "id": self.id_mock, "Actor": {"Attributes": {"name": image_name}}}
        ]
        self.image_observer._watch_images_events()
        self.assertEqual({self.image_name: self.id_mock}, self.image_observer._observed_images)
        self.on_change.assert_not_called()

    def test_skip_non_tag_events(self):
        new_id_mock = Mock()
        self.mocked_events_list += [
            {"Action": "Create", "id": new_id_mock, "Actor": {"Attributes": {"name": self.image_name}}}
        ]
        self.image_observer._watch_images_events()
        self.assertEqual({self.image_name: self.id_mock}, self.image_observer._observed_images)
        self.on_change.assert_not_called()


class LambdaFunctionObserver_init(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def test_image_observer_initiated_successfully(self, ImageObserverMock, FileObserverMock):
        on_change = Mock()
        image_observer_mock = Mock()
        ImageObserverMock.return_value = image_observer_mock
        file_observer_mock = Mock()
        FileObserverMock.return_value = file_observer_mock

        lambda_function_observer = LambdaFunctionObserver(on_change)

        self.assertEqual(
            lambda_function_observer._observers,
            {
                ZIP: file_observer_mock,
                IMAGE: image_observer_mock,
            },
        )
        self.assertEqual(
            lambda_function_observer._observed_functions,
            {
                ZIP: {},
                IMAGE: {},
            },
        )
        self.assertEqual(lambda_function_observer._input_on_change, on_change)


class LambdaFunctionObserver_watch(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def setUp(self, ImageObserverMock, FileObserverMock):
        self.on_change = Mock()
        self.image_observer_mock = Mock()
        ImageObserverMock.return_value = self.image_observer_mock
        self.file_observer_mock = Mock()
        FileObserverMock.return_value = self.file_observer_mock
        self.lambda_function_observer = LambdaFunctionObserver(self.on_change)

    def test_watch_ZIP_lambda_function(self):
        lambda_function = Mock()
        lambda_function.packagetype = ZIP
        lambda_function.code_abs_path = "path1"
        lambda_function.layers = []
        self.lambda_function_observer.watch(lambda_function)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {"path1": [lambda_function]},
                IMAGE: {},
            },
        )
        self.file_observer_mock.watch.assert_called_with("path1")

    def test_watch_ZIP_lambda_function_with_layers(self):
        lambda_function = Mock()
        lambda_function.packagetype = ZIP
        lambda_function.code_abs_path = "path1"
        layer1_mock = Mock()
        layer1_mock.codeuri = "layer1_path"
        layer2_mock = Mock()
        layer2_mock.codeuri = "layer2_path"

        lambda_function.layers = [layer1_mock, layer2_mock]
        self.lambda_function_observer.watch(lambda_function)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path1": [lambda_function],
                    "layer1_path": [lambda_function],
                    "layer2_path": [lambda_function],
                },
                IMAGE: {},
            },
        )
        self.assertEqual(
            self.file_observer_mock.watch.call_args_list,
            [
                call("path1"),
                call("layer1_path"),
                call("layer2_path"),
            ],
        )

    def test_watch_ZIP_lambda_function_with_non_local_layers(self):
        lambda_function = Mock()
        lambda_function.packagetype = ZIP
        lambda_function.code_abs_path = "path1"
        layer1_mock = LayerVersion(arn="arn", codeuri="layer1_path")
        layer2_mock = LayerVersion(arn="arn2", codeuri=None)

        lambda_function.layers = [layer1_mock, layer2_mock]
        self.lambda_function_observer.watch(lambda_function)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path1": [lambda_function],
                    "layer1_path": [lambda_function],
                },
                IMAGE: {},
            },
        )
        self.assertEqual(
            self.file_observer_mock.watch.call_args_list,
            [
                call("path1"),
                call("layer1_path"),
            ],
        )

    def test_watch_IMAGE_lambda_function(self):
        lambda_function = Mock()
        lambda_function.packagetype = IMAGE
        lambda_function.imageuri = "image1"
        self.lambda_function_observer.watch(lambda_function)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {},
                IMAGE: {"image1": [lambda_function]},
            },
        )
        self.image_observer_mock.watch.assert_called_with("image1")


class LambdaFunctionObserver_unwatch(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def setUp(self, ImageObserverMock, FileObserverMock):
        self.on_change = Mock()
        self.image_observer_mock = Mock()
        ImageObserverMock.return_value = self.image_observer_mock
        self.file_observer_mock = Mock()
        FileObserverMock.return_value = self.file_observer_mock
        self.lambda_function_observer = LambdaFunctionObserver(self.on_change)

        self.zip_lambda_function1 = Mock()
        self.zip_lambda_function1.packagetype = ZIP
        self.zip_lambda_function1.code_abs_path = "path1"
        self.zip_lambda_function1.layers = []
        self.lambda_function_observer.watch(self.zip_lambda_function1)

        self.zip_lambda_function2 = Mock()
        self.zip_lambda_function2.packagetype = ZIP
        self.zip_lambda_function2.code_abs_path = "path2"
        layer1_mock = Mock()
        layer1_mock.codeuri = "layer1_path1"
        layer2_mock = Mock()
        layer2_mock.codeuri = "layer1_path2"
        self.zip_lambda_function2.layers = [layer1_mock, layer2_mock]
        self.lambda_function_observer.watch(self.zip_lambda_function2)

        self.zip_lambda_function3 = Mock()
        self.zip_lambda_function3.packagetype = ZIP
        self.zip_lambda_function3.code_abs_path = "path3"
        self.zip_lambda_function3.layers = [layer1_mock]
        self.lambda_function_observer.watch(self.zip_lambda_function3)

        self.image_lambda_function1 = Mock()
        self.image_lambda_function1.packagetype = IMAGE
        self.image_lambda_function1.imageuri = "image1"
        self.lambda_function_observer.watch(self.image_lambda_function1)

        self.image_lambda_function2 = Mock()
        self.image_lambda_function2.packagetype = IMAGE
        self.image_lambda_function2.imageuri = "image2"
        self.lambda_function_observer.watch(self.image_lambda_function2)

        self.image_lambda_function3 = Mock()
        self.image_lambda_function3.packagetype = IMAGE
        self.image_lambda_function3.imageuri = "image2"
        self.lambda_function_observer.watch(self.image_lambda_function3)

    def test_successfully_unwatch_last_zip_lambda_function(self):
        self.lambda_function_observer.unwatch(self.zip_lambda_function1)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path2": [self.zip_lambda_function2],
                    "path3": [self.zip_lambda_function3],
                    "layer1_path1": [self.zip_lambda_function2, self.zip_lambda_function3],
                    "layer1_path2": [self.zip_lambda_function2],
                },
                IMAGE: {
                    "image1": [self.image_lambda_function1],
                    "image2": [self.image_lambda_function2, self.image_lambda_function3],
                },
            },
        )
        self.file_observer_mock.unwatch.assert_called_with("path1")

    def test_successfully_unwatch_zip_lambda_function_with_layers(self):
        self.lambda_function_observer.unwatch(self.zip_lambda_function2)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path1": [self.zip_lambda_function1],
                    "path3": [self.zip_lambda_function3],
                    "layer1_path1": [self.zip_lambda_function3],
                },
                IMAGE: {
                    "image1": [self.image_lambda_function1],
                    "image2": [self.image_lambda_function2, self.image_lambda_function3],
                },
            },
        )
        self.assertEqual(
            self.file_observer_mock.unwatch.call_args_list,
            [
                call("path2"),
                call("layer1_path2"),
            ],
        )

    def test_successfully_unwatch_last_image_lambda_function(self):
        self.lambda_function_observer.unwatch(self.image_lambda_function1)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path1": [self.zip_lambda_function1],
                    "path2": [self.zip_lambda_function2],
                    "path3": [self.zip_lambda_function3],
                    "layer1_path1": [self.zip_lambda_function2, self.zip_lambda_function3],
                    "layer1_path2": [self.zip_lambda_function2],
                },
                IMAGE: {"image2": [self.image_lambda_function2, self.image_lambda_function3]},
            },
        )
        self.image_observer_mock.unwatch.assert_called_with("image1")

    def test_successfully_unwatch_non_last_image_lambda_function(self):
        self.lambda_function_observer.unwatch(self.image_lambda_function2)
        self.assertEqual(
            self.lambda_function_observer._observed_functions,
            {
                ZIP: {
                    "path1": [self.zip_lambda_function1],
                    "path2": [self.zip_lambda_function2],
                    "path3": [self.zip_lambda_function3],
                    "layer1_path1": [self.zip_lambda_function2, self.zip_lambda_function3],
                    "layer1_path2": [self.zip_lambda_function2],
                },
                IMAGE: {"image1": [self.image_lambda_function1], "image2": [self.image_lambda_function3]},
            },
        )
        self.image_observer_mock.unwatch.assert_not_called()


class LambdaFunctionObserver_start(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def setUp(self, ImageObserverMock, FileObserverMock):
        self.on_change = Mock()
        self.image_observer_mock = Mock()
        ImageObserverMock.return_value = self.image_observer_mock
        self.file_observer_mock = Mock()
        FileObserverMock.return_value = self.file_observer_mock
        self.lambda_function_observer = LambdaFunctionObserver(self.on_change)

    def test_successfully_start_observing(self):
        self.lambda_function_observer.start()
        self.file_observer_mock.start.assert_called_once_with()
        self.image_observer_mock.start.assert_called_once_with()


class LambdaFunctionObserver_stop(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def setUp(self, ImageObserverMock, FileObserverMock):
        self.on_change = Mock()
        self.image_observer_mock = Mock()
        ImageObserverMock.return_value = self.image_observer_mock
        self.file_observer_mock = Mock()
        FileObserverMock.return_value = self.file_observer_mock
        self.lambda_function_observer = LambdaFunctionObserver(self.on_change)

    def test_successfully_start_observing(self):
        self.lambda_function_observer.stop()
        self.file_observer_mock.stop.assert_called_once_with()
        self.image_observer_mock.stop.assert_called_once_with()


class LambdaFunctionObserver_on_change(TestCase):
    @patch("samcli.lib.utils.file_observer.FileObserver")
    @patch("samcli.lib.utils.file_observer.ImageObserver")
    def setUp(self, ImageObserverMock, FileObserverMock):
        self.on_change = Mock()
        self.image_observer_mock = Mock()
        ImageObserverMock.return_value = self.image_observer_mock
        self.file_observer_mock = Mock()
        FileObserverMock.return_value = self.file_observer_mock
        self.lambda_function_observer = LambdaFunctionObserver(self.on_change)

        self.zip_lambda_function1 = Mock()
        self.zip_lambda_function1.packagetype = ZIP
        self.zip_lambda_function1.code_abs_path = "path1"
        self.zip_lambda_function1.layers = []
        self.lambda_function_observer.watch(self.zip_lambda_function1)

        self.zip_lambda_function2 = Mock()
        self.zip_lambda_function2.packagetype = ZIP
        self.zip_lambda_function2.code_abs_path = "path2"
        layer1_mock = Mock()
        layer1_mock.codeuri = "layer1_path1"
        layer2_mock = Mock()
        layer2_mock.codeuri = "layer1_path2"
        self.zip_lambda_function2.layers = [layer1_mock, layer2_mock]
        self.lambda_function_observer.watch(self.zip_lambda_function2)

        self.zip_lambda_function3 = Mock()
        self.zip_lambda_function3.packagetype = ZIP
        self.zip_lambda_function3.code_abs_path = "path3"
        self.zip_lambda_function3.layers = [layer1_mock]
        self.lambda_function_observer.watch(self.zip_lambda_function3)

        self.image_lambda_function1 = Mock()
        self.image_lambda_function1.packagetype = IMAGE
        self.image_lambda_function1.imageuri = "image1"
        self.lambda_function_observer.watch(self.image_lambda_function1)

        self.image_lambda_function2 = Mock()
        self.image_lambda_function2.packagetype = IMAGE
        self.image_lambda_function2.imageuri = "image2"
        self.lambda_function_observer.watch(self.image_lambda_function2)

        self.image_lambda_function3 = Mock()
        self.image_lambda_function3.packagetype = IMAGE
        self.image_lambda_function3.imageuri = "image2"
        self.lambda_function_observer.watch(self.image_lambda_function3)

    def test_one_lambda_function_code_path_got_changed(self):
        self.lambda_function_observer._on_zip_change(["path1"])
        self.on_change.assert_called_once_with([self.zip_lambda_function1])

    def test_one_lambda_function_layer_code_path_got_changed(self):
        self.lambda_function_observer._on_zip_change(["layer1_path2"])
        self.on_change.assert_called_once_with([self.zip_lambda_function2])

    def test_common_layer_code_path_got_changed(self):
        self.lambda_function_observer._on_zip_change(["layer1_path1"])
        self.on_change.assert_called_once_with([self.zip_lambda_function2, self.zip_lambda_function3])

    def test_one_lambda_function_image_got_changed(self):
        self.lambda_function_observer._on_image_change(["image1"])
        self.on_change.assert_called_once_with([self.image_lambda_function1])

    def test_common_image_got_changed(self):
        self.lambda_function_observer._on_image_change(["image2"])
        self.on_change.assert_called_once_with([self.image_lambda_function2, self.image_lambda_function3])


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
