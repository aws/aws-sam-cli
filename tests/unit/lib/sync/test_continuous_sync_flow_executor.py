from multiprocessing.managers import ValueProxy
from queue import Queue
from samcli.lib.sync.continuous_sync_flow_executor import ContinuousSyncFlowExecutor, DelayedSyncFlowTask
from samcli.lib.sync.sync_flow import SyncFlow

from botocore.exceptions import ClientError
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    SyncFlowException,
)
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch

from samcli.lib.sync.sync_flow_executor import (
    SyncFlowExecutor,
    SyncFlowResult,
    SyncFlowTask,
    default_exception_handler,
    HELP_TEXT_FOR_SYNC_INFRA,
)


class TestContinuousSyncFlowExecutor(TestCase):
    def setUp(self):
        self.thread_pool_executor_patch = patch("samcli.lib.sync.sync_flow_executor.ThreadPoolExecutor")
        self.thread_pool_executor_mock = self.thread_pool_executor_patch.start()
        self.thread_pool_executor = self.thread_pool_executor_mock.return_value
        self.thread_pool_executor.__enter__.return_value = self.thread_pool_executor
        self.lock_distributor_patch = patch("samcli.lib.sync.sync_flow_executor.LockDistributor")
        self.lock_distributor_mock = self.lock_distributor_patch.start()
        self.lock_distributor = self.lock_distributor_mock.return_value
        self.executor = ContinuousSyncFlowExecutor()

    def tearDown(self) -> None:
        self.thread_pool_executor_patch.stop()
        self.lock_distributor_patch.stop()

    @patch("samcli.lib.sync.continuous_sync_flow_executor.time.time")
    @patch("samcli.lib.sync.continuous_sync_flow_executor.DelayedSyncFlowTask")
    def test_add_delayed_sync_flow(self, task_mock, time_mock):
        add_sync_flow_task_mock = MagicMock()
        task = MagicMock()
        task_mock.return_value = task
        time_mock.return_value = 1000
        self.executor._add_sync_flow_task = add_sync_flow_task_mock
        sync_flow = MagicMock()

        self.executor.add_delayed_sync_flow(sync_flow, False, 15)

        task_mock.assert_called_once_with(sync_flow, False, 1000, 15)
        add_sync_flow_task_mock.assert_called_once_with(task)

    def test_add_sync_flow_task(self):
        sync_flow = MagicMock()
        task = DelayedSyncFlowTask(sync_flow, False, 1000, 15)

        self.executor._add_sync_flow_task(task)

        sync_flow.set_locks_with_distributor.assert_called_once_with(self.executor._lock_distributor)

        queue_task = self.executor._flow_queue.get()
        self.assertEqual(sync_flow, queue_task.sync_flow)

    def test_stop_without_manager(self):
        self.executor.stop()
        self.assertTrue(self.executor._stop_flag)

    def test_should_stop_without_manager(self):
        self.executor._stop_flag = True
        self.assertTrue(self.executor.should_stop())

    @patch("samcli.lib.sync.continuous_sync_flow_executor.time.time")
    @patch("samcli.lib.sync.sync_flow_executor.time.sleep")
    def test_execute_high_level_logic(self, sleep_mock, time_mock):
        exception_handler_mock = MagicMock()
        time_mock.return_value = 1001

        flow1 = MagicMock()
        flow2 = MagicMock()
        flow3 = MagicMock()

        task1 = DelayedSyncFlowTask(flow1, False, 1000, 0)
        task2 = DelayedSyncFlowTask(flow2, False, 1000, 0)
        task3 = DelayedSyncFlowTask(flow3, False, 1000, 0)

        result1 = SyncFlowResult(flow1, [flow3])

        future1 = MagicMock()
        future2 = MagicMock()
        future3 = MagicMock()

        exception1 = MagicMock(spec=Exception)
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        sync_flow_exception.sync_flow = flow2
        sync_flow_exception.exception = exception1

        future1.done.side_effect = [False, False, True]
        future1.exception.return_value = None
        future1.result.return_value = result1

        future2.done.side_effect = [False, False, False, True]
        future2.exception.return_value = sync_flow_exception

        future3.done.side_effect = [False, False, False, True]
        future3.exception.return_value = None

        self.thread_pool_executor.submit = MagicMock()
        self.thread_pool_executor.submit.side_effect = [future1, future2, future3]

        self.executor._flow_queue.put(task1)
        self.executor._flow_queue.put(task2)

        self.executor.add_sync_flow = MagicMock()
        self.executor.add_sync_flow.side_effect = lambda x: self.executor._flow_queue.put(task3)

        self.executor.should_stop = MagicMock()
        self.executor.should_stop.side_effect = [
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
        ]

        self.executor.execute(exception_handler=exception_handler_mock)

        self.thread_pool_executor.submit.assert_has_calls(
            [
                call(SyncFlowExecutor._sync_flow_execute_wrapper, flow1),
                call(SyncFlowExecutor._sync_flow_execute_wrapper, flow2),
                call(SyncFlowExecutor._sync_flow_execute_wrapper, flow3),
            ]
        )
        self.executor.add_sync_flow.assert_called_once_with(flow3)

        exception_handler_mock.assert_called_once_with(sync_flow_exception)
        self.assertEqual(len(sleep_mock.mock_calls), 10)
