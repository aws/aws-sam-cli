import re
from unittest.case import TestCase
from unittest.mock import MagicMock, patch, ANY
from samcli.lib.utils.path_observer import HandlerObserver, PathHandler, StaticFolderWrapper


class TestPathHandler(TestCase):
    def test_init(self):
        handler_mock = MagicMock()
        path_mock = MagicMock()
        create_mock = MagicMock()
        delete_mock = MagicMock()
        bundle = PathHandler(handler_mock, path_mock, True, True, create_mock, delete_mock)

        self.assertEqual(bundle.event_handler, handler_mock)
        self.assertEqual(bundle.path, path_mock)
        self.assertEqual(bundle.self_create, create_mock)
        self.assertEqual(bundle.self_delete, delete_mock)
        self.assertTrue(bundle.recursive)
        self.assertTrue(bundle.static_folder)


class TestStaticFolderWrapper(TestCase):
    def setUp(self) -> None:
        self.observer = MagicMock()
        self.path_handler = MagicMock()
        self.initial_watch = MagicMock()
        self.wrapper = StaticFolderWrapper(self.observer, self.initial_watch, self.path_handler)

    def test_on_parent_change_on_delete(self):
        watch_mock = MagicMock()
        self.wrapper._watch = watch_mock
        self.wrapper._path_handler.path.exists.return_value = False

        self.wrapper._on_parent_change(MagicMock())

        self.path_handler.self_delete.assert_called_once_with()
        self.observer.unschedule.assert_called_once_with(watch_mock)
        self.assertIsNone(self.wrapper._watch)

    def test_on_parent_change_on_create(self):
        watch_mock = MagicMock()
        self.observer.schedule_handler.return_value = watch_mock

        self.wrapper._watch = None
        self.wrapper._path_handler.path.exists.return_value = True

        self.wrapper._on_parent_change(MagicMock())

        self.path_handler.self_create.assert_called_once_with()
        self.observer.schedule_handler.assert_called_once_with(self.wrapper._path_handler)
        self.assertEqual(self.wrapper._watch, watch_mock)

    @patch("samcli.lib.utils.path_observer.RegexMatchingEventHandler")
    @patch("samcli.lib.utils.path_observer.PathHandler")
    def test_get_dir_parent_path_handler(self, path_handler_mock, event_handler_mock):
        path_mock = MagicMock()
        path_mock.resolve.return_value.parent = "/parent/"
        path_mock.resolve.return_value.__str__.return_value = "/parent/dir/"
        self.path_handler.path = path_mock

        event_handler = MagicMock()
        event_handler_mock.return_value = event_handler
        path_handler = MagicMock()
        path_handler_mock.return_value = path_handler
        result = self.wrapper.get_dir_parent_path_handler()

        self.assertEqual(result, path_handler)
        path_handler_mock.assert_called_once_with(path="/parent/", event_handler=event_handler)
        escaped_path = re.escape("/parent/dir/")
        event_handler_mock.assert_called_once_with(
            regexes=[f"^{escaped_path}$"], ignore_regexes=[], ignore_directories=False, case_sensitive=True
        )


class TestHandlerObserver(TestCase):
    def setUp(self) -> None:
        self.observer = HandlerObserver()

    def test_schedule_handlers(self):
        bundle_1 = MagicMock()
        bundle_2 = MagicMock()
        watch_1 = MagicMock()
        watch_2 = MagicMock()

        schedule_handler_mock = MagicMock()
        schedule_handler_mock.side_effect = [watch_1, watch_2]
        self.observer.schedule_handler = schedule_handler_mock
        result = self.observer.schedule_handlers([bundle_1, bundle_2])
        self.assertEqual(result, [watch_1, watch_2])
        schedule_handler_mock.assert_any_call(bundle_1)
        schedule_handler_mock.assert_any_call(bundle_2)

    @patch("samcli.lib.utils.path_observer.StaticFolderWrapper")
    def test_schedule_handler_not_static(self, wrapper_mock: MagicMock):
        bundle = MagicMock()
        event_handler = MagicMock()
        bundle.event_handler = event_handler
        bundle.path = "dir"
        bundle.recursive = True
        bundle.static_folder = False
        watch = MagicMock()

        schedule_mock = MagicMock()
        schedule_mock.return_value = watch
        self.observer.schedule = schedule_mock

        result = self.observer.schedule_handler(bundle)

        self.assertEqual(result, watch)
        schedule_mock.assert_any_call(bundle.event_handler, "dir", True)
        wrapper_mock.assert_not_called()

    @patch("samcli.lib.utils.path_observer.StaticFolderWrapper")
    def test_schedule_handler_static(self, wrapper_mock: MagicMock):
        bundle = MagicMock()
        event_handler = MagicMock()
        bundle.event_handler = event_handler
        bundle.path = "dir"
        bundle.recursive = True
        bundle.static_folder = True
        watch = MagicMock()

        parent_bundle = MagicMock()
        event_handler = MagicMock()
        parent_bundle.event_handler = event_handler
        parent_bundle.path = "parent"
        parent_bundle.recursive = False
        parent_bundle.static_folder = False
        parent_watch = MagicMock()

        schedule_mock = MagicMock()
        schedule_mock.side_effect = [watch, parent_watch]
        self.observer.schedule = schedule_mock

        wrapper = MagicMock()
        wrapper_mock.return_value = wrapper
        wrapper.get_dir_parent_path_handler.return_value = parent_bundle

        result = self.observer.schedule_handler(bundle)

        self.assertEqual(result, parent_watch)
        schedule_mock.assert_any_call(bundle.event_handler, "dir", True)
        schedule_mock.assert_any_call(parent_bundle.event_handler, "parent", False)
        wrapper_mock.assert_called_once_with(self.observer, watch, bundle)
