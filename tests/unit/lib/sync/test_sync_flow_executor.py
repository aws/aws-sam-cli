from multiprocessing.managers import ValueProxy
from queue import Queue

from botocore.exceptions import ClientError
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    LayerPhysicalIdNotFoundError,
)
from samcli.lib.providers.provider import ResourceIdentifier
from unittest import TestCase
from unittest.mock import ANY, MagicMock, call, patch

from samcli.lib.sync.sync_flow import SyncFlow, ResourceAPICall
from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow
from samcli.lib.utils.lock_distributor import LockChain

from samcli.lib.sync.sync_flow_executor import SyncFlowExecutor, default_exception_handler, HELP_TEXT_FOR_SYNC_INFRA


class TestSyncFlowExecutor(TestCase):
    def create_executor(self):
        factory = SyncFlowExecutor(
            executor=MagicMock(), lock_distributor=MagicMock(), manager=None, flow_queue=Queue(), persistent=False
        )
        return factory

    def create_executor_with_manager(self):
        manager_mock = MagicMock()
        exit_flag_mock = MagicMock(spec=ValueProxy)
        exit_flag_mock.value = 0
        manager_mock.Value.return_value = exit_flag_mock
        factory = SyncFlowExecutor(
            executor=MagicMock(),
            lock_distributor=MagicMock(),
            manager=manager_mock,
            flow_queue=Queue(),
            persistent=False,
        )
        return factory

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_missing_physical_resource_error(self, log_mock):
        exception = MagicMock(spec=MissingPhysicalResourceError)
        exception.resource_identifier = "Resource1"
        default_exception_handler(exception)
        log_mock.error.assert_called_once_with(
            "Cannot find resource %s in remote.%s", "Resource1", HELP_TEXT_FOR_SYNC_INFRA
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_valid(self, log_mock):
        exception = MagicMock(spec=ClientError)
        exception.resource_identifier = "Resource1"
        exception.response = {"Error": {"Code": "ResourceNotFoundException", "Message": "MessageContent"}}
        default_exception_handler(exception)
        log_mock.error.assert_has_calls(
            [call("Cannot find resource in remote.%s", HELP_TEXT_FOR_SYNC_INFRA), call("MessageContent")]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_no_layer_versions_found(self, log_mock):
        exception = MagicMock(spec=NoLayerVersionsFoundError)
        exception.layer_name_arn = "layer_name"
        default_exception_handler(exception)
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
    def test_default_exception_layer_physical_id_not_found(self, log_mock):
        exception = MagicMock(spec=LayerPhysicalIdNotFoundError)
        exception.layer_name = "LayerName"
        exception.stack_resource_names = ["ResourceA", "ResourceB"]
        default_exception_handler(exception)
        log_mock.error.assert_has_calls(
            [
                call(
                    "Cannot find physical resource id for layer %s in all resources (%s).%s",
                    exception.layer_name,
                    exception.stack_resource_names,
                    HELP_TEXT_FOR_SYNC_INFRA,
                )
            ]
        )

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_invalid_code(self, log_mock):
        exception = ClientError({"Error": {"Code": "RandomException", "Message": "MessageContent"}}, "")
        exception.resource_identifier = "Resource1"
        with self.assertRaises(ClientError):
            default_exception_handler(exception)

    @patch("samcli.lib.sync.sync_flow_executor.LOG")
    def test_default_exception_handler_client_error_invalid_exception(self, log_mock):
        class RandomException(Exception):
            pass

        exception = RandomException()
        exception.resource_identifier = "Resource1"
        with self.assertRaises(RandomException):
            default_exception_handler(exception)

    def test_add_sync_flow(self):
        executor = self.create_executor()
        sync_flow = MagicMock()
        executor.add_sync_flow(sync_flow)
        sync_flow.set_locks_with_distributor.assert_called_once_with(executor._lock_distributor)
        self.assertEqual(executor._flow_queue.get(), sync_flow)

    def test_exit_without_manager(self):
        executor = self.create_executor()
        executor.exit()
        self.assertTrue(executor._exit_flag)

    def test_exit_with_manager(self):
        executor = self.create_executor_with_manager()
        executor.exit()
        self.assertTrue(executor._exit_flag.value)

    def test_should_exit_without_manager(self):
        executor = self.create_executor()
        executor._exit_flag = True
        self.assertTrue(executor.should_exit())

    def test_should_exit_with_manager(self):
        executor = self.create_executor_with_manager()
        executor._exit_flag.value = 1
        self.assertTrue(executor.should_exit())

    @patch("samcli.lib.sync.sync_flow_executor.time.sleep")
    def test_execute(self, sleep_mock):
        exception_handler_mock = MagicMock()
        executor = self.create_executor()
        flow1 = MagicMock()
        flow2 = MagicMock()
        flow3 = MagicMock()

        future1 = MagicMock()
        future2 = MagicMock()
        future3 = MagicMock()

        exception1 = MagicMock(spec=Exception)

        future1.done.side_effect = [False, False, True]
        future1.exception.return_value = None
        future1.result.return_value = [flow3]

        future2.done.side_effect = [False, False, False, True]
        future2.exception.return_value = exception1

        future3.done.side_effect = [False, False, False, True]
        future3.exception.return_value = None

        executor._executor.submit = MagicMock()
        executor._executor.submit.side_effect = [future1, future2, future3]

        executor._flow_queue.put(flow1)
        executor._flow_queue.put(flow2)

        executor.add_sync_flow = MagicMock()
        executor.add_sync_flow.side_effect = lambda x: executor._flow_queue.put(flow3)

        executor.should_exit = MagicMock()
        executor.should_exit.return_value = False

        executor.execute(exception_handler=exception_handler_mock)

        executor._executor.submit.assert_has_calls([call(flow1.execute), call(flow2.execute), call(flow3.execute)])
        executor.add_sync_flow.assert_called_once_with(flow3)

        exception_handler_mock.assert_called_once_with(exception1)
        self.assertEqual(len(executor.should_exit.mock_calls), 6)
