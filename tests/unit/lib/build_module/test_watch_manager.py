"""
Tests for BuildWatchManager
"""

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.lib.build.watch_manager import BuildWatchManager


class TestBuildWatchManager(TestCase):
    def setUp(self):
        self.template = "template.yaml"
        self.build_context = MagicMock()
        self.build_context.base_dir = "/base"
        self.build_context.build_dir = "/base/.aws-sam/build"
        self.build_context.cache_dir = "/base/.aws-sam/cache"
        self.build_context.build_in_source = False
        self.watch_exclude = {}

        with patch("samcli.lib.build.watch_manager.HandlerObserver"), patch.object(
            BuildWatchManager, "_validate_watch_safety"
        ), patch.object(BuildWatchManager, "_build_smart_exclusions", return_value={}):
            self.watch_manager = BuildWatchManager(
                self.template,
                self.build_context,
                self.watch_exclude,
            )

    def test_initialization(self):
        """Test that BuildWatchManager initializes correctly"""
        self.assertEqual(self.watch_manager._template, self.template)
        self.assertIsNone(self.watch_manager._stacks)
        self.assertIsNone(self.watch_manager._trigger_factory)
        self.assertFalse(self.watch_manager._waiting_build)

    @patch("samcli.lib.build.watch_manager.time.sleep")
    @patch.object(BuildWatchManager, "_execute_build")
    @patch.object(BuildWatchManager, "_start_watch")
    def test_start(self, start_watch_mock, execute_build_mock, time_sleep_mock):
        """Test the start method initiates build watch"""
        # Make time.sleep raise KeyboardInterrupt to exit the loop
        time_sleep_mock.side_effect = KeyboardInterrupt()

        # Start should catch KeyboardInterrupt gracefully
        self.watch_manager.start()

        # Verify that build was queued and initial build executed
        self.assertTrue(execute_build_mock.called)
        start_watch_mock.assert_called_once()

    @patch("samcli.lib.build.watch_manager.time.sleep")
    @patch.object(BuildWatchManager, "_execute_build")
    @patch.object(BuildWatchManager, "_start_watch")
    def test_start_with_keyboard_interrupt(self, start_watch_mock, execute_build_mock, time_sleep_mock):
        """Test that KeyboardInterrupt is handled gracefully"""
        time_sleep_mock.side_effect = KeyboardInterrupt()

        # Should not raise
        self.watch_manager.start()

        # Observer should have been stopped
        self.watch_manager._observer.stop.assert_called_once()

    @patch("samcli.lib.build.watch_manager.time.sleep")
    @patch.object(BuildWatchManager, "_start_watch")
    def test_template_change_triggers_rebuild(self, start_watch_mock, time_sleep_mock):
        """Test that template changes trigger a rebuild"""
        # Setup: start with no pending build
        self.watch_manager._waiting_build = False

        # Action: queue a build (simulating template change)
        self.watch_manager.queue_build()

        # Assert: build should be queued
        self.assertTrue(self.watch_manager._waiting_build)

    @patch("samcli.lib.build.watch_manager.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.build.watch_manager.get_all_resource_ids")
    @patch("samcli.lib.build.watch_manager.CodeTriggerFactory")
    def test_add_code_triggers(self, trigger_factory_mock, get_resource_ids_mock, get_stacks_mock):
        """Test adding code triggers for resources"""
        # Setup stacks
        stack = MagicMock()
        self.watch_manager._stacks = [stack]

        # Setup factory
        factory_instance = MagicMock()
        self.watch_manager._trigger_factory = factory_instance

        # Setup resource IDs
        resource_id = MagicMock()
        get_resource_ids_mock.return_value = [resource_id]

        # Setup trigger
        trigger = MagicMock()
        path_handlers = [MagicMock()]
        trigger.get_path_handlers.return_value = path_handlers
        factory_instance.create_trigger.return_value = trigger

        # Execute
        self.watch_manager._add_code_triggers()

        # Verify
        get_resource_ids_mock.assert_called_once_with([stack])
        factory_instance.create_trigger.assert_called_once()
        self.watch_manager._observer.schedule_handlers.assert_called_once_with(path_handlers)

    @patch("samcli.lib.build.watch_manager.Path")
    @patch.object(BuildWatchManager, "_start_template_polling")
    def test_template_validation(self, polling_mock, path_mock):
        """Test template trigger setup"""
        template_path_mock = MagicMock()
        template_path_mock.resolve.return_value = template_path_mock
        template_path_mock.parent = "/parent"
        path_mock.return_value = template_path_mock

        self.watch_manager._add_template_triggers()

        # Verify template polling was started
        polling_mock.assert_called_once()

    def test_watch_exclude_filter(self):
        """Test that watch_exclude filter is properly processed with smart exclusions"""
        watch_exclude = {"Function1": ["*.pyc", "__pycache__"]}
        build_context = MagicMock()
        build_context.base_dir = "/base"
        build_context.build_dir = "/base/.aws-sam/build"
        build_context.cache_dir = "/base/.aws-sam/cache"
        build_context.build_in_source = False

        with patch("samcli.lib.build.watch_manager.HandlerObserver"), patch.object(
            BuildWatchManager, "_validate_watch_safety"
        ):
            watch_manager = BuildWatchManager(
                self.template,
                build_context,
                watch_exclude,
            )

        # Should have Function1 with both base exclusions and user exclusions
        self.assertIn("Function1", watch_manager._watch_exclude)
        function_exclusions = watch_manager._watch_exclude["Function1"]

        # User-provided exclusions should be present
        self.assertIn("*.pyc", function_exclusions)
        self.assertIn("__pycache__", function_exclusions)

        # Base exclusions should also be present
        self.assertTrue(any(".aws-sam" in excl for excl in function_exclusions))

    @patch("samcli.lib.build.watch_manager.time.sleep")
    @patch("samcli.lib.build.watch_manager.threading.Thread")
    @patch("samcli.lib.build.watch_manager.Path")
    def test_periodic_template_check(self, path_mock, thread_mock, sleep_mock):
        """Test periodic template checking is started"""
        template_path = MagicMock()
        template_path.stat.return_value.st_mtime = 12345
        path_mock.return_value.resolve.return_value = template_path

        thread_instance = MagicMock()
        thread_mock.return_value = thread_instance

        self.watch_manager._start_template_polling()

        # Verify thread was created and started
        thread_mock.assert_called_once()
        thread_instance.start.assert_called_once()

    def test_queue_build(self):
        """Test that queue_build sets the waiting flag"""
        self.watch_manager._waiting_build = False
        self.watch_manager.queue_build()
        self.assertTrue(self.watch_manager._waiting_build)

    @patch("samcli.lib.build.watch_manager.threading.Timer")
    def test_queue_debounced_build(self, timer_mock):
        """Test that debounced build queues with a timer"""
        timer_instance = MagicMock()
        timer_mock.return_value = timer_instance

        self.watch_manager.queue_debounced_build(wait_time=2.0)

        # Verify timer was created and started
        timer_mock.assert_called_once()
        timer_instance.start.assert_called_once()

    def test_execute_debounced_build(self):
        """Test that debounced build execution sets the waiting flag"""
        self.watch_manager._waiting_build = False
        self.watch_manager._execute_debounced_build()
        self.assertTrue(self.watch_manager._waiting_build)

    @patch.object(BuildWatchManager, "_start_watch")
    def test_execute_build_success(self, start_watch_mock):
        """Test successful build execution"""
        self.watch_manager._waiting_build = True
        self.watch_manager._build_context.run = MagicMock()
        self.watch_manager._build_context.set_up = MagicMock()

        self.watch_manager._execute_build(first_build=True)

        # Verify build was executed
        self.watch_manager._build_context.run.assert_called_once()
        self.assertFalse(self.watch_manager._waiting_build)
        start_watch_mock.assert_called_once()

    @patch.object(BuildWatchManager, "_start_watch")
    def test_execute_build_failure(self, start_watch_mock):
        """Test build execution handles failures gracefully"""
        self.watch_manager._waiting_build = True
        self.watch_manager._build_context.run = MagicMock(side_effect=Exception("Build failed"))
        self.watch_manager._build_context.set_up = MagicMock()

        # Should not raise - just log error
        self.watch_manager._execute_build(first_build=False)

        # Verify build was attempted and watch continues
        self.watch_manager._build_context.run.assert_called_once()
        self.assertFalse(self.watch_manager._waiting_build)
        start_watch_mock.assert_called_once()

    @patch("samcli.lib.build.watch_manager.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.build.watch_manager.CodeTriggerFactory")
    def test_update_stacks(self, factory_mock, get_stacks_mock):
        """Test updating stacks reloads template"""
        stacks = [MagicMock()]
        get_stacks_mock.return_value = (stacks,)

        factory_instance = MagicMock()
        factory_mock.return_value = factory_instance

        self.watch_manager._update_stacks()

        # Verify stacks were loaded and factory was created
        get_stacks_mock.assert_called_once_with(self.template, use_sam_transform=False)
        self.assertEqual(self.watch_manager._stacks, stacks)
        self.assertEqual(self.watch_manager._trigger_factory, factory_instance)

    def test_build_smart_exclusions_with_build_in_source(self):
        """Test smart exclusions when building in source"""
        build_context = MagicMock()
        build_context.base_dir = "/base"
        build_context.build_dir = "/base/.aws-sam/build"
        build_context.cache_dir = "/base/.aws-sam/cache"
        build_context.build_in_source = True

        watch_exclude = {"Function1": ["custom_pattern"]}

        with patch("samcli.lib.build.watch_manager.HandlerObserver"), patch.object(
            BuildWatchManager, "_validate_watch_safety"
        ):
            watch_manager = BuildWatchManager(
                self.template,
                build_context,
                watch_exclude,
            )

        # Verify Function1 has both custom and smart exclusions
        function_exclusions = watch_manager._watch_exclude["Function1"]
        self.assertIn("custom_pattern", function_exclusions)
        # Should include build-in-source specific exclusions
        self.assertTrue(any(".pyc" in str(excl) for excl in function_exclusions))

    def test_get_cache_exclusions_under_base_dir(self):
        """Test cache exclusions when cache is under base dir"""
        build_context = MagicMock()
        build_context.base_dir = "/base"
        build_context.cache_dir = "/base/.aws-sam/cache"
        build_context.build_dir = "/base/.aws-sam/build"
        build_context.build_in_source = False

        with patch("samcli.lib.build.watch_manager.HandlerObserver"), patch.object(
            BuildWatchManager, "_validate_watch_safety"
        ):
            watch_manager = BuildWatchManager(
                self.template,
                build_context,
                {},
            )

        exclusions = watch_manager._get_cache_exclusions(build_context)
        # Should have an exclusion for the cache directory
        self.assertTrue(len(exclusions) > 0)
        self.assertTrue(any("cache" in excl for excl in exclusions))

    def test_get_cache_exclusions_outside_base_dir(self):
        """Test cache exclusions when cache is outside base dir"""
        build_context = MagicMock()
        build_context.base_dir = "/base"
        build_context.cache_dir = "/other/cache"
        build_context.build_dir = "/base/.aws-sam/build"
        build_context.build_in_source = False

        with patch("samcli.lib.build.watch_manager.HandlerObserver"), patch.object(
            BuildWatchManager, "_validate_watch_safety"
        ):
            watch_manager = BuildWatchManager(
                self.template,
                build_context,
                {},
            )

        exclusions = watch_manager._get_cache_exclusions(build_context)
        # Should be empty since cache is outside base
        self.assertEqual(exclusions, [])

    def test_on_code_change_wrapper_ignores_opened_events(self):
        """Test that file opened events are ignored"""
        resource_id = MagicMock()
        callback = self.watch_manager._on_code_change_wrapper(resource_id)

        event = MagicMock()
        event.event_type = "opened"

        # Call should return without queueing build
        self.watch_manager._waiting_build = False
        callback(event)
        self.assertFalse(self.watch_manager._waiting_build)

    def test_on_code_change_wrapper_handles_code_changes(self):
        """Test that code changes trigger debounced build"""
        resource_id = MagicMock()
        callback = self.watch_manager._on_code_change_wrapper(resource_id)

        event = MagicMock()
        event.event_type = "modified"
        event.is_directory = False

        with patch.object(self.watch_manager, "queue_debounced_build") as queue_mock:
            callback(event)
            queue_mock.assert_called_once()

    @patch("samcli.lib.build.watch_manager.LOG")
    def test_validate_watch_safety_logs_warnings(self, log_mock):
        """Test that watch safety validation logs appropriate warnings"""
        build_context = MagicMock()
        build_context.base_dir = "/base"
        build_context.build_dir = "/base/custom-build"  # Custom build dir under base
        build_context.cache_dir = "/base/.aws-sam/cache"
        build_context.build_in_source = True

        with patch("samcli.lib.build.watch_manager.HandlerObserver"):
            # This should trigger warning about custom build dir
            watch_manager = BuildWatchManager(
                self.template,
                build_context,
                {},
            )

        # Verify warning was logged
        self.assertTrue(log_mock.warning.called)
