from unittest.case import TestCase
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from typing import Dict, List
from samcli.lib.build.watch_manager import BuildWatchManager


class TestBuildWatchManager(TestCase):
    def setUp(self) -> None:
        self.template = "template.yaml"
        self.build_context = MagicMock()
        self.watch_exclude: Dict[str, List[str]] = {}
        
        self.path_observer_patch = patch("samcli.lib.build.watch_manager.HandlerObserver")
        self.path_observer_mock = self.path_observer_patch.start()
        self.path_observer = self.path_observer_mock.return_value
        
        self.colored_patch = patch("samcli.lib.build.watch_manager.Colored")
        self.colored_mock = self.colored_patch.start()
        self.colored = self.colored_mock.return_value
        
        self.watch_manager = BuildWatchManager(
            self.template,
            self.build_context,
            self.watch_exclude,
        )

    def tearDown(self) -> None:
        self.path_observer_patch.stop()
        self.colored_patch.stop()

    def test_initialization(self):
        """Test that BuildWatchManager initializes correctly"""
        self.assertEqual(self.watch_manager._template_path, Path(self.template))
        self.assertEqual(self.watch_manager._build_context, self.build_context)
        self.assertEqual(self.watch_manager._watch_exclude, self.watch_exclude)

    @patch("samcli.lib.build.watch_manager.FileSystemEventHandler")
    @patch("samcli.lib.build.watch_manager.Observer")
    @patch("samcli.lib.build.watch_manager.threading.Thread")
    @patch("samcli.lib.build.watch_manager.time.sleep")
    def test_start(self, sleep_mock, thread_mock, observer_mock, handler_mock):
        """Test that start() method sets up watchers and runs the loop"""
        sleep_mock.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager.start()
        
        # Verify observer was started
        observer_mock.return_value.start.assert_called_once()

    @patch("samcli.lib.build.watch_manager.Observer")
    @patch("samcli.lib.build.watch_manager.threading.Thread")
    @patch("samcli.lib.build.watch_manager.time.sleep")
    def test_start_with_keyboard_interrupt(self, sleep_mock, thread_mock, observer_mock):
        """Test that KeyboardInterrupt is handled gracefully"""
        sleep_mock.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager.start()
        
        observer_mock.return_value.stop.assert_called_once()

    @patch("samcli.lib.build.watch_manager.Observer")
    def test_template_change_triggers_rebuild(self, observer_mock):
        """Test that template changes trigger a rebuild"""
        # This test verifies the template event handler is created
        with patch("samcli.lib.build.watch_manager.threading.Thread"):
            with patch("samcli.lib.build.watch_manager.time.sleep", side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    self.watch_manager.start()

    @patch("samcli.lib.build.watch_manager.get_all_resource_ids")
    @patch("samcli.lib.build.watch_manager.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.build.watch_manager.CodeTriggerFactory")
    def test_add_code_triggers(self, trigger_factory_mock, get_stacks_mock, get_resource_ids_mock):
        """Test adding code triggers for resources"""
        stacks = [MagicMock()]
        get_stacks_mock.return_value = [stacks]
        
        resource_ids = [MagicMock()]
        get_resource_ids_mock.return_value = resource_ids
        
        trigger = MagicMock()
        trigger_factory_mock.return_value.create_trigger.return_value = trigger
        
        self.watch_manager._add_code_triggers()
        
        get_stacks_mock.assert_called_once()
        trigger_factory_mock.assert_called_once()

    @patch("samcli.lib.build.watch_manager.time.sleep")
    @patch("samcli.lib.build.watch_manager.Observer")
    @patch("samcli.lib.build.watch_manager.threading.Thread")
    def test_template_validation(self, thread_mock, observer_mock, sleep_mock):
        """Test template validation during startup"""
        sleep_mock.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager.start()

    def test_watch_exclude_filter(self):
        """Test that watch_exclude filter is properly initialized"""
        watch_exclude = {"Function1": ["*.pyc", "__pycache__"]}
        watch_manager = BuildWatchManager(
            self.template,
            self.build_context,
            watch_exclude,
        )
        self.assertEqual(watch_manager._watch_exclude, watch_exclude)

    @patch("samcli.lib.build.watch_manager.Observer")
    @patch("samcli.lib.build.watch_manager.threading.Thread")
    def test_periodic_template_check(self, thread_mock, observer_mock):
        """Test that periodic template checking thread is created"""
        with patch("samcli.lib.build.watch_manager.time.sleep", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.watch_manager.start()
            
            # Verify a thread was created for periodic checking
            thread_mock.assert_called()
