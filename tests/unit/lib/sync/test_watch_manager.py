from unittest.case import TestCase
from unittest.mock import MagicMock, patch, ANY
from samcli.lib.sync.watch_manager import WatchManager
from samcli.lib.providers.exceptions import MissingCodeUri, MissingLocalDefinition, InvalidTemplateFile
from samcli.lib.sync.exceptions import MissingPhysicalResourceError, SyncFlowException


class TestWatchManager(TestCase):
    def setUp(self) -> None:
        self.template = "template.yaml"
        self.path_observer_patch = patch("samcli.lib.sync.watch_manager.HandlerObserver")
        self.path_observer_mock = self.path_observer_patch.start()
        self.path_observer = self.path_observer_mock.return_value
        self.executor_patch = patch("samcli.lib.sync.watch_manager.ContinuousSyncFlowExecutor")
        self.executor_mock = self.executor_patch.start()
        self.executor = self.executor_mock.return_value
        self.colored_patch = patch("samcli.lib.sync.watch_manager.Colored")
        self.colored_mock = self.colored_patch.start()
        self.colored = self.colored_mock.return_value
        self.build_context = MagicMock()
        self.package_context = MagicMock()
        self.deploy_context = MagicMock()
        self.sync_context = MagicMock()
        self.watch_manager = WatchManager(
            self.template,
            self.build_context,
            self.package_context,
            self.deploy_context,
            self.sync_context,
            False,
            False,
        )

    def tearDown(self) -> None:
        self.path_observer_patch.stop()
        self.executor_patch.stop()
        self.colored_patch.stop()

    def test_queue_infra_sync(self):
        self.assertFalse(self.watch_manager._waiting_infra_sync)
        self.watch_manager.queue_infra_sync()
        self.assertTrue(self.watch_manager._waiting_infra_sync)

    @patch("samcli.lib.sync.watch_manager.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.sync.watch_manager.SyncFlowFactory")
    @patch("samcli.lib.sync.watch_manager.CodeTriggerFactory")
    @patch("samcli.lib.sync.watch_manager.Path")
    def test_update_stacks(
        self,
        path_mock: MagicMock,
        trigger_factory_mock: MagicMock,
        sync_flow_factory_mock: MagicMock,
        get_stacks_mock: MagicMock,
    ):
        stacks = [MagicMock()]
        get_stacks_mock.return_value = [
            stacks,
        ]
        self.watch_manager._update_stacks()
        get_stacks_mock.assert_called_once_with(self.template)
        sync_flow_factory_mock.assert_called_once_with(
            self.build_context, self.deploy_context, self.sync_context, stacks, False
        )
        sync_flow_factory_mock.return_value.load_physical_id_mapping.assert_called_once_with()
        trigger_factory_mock.assert_called_once_with(stacks, path_mock.return_value)

    @patch("samcli.lib.sync.watch_manager.get_all_resource_ids")
    def test_add_code_triggers(self, get_all_resource_ids_mock):
        resource_ids = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        get_all_resource_ids_mock.return_value = resource_ids

        trigger_1 = MagicMock()
        trigger_2 = MagicMock()

        trigger_factory = MagicMock()
        trigger_factory.create_trigger.side_effect = [
            trigger_1,
            None,
            MissingCodeUri(),
            trigger_2,
            MissingLocalDefinition(MagicMock(), MagicMock()),
        ]
        self.watch_manager._stacks = [MagicMock()]
        self.watch_manager._trigger_factory = trigger_factory

        on_code_change_wrapper_mock = MagicMock()
        self.watch_manager._on_code_change_wrapper = on_code_change_wrapper_mock

        self.watch_manager._add_code_triggers()

        trigger_factory.create_trigger.assert_any_call(resource_ids[0], on_code_change_wrapper_mock.return_value)
        trigger_factory.create_trigger.assert_any_call(resource_ids[1], on_code_change_wrapper_mock.return_value)

        on_code_change_wrapper_mock.assert_any_call(resource_ids[0])
        on_code_change_wrapper_mock.assert_any_call(resource_ids[1])

        self.path_observer.schedule_handlers.assert_any_call(trigger_1.get_path_handlers.return_value)
        self.path_observer.schedule_handlers.assert_any_call(trigger_2.get_path_handlers.return_value)
        self.assertEqual(self.path_observer.schedule_handlers.call_count, 2)

    @patch("samcli.lib.sync.watch_manager.TemplateTrigger")
    @patch("samcli.lib.sync.watch_manager.SamLocalStackProvider.get_stacks")
    def test_add_template_triggers(self, get_stack_mock, template_trigger_mock):
        trigger = template_trigger_mock.return_value
        stack_name = "stack"
        stack_mock = MagicMock()
        stack_mock.location = self.template
        stack_mock.name = stack_name
        get_stack_mock.return_value = [[stack_mock]]

        self.watch_manager._add_template_triggers()

        template_trigger_mock.assert_called_once_with(self.template, stack_name, ANY)
        self.path_observer.schedule_handlers.assert_any_call(trigger.get_path_handlers.return_value)

    @patch("samcli.lib.sync.watch_manager.TemplateTrigger")
    @patch("samcli.lib.sync.watch_manager.SamLocalStackProvider.get_stacks")
    def test_add_nested_template_triggers(self, get_stack_mock, template_trigger_mock):
        trigger = template_trigger_mock.return_value
        root_stack = MagicMock()
        root_stack.location = "template.yaml"
        root_stack.name = "root_stack"
        child_stack = MagicMock()
        child_stack.location = "child_stack/child_template.yaml"
        child_stack.name = "child_stack"
        child_stack2 = MagicMock()
        child_stack2.location = "child_stack2/child_template2.yaml"
        child_stack2.name = "child_stack2"
        get_stack_mock.return_value = [[root_stack, child_stack, child_stack2]]

        self.watch_manager._add_template_triggers()

        self.assertEqual(3, template_trigger_mock.call_count)

        template_trigger_mock.assert_any_call("template.yaml", "root_stack", ANY)
        template_trigger_mock.assert_any_call("child_stack/child_template.yaml", "child_stack", ANY)
        template_trigger_mock.assert_any_call("child_stack2/child_template2.yaml", "child_stack2", ANY)

        self.assertEqual(3, self.path_observer.schedule_handlers.call_count)
        self.path_observer.schedule_handlers.assert_any_call(trigger.get_path_handlers.return_value)

    @patch("samcli.lib.sync.watch_manager.TemplateTrigger")
    @patch("samcli.lib.sync.watch_manager.SamLocalStackProvider.get_stacks")
    def test_add_invalid_template_triggers(self, get_stack_mock, template_trigger_mock):
        stack_name = "stack"
        template = "template.yaml"
        template_trigger_mock.return_value.raw_validate.side_effect = InvalidTemplateFile(template, stack_name)
        stack = MagicMock()
        stack.location = template
        stack.name = stack_name
        get_stack_mock.return_value = [[stack]]

        self.watch_manager._add_template_triggers()

        self.assertEqual(1, template_trigger_mock.call_count)

        template_trigger_mock.assert_any_call("template.yaml", stack_name, ANY)

        self.assertEqual(1, self.path_observer.schedule_handlers.call_count)

    def test_execute_infra_sync(self):
        self.watch_manager._execute_infra_context()
        self.build_context.set_up.assert_called_once_with()
        self.build_context.run.assert_called_once_with()
        self.package_context.run.assert_called_once_with()
        self.deploy_context.run.assert_called_once_with()

    @patch("samcli.lib.sync.watch_manager.threading.Thread")
    def test_start_code_sync(self, thread_mock):
        self.watch_manager._start_code_sync()
        thread = thread_mock.return_value

        self.assertEqual(self.watch_manager._executor_thread, thread)
        thread.start.assert_called_once_with()

    def test_stop_code_sync(self):
        thread = MagicMock()
        thread.is_alive.return_value = True
        self.watch_manager._executor_thread = thread

        self.watch_manager._stop_code_sync()

        self.executor.stop.assert_called_once_with()
        thread.join.assert_called_once_with()

    def test_start(self):
        queue_infra_sync_mock = MagicMock()
        _start_mock = MagicMock()
        stop_code_sync_mock = MagicMock()

        self.watch_manager.queue_infra_sync = queue_infra_sync_mock
        self.watch_manager._start = _start_mock
        self.watch_manager._stop_code_sync = stop_code_sync_mock

        _start_mock.side_effect = KeyboardInterrupt()

        self.watch_manager.start()

        self.path_observer.stop.assert_called_once_with()
        stop_code_sync_mock.assert_called_once_with()

    @patch("samcli.lib.sync.watch_manager.time.sleep")
    def test__start(self, sleep_mock):
        sleep_mock.side_effect = KeyboardInterrupt()

        stop_code_sync_mock = MagicMock()
        execute_infra_sync_mock = MagicMock()

        update_stacks_mock = MagicMock()
        add_template_trigger_mock = MagicMock()
        add_code_trigger_mock = MagicMock()
        start_code_sync_mock = MagicMock()

        self.watch_manager._stop_code_sync = stop_code_sync_mock
        self.watch_manager._execute_infra_context = execute_infra_sync_mock
        self.watch_manager._update_stacks = update_stacks_mock
        self.watch_manager._add_template_triggers = add_template_trigger_mock
        self.watch_manager._add_code_triggers = add_code_trigger_mock
        self.watch_manager._start_code_sync = start_code_sync_mock

        self.watch_manager._waiting_infra_sync = True
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager._start()

        self.path_observer.start.assert_called_once_with()
        self.assertFalse(self.watch_manager._waiting_infra_sync)

        stop_code_sync_mock.assert_called_once_with()
        execute_infra_sync_mock.assert_called_once_with()
        update_stacks_mock.assert_called_once_with()
        add_template_trigger_mock.assert_called_once_with()
        add_code_trigger_mock.assert_called_once_with()
        start_code_sync_mock.assert_called_once_with()

        self.path_observer.unschedule_all.assert_called_once_with()

        self.path_observer.start.assert_called_once_with()

    @patch("samcli.lib.sync.watch_manager.time.sleep")
    def test_start_code_only(self, sleep_mock):
        sleep_mock.side_effect = KeyboardInterrupt()

        stop_code_sync_mock = MagicMock()
        execute_infra_sync_mock = MagicMock()

        update_stacks_mock = MagicMock()
        add_template_trigger_mock = MagicMock()
        add_code_trigger_mock = MagicMock()
        start_code_sync_mock = MagicMock()

        self.watch_manager._stop_code_sync = stop_code_sync_mock
        self.watch_manager._execute_infra_context = execute_infra_sync_mock
        self.watch_manager._update_stacks = update_stacks_mock
        self.watch_manager._add_template_triggers = add_template_trigger_mock
        self.watch_manager._add_code_triggers = add_code_trigger_mock
        self.watch_manager._start_code_sync = start_code_sync_mock

        self.watch_manager._skip_infra_syncs = True
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager._start()

        self.path_observer.start.assert_called_once_with()
        self.assertFalse(self.watch_manager._waiting_infra_sync)

        stop_code_sync_mock.assert_not_called()
        execute_infra_sync_mock.assert_not_called()
        update_stacks_mock.assert_not_called()
        add_template_trigger_mock.assert_not_called()
        add_code_trigger_mock.assert_not_called()
        start_code_sync_mock.assert_not_called()

        self.path_observer.unschedule_all.assert_not_called()

        self.path_observer.start.assert_called_once_with()

    def test_start_code_only_infra_sync_not_set(self):
        self.watch_manager._skip_infra_syncs = True
        self.watch_manager.queue_infra_sync()
        self.assertFalse(self.watch_manager._waiting_infra_sync)

    @patch("samcli.lib.sync.watch_manager.time.sleep")
    def test__start_infra_exception(self, sleep_mock):
        sleep_mock.side_effect = KeyboardInterrupt()

        stop_code_sync_mock = MagicMock()
        execute_infra_sync_mock = MagicMock()
        execute_infra_sync_mock.side_effect = Exception()

        update_stacks_mock = MagicMock()
        add_template_trigger_mock = MagicMock()
        add_code_trigger_mock = MagicMock()
        start_code_sync_mock = MagicMock()

        self.watch_manager._stop_code_sync = stop_code_sync_mock
        self.watch_manager._execute_infra_context = execute_infra_sync_mock
        self.watch_manager._update_stacks = update_stacks_mock
        self.watch_manager._add_template_triggers = add_template_trigger_mock
        self.watch_manager._add_code_triggers = add_code_trigger_mock
        self.watch_manager._start_code_sync = start_code_sync_mock

        self.watch_manager._waiting_infra_sync = True
        with self.assertRaises(KeyboardInterrupt):
            self.watch_manager._start()

        self.path_observer.start.assert_called_once_with()
        self.assertFalse(self.watch_manager._waiting_infra_sync)

        stop_code_sync_mock.assert_called_once_with()
        execute_infra_sync_mock.assert_called_once_with()
        add_template_trigger_mock.assert_called_once_with()

        update_stacks_mock.assert_not_called()
        add_code_trigger_mock.assert_not_called()
        start_code_sync_mock.assert_not_called()

        self.path_observer.unschedule_all.assert_called_once_with()

        self.path_observer.start.assert_called_once_with()

    def test_on_code_change_wrapper(self):
        flow1 = MagicMock()
        resource_id_mock = MagicMock()
        factory_mock = MagicMock()

        self.watch_manager._sync_flow_factory = factory_mock
        factory_mock.create_sync_flow.return_value = flow1

        callback = self.watch_manager._on_code_change_wrapper(resource_id_mock)

        callback()

        self.executor.add_delayed_sync_flow.assert_any_call(flow1, dedup=True, wait_time=ANY)

    def test_watch_sync_flow_exception_handler_missing_physical(self):
        sync_flow = MagicMock()
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=MissingPhysicalResourceError)
        sync_flow_exception.exception = exception
        sync_flow_exception.sync_flow = sync_flow

        queue_infra_sync_mock = MagicMock()
        self.watch_manager.queue_infra_sync = queue_infra_sync_mock

        self.watch_manager._watch_sync_flow_exception_handler(sync_flow_exception)

        queue_infra_sync_mock.assert_called_once_with()
