from multiprocessing.managers import ValueProxy
from queue import Queue
from samcli.lib.sync.sync_flow import SyncFlow

from botocore.exceptions import ClientError
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    SyncFlowException,
    MissingFunctionBuildDefinition,
    InvalidRuntimeDefinitionForFunction,
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


class TestSyncFlowExecutor(TestCase):
    def setUp(self):
        self.thread_pool_executor_patch = patch("samcli.lib.sync.sync_flow_executor.ThreadPoolExecutor")
        self.thread_pool_executor_mock = self.thread_pool_executor_patch.start()
        self.thread_pool_executor = self.thread_pool_executor_mock.return_value
        self.thread_pool_executor.__enter__.return_value = self.thread_pool_executor
        self.lock_distributor_patch = patch("samcli.lib.sync.sync_flow_executor.LockDistributor")
        self.lock_distributor_mock = self.lock_distributor_patch.start()
        self.lock_distributor = self.lock_distributor_mock.return_value
        self.executor = SyncFlowExecutor()

    def tearDown(self) -> None:
        self.thread_pool_executor_patch.stop()
        self.lock_distributor_patch.stop()

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_missing_physical_resource_error(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=MissingPhysicalResourceError)
        exception.resource_identifier = "Resource1"
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_called_once_with(
            "Cannot find resource %s in remote.%s", "Resource1", HELP_TEXT_FOR_SYNC_INFRA
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_valid(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=ClientError)
        exception.resource_identifier = "Resource1"
        exception.response = {"Error": {"Code": "ResourceNotFoundException", "Message": "MessageContent"}}
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_has_calls(
            [call("Cannot find resource in remote.%s", HELP_TEXT_FOR_SYNC_INFRA), call("MessageContent")]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_no_layer_versions_found(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=NoLayerVersionsFoundError)
        exception.layer_name_arn = "layer_name"
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_has_calls(
            [
                call(
                    "Cannot find any versions for layer %s.%s",
                    exception.layer_name_arn,
                    HELP_TEXT_FOR_SYNC_INFRA,
                )
            ]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_missing_function_build_exception(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=MissingFunctionBuildDefinition)
        exception.function_logical_id = "function_logical_id"
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_has_calls(
            [
                call(
                    "Cannot find build definition for function %s.%s",
                    exception.function_logical_id,
                    HELP_TEXT_FOR_SYNC_INFRA,
                )
            ]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_missing_local_definition(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=MissingLocalDefinition)
        exception.resource_identifier = "resource"
        exception.property_name = "property"
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_has_calls(
            [
                call(
                    "Resource %s does not have %s specified. Skipping the sync.%s",
                    exception.resource_identifier,
                    exception.property_name,
                    HELP_TEXT_FOR_SYNC_INFRA,
                )
            ]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_invalid_runtime_exception(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = MagicMock(spec=InvalidRuntimeDefinitionForFunction)
        exception.function_logical_id = "function_logical_id"
        sync_flow_exception.exception = exception

        default_exception_handler(sync_flow_exception)
        log_mock.error.assert_has_calls(
            [
                call(
                    "No Runtime information found for function resource named %s",
                    exception.function_logical_id,
                )
            ]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_invalid_code(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)
        exception = ClientError({"Error": {"Code": "RandomException", "Message": "MessageContent"}}, "")
        exception.resource_identifier = "Resource1"
        sync_flow_exception.exception = exception
        with self.assertRaises(ClientError):
            default_exception_handler(sync_flow_exception)

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_invalid_exception(self, log_mock):
        sync_flow_exception = MagicMock(spec=SyncFlowException)

        class RandomException(Exception):
            pass

        exception = RandomException()
        exception.resource_identifier = "Resource1"
        sync_flow_exception.exception = exception
        with self.assertRaises(RandomException):
            default_exception_handler(sync_flow_exception)

    @patch("samcli.lib.sync.sync_flow_executor.time.time")
    @patch("samcli.lib.sync.sync_flow_executor.SyncFlowTask")
    def test_add_sync_flow(self, task_mock, time_mock):
        add_sync_flow_task_mock = MagicMock()
        task = MagicMock()
        task_mock.return_value = task
        time_mock.return_value = 1000
        self.executor._add_sync_flow_task = add_sync_flow_task_mock
        sync_flow = MagicMock()

        self.executor.add_sync_flow(sync_flow, False)

        task_mock.assert_called_once_with(sync_flow, False)
        add_sync_flow_task_mock.assert_called_once_with(task)

    def test_add_sync_flow_task(self):
        sync_flow = MagicMock()
        task = SyncFlowTask(sync_flow, False)

        self.executor._add_sync_flow_task(task)

        sync_flow.set_locks_with_distributor.assert_called_once_with(self.executor._lock_distributor)

        queue_task = self.executor._flow_queue.get()
        self.assertEqual(sync_flow, queue_task.sync_flow)

    def test_add_sync_flow_task_dedup(self):
        sync_flow = MagicMock()

        task1 = SyncFlowTask(sync_flow, True)
        task2 = SyncFlowTask(sync_flow, True)

        self.executor._add_sync_flow_task(task1)
        self.executor._add_sync_flow_task(task2)

        sync_flow.set_locks_with_distributor.assert_called_once_with(self.executor._lock_distributor)

        queue_task = self.executor._flow_queue.get()
        self.assertEqual(sync_flow, queue_task.sync_flow)
        self.assertTrue(self.executor._flow_queue.empty())

    def test_is_running_without_manager(self):
        self.executor._running_flag = True
        self.assertTrue(self.executor.is_running())

    @patch("samcli.lib.sync.sync_flow_executor.time.time")
    @patch("samcli.lib.sync.sync_flow_executor.time.sleep")
    def test_execute_high_level_logic(self, sleep_mock, time_mock):
        exception_handler_mock = MagicMock()
        time_mock.return_value = 1001

        flow1 = MagicMock()
        flow2 = MagicMock()
        flow3 = MagicMock()

        task1 = SyncFlowTask(flow1, False)
        task2 = SyncFlowTask(flow2, False)
        task3 = SyncFlowTask(flow3, False)

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
        self.assertEqual(len(sleep_mock.mock_calls), 6)
