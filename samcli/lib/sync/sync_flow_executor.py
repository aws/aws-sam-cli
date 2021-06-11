"""Executor for SyncFlows"""
import logging
import time

from queue import Queue
from typing import Callable, List, Optional, Union
from multiprocessing.managers import SyncManager, ValueProxy
from concurrent.futures import ThreadPoolExecutor, Future, ProcessPoolExecutor

from botocore.exceptions import ClientError
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    LayerPhysicalIdNotFoundError,
)

from samcli.lib.utils.lock_distributor import LockDistributor, LockDistributorType
from samcli.lib.sync.sync_flow import SyncFlow

LOG = logging.getLogger(__name__)

HELP_TEXT_FOR_SYNC_INFRA = " Try sam sync --infra or sam deploy."


def default_exception_handler(exception: Exception) -> None:
    """Default exception handler for SyncFlowExecutor
    This will try log and parse common SyncFlow exceptions.

    Parameters
    ----------
    exception : Exception
        Exception to be handled

    Raises
    ------
    exception
        Unhandled exception
    """
    if isinstance(exception, MissingPhysicalResourceError):
        LOG.error("Cannot find resource %s in remote.%s", exception.resource_identifier, HELP_TEXT_FOR_SYNC_INFRA)
    elif (
        isinstance(exception, ClientError)
        and exception.response.get("Error", dict()).get("Code", "") == "ResourceNotFoundException"
    ):
        LOG.error("Cannot find resource in remote.%s", HELP_TEXT_FOR_SYNC_INFRA)
        LOG.error(exception.response.get("Error", dict()).get("Message", ""))
    elif isinstance(exception, NoLayerVersionsFoundError):
        LOG.error("Cannot find any versions for layer %s.%s", exception.layer_name_arn, HELP_TEXT_FOR_SYNC_INFRA)
    elif isinstance(exception, LayerPhysicalIdNotFoundError):
        LOG.error(
            "Cannot find physical resource id for layer %s in all resources (%s).%s",
            exception.layer_name,
            exception.stack_resource_names,
            HELP_TEXT_FOR_SYNC_INFRA,
        )
    else:
        raise exception


class SyncFlowExecutor:
    """Executor for SyncFlows
    Can be used with ThreadPoolExecutor or ProcessPoolExecutor with/without manager
    """

    _flow_queue: Queue
    _executor: Union[ThreadPoolExecutor, ProcessPoolExecutor]
    _lock_distributor: LockDistributor
    _manager: Optional[SyncManager]
    _persistent: bool
    _exit_flag: Union[bool, ValueProxy]

    def __init__(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
        lock_distributor: Optional[LockDistributor] = None,
        manager: Optional[SyncManager] = None,
        flow_queue: Optional[Queue] = None,
        persistent: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        executor : ThreadPoolExecutor, optional
            Can be ThreadPoolExecutor or ProcessPoolExecutor, by default ThreadPoolExecutor()
        lock_distributor : LockDistributor, optional
            LockDistributor, by default LockDistributor(LockDistributorType.THREAD)
        manager : Optional[SyncManager], optional
            SyncManager to be used for cross process communication, by default None
        flow_queue : Queue, optional
            Queue for storing unexecuted SyncFlows, by default Queue()
        persistent : bool, optional
            Should executor stay running after finishing all SyncFlows in the queue, by default False
        """
        self._flow_queue = flow_queue if flow_queue else Queue()
        self._executor = executor if executor else ThreadPoolExecutor()
        self._lock_distributor = lock_distributor if lock_distributor else LockDistributor(LockDistributorType.THREAD)
        self._manager = manager
        self._persistent = persistent
        self._exit_flag = manager.Value("i", 0) if manager else False

    def add_sync_flow(self, sync_flow: SyncFlow) -> None:
        """Add a SyncFlow to queue to be executed
        Locks will be set with LockDistributor

        Parameters
        ----------
        sync_flow : SyncFlow
            SyncFlow to be executed
        """
        sync_flow.set_locks_with_distributor(self._lock_distributor)
        self._flow_queue.put(sync_flow)

    def exit(self, should_exit: bool = True) -> None:
        """Stop executor on the next available time.

        Parameters
        ----------
        should_exit : bool, optional
            True to stop the executor, False otherwise, by default True
        """
        if isinstance(self._exit_flag, ValueProxy):
            self._exit_flag.value = int(should_exit)
        else:
            self._exit_flag = should_exit

    def should_exit(self) -> bool:
        """
        Returns
        -------
        bool
            Should executor stop execution on the next available time.
        """
        return bool(self._exit_flag.value) if isinstance(self._exit_flag, ValueProxy) else self._exit_flag

    def execute(self, exception_handler: Optional[Callable[[Exception], None]] = default_exception_handler) -> None:
        """Stop blocking execution of the SyncFlows

        Parameters
        ----------
        exception_handler : Optional[Callable[[Exception], None]], optional
            Function to be called if an exception is raised during the execution of a SyncFlow,
            by default default_exception_handler.__func__
        """
        with self._executor:
            running_futures: List[Future] = list()

            while True:
                # Execute all pending sync flows
                while not self._flow_queue.empty():
                    sync_flow = self._flow_queue.get()
                    running_futures.append(self._executor.submit(sync_flow.execute))
                    LOG.debug("Syncing %s...", sync_flow.log_name)

                # Check for finished sync flows
                for future in list(running_futures):
                    if not future.done():
                        continue

                    exception = future.exception()
                    if exception and isinstance(exception, Exception) and exception_handler:
                        # Exception Handling
                        exception_handler(exception)
                    else:
                        # Add depentency sync flows to queue
                        dependent_sync_flows = future.result()
                        for dependent_sync_flow in dependent_sync_flows:
                            self.add_sync_flow(dependent_sync_flow)

                    running_futures.remove(future)

                # Exit execution if there are no running and pending sync flows
                if not self._persistent and not running_futures and self._flow_queue.empty():
                    LOG.debug("Not more SyncFlows in executor. Exiting.")
                    break

                if self.should_exit():
                    self.exit(should_exit=False)
                    LOG.debug("Exiting SyncFlow Executor due to exit flag.")
                    break

                # Sleep for a bit to cut down CPU utilization of this busy wait loop
                time.sleep(0.1)
