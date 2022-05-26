"""Executor for SyncFlows"""
import logging
import time

from queue import Queue
from typing import Callable, List, Optional, Set
from dataclasses import dataclass

from threading import RLock
from concurrent.futures import ThreadPoolExecutor, Future

from botocore.exceptions import ClientError

from samcli.lib.utils.colors import Colored
from samcli.lib.providers.exceptions import MissingLocalDefinition
from samcli.lib.sync.exceptions import (
    InfraSyncRequiredError,
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    SyncFlowException,
    MissingFunctionBuildDefinition,
    InvalidRuntimeDefinitionForFunction,
)

from samcli.lib.utils.lock_distributor import LockDistributor, LockDistributorType
from samcli.lib.sync.sync_flow import SyncFlow

LOG = logging.getLogger(__name__)

HELP_TEXT_FOR_SYNC_INFRA = " Try sam sync without --code or sam deploy."


@dataclass(frozen=True, eq=True)
class SyncFlowTask:
    """Data struct for individual SyncFlow execution tasks"""

    # SyncFlow to be executed
    sync_flow: SyncFlow

    # Should this task be ignored if there is a sync flow in the queue that's the same
    dedup: bool


@dataclass(frozen=True, eq=True)
class SyncFlowResult:
    """Data struct for SyncFlow results"""

    sync_flow: SyncFlow
    dependent_sync_flows: List[SyncFlow]


@dataclass(frozen=True, eq=True)
class SyncFlowFuture:
    """Data struct for SyncFlow futures"""

    sync_flow: SyncFlow
    future: Future


def default_exception_handler(sync_flow_exception: SyncFlowException) -> None:
    """Default exception handler for SyncFlowExecutor
    This will try log and parse common SyncFlow exceptions.

    Parameters
    ----------
    sync_flow_exception : SyncFlowException
        SyncFlowException containing exception to be handled and SyncFlow that raised it

    Raises
    ------
    exception
        Unhandled exception
    """
    exception = sync_flow_exception.exception
    if isinstance(exception, MissingPhysicalResourceError):
        LOG.error("Cannot find resource %s in remote.%s", exception.resource_identifier, HELP_TEXT_FOR_SYNC_INFRA)
    elif isinstance(exception, InfraSyncRequiredError):
        LOG.error(
            "Cannot code sync for %s due to: %s.%s",
            exception.resource_identifier,
            exception.reason,
            HELP_TEXT_FOR_SYNC_INFRA,
        )
    elif (
        isinstance(exception, ClientError)
        and exception.response.get("Error", dict()).get("Code", "") == "ResourceNotFoundException"
    ):
        LOG.error("Cannot find resource in remote.%s", HELP_TEXT_FOR_SYNC_INFRA)
        LOG.error(exception.response.get("Error", dict()).get("Message", ""))
    elif isinstance(exception, NoLayerVersionsFoundError):
        LOG.error("Cannot find any versions for layer %s.%s", exception.layer_name_arn, HELP_TEXT_FOR_SYNC_INFRA)
    elif isinstance(exception, MissingFunctionBuildDefinition):
        LOG.error(
            "Cannot find build definition for function %s.%s", exception.function_logical_id, HELP_TEXT_FOR_SYNC_INFRA
        )
    elif isinstance(exception, InvalidRuntimeDefinitionForFunction):
        LOG.error("No Runtime information found for function resource named %s", exception.function_logical_id)
    elif isinstance(exception, MissingLocalDefinition):
        LOG.error(
            "Resource %s does not have %s specified. Skipping the sync.%s",
            exception.resource_identifier,
            exception.property_name,
            HELP_TEXT_FOR_SYNC_INFRA,
        )
    else:
        raise exception


class SyncFlowExecutor:
    """Executor for SyncFlows
    Can be used with ThreadPoolExecutor or ProcessPoolExecutor with/without manager
    """

    _flow_queue: Queue
    _flow_queue_lock: RLock
    _lock_distributor: LockDistributor
    _running_flag: bool
    _color: Colored
    _running_futures: Set[SyncFlowFuture]

    def __init__(
        self,
    ) -> None:
        self._flow_queue = Queue()
        self._lock_distributor = LockDistributor(LockDistributorType.THREAD)
        self._running_flag = False
        self._flow_queue_lock = RLock()
        self._color = Colored()
        self._running_futures = set()

    def _add_sync_flow_task(self, task: SyncFlowTask) -> None:
        """Add SyncFlowTask to the queue

        Parameters
        ----------
        task : SyncFlowTask
            SyncFlowTask to be added.
        """
        # Lock flow_queue as check dedup and add is not atomic
        with self._flow_queue_lock:
            if task.dedup and task.sync_flow in [task.sync_flow for task in self._flow_queue.queue]:
                LOG.debug("Found the same SyncFlow in queue. Skip adding.")
                return

            task.sync_flow.set_locks_with_distributor(self._lock_distributor)
            self._flow_queue.put(task)

    def add_sync_flow(self, sync_flow: SyncFlow, dedup: bool = True) -> None:
        """Add a SyncFlow to queue to be executed
        Locks will be set with LockDistributor

        Parameters
        ----------
        sync_flow : SyncFlow
            SyncFlow to be executed
        dedup : bool
            SyncFlow will not be added if this flag is True and has a duplicate in the queue
        """
        self._add_sync_flow_task(SyncFlowTask(sync_flow, dedup))

    def is_running(self) -> bool:
        """
        Returns
        -------
        bool
            Is executor running
        """
        return self._running_flag

    def _can_exit(self) -> bool:
        """
        Returns
        -------
        bool
            Can executor be safely exited
        """
        return not self._running_futures and self._flow_queue.empty()

    def execute(
        self, exception_handler: Optional[Callable[[SyncFlowException], None]] = default_exception_handler
    ) -> None:
        """Blocking execution of the SyncFlows

        Parameters
        ----------
        exception_handler : Optional[Callable[[Exception], None]], optional
            Function to be called if an exception is raised during the execution of a SyncFlow,
            by default default_exception_handler.__func__
        """
        self._running_flag = True
        with ThreadPoolExecutor() as executor:
            self._running_futures.clear()
            while True:

                self._execute_step(executor, exception_handler)

                # Exit execution if there are no running and pending sync flows
                if self._can_exit():
                    LOG.debug("No more SyncFlows in executor. Stopping.")
                    break

                # Sleep for a bit to cut down CPU utilization of this busy wait loop
                time.sleep(0.1)
        self._running_flag = False

    def _execute_step(
        self,
        executor: ThreadPoolExecutor,
        exception_handler: Optional[Callable[[SyncFlowException], None]],
    ) -> None:
        """A single step in the execution flow

        Parameters
        ----------
        executor : ThreadPoolExecutor
            THreadPoolExecutor to be used for execution
        exception_handler : Optional[Callable[[SyncFlowException], None]]
            Exception handler
        """
        # Execute all pending sync flows
        with self._flow_queue_lock:
            # Putting nonsubmitted tasks into this deferred tasks list
            # to avoid modifying the queue while emptying it
            deferred_tasks = list()

            # Go through all queued tasks and try to execute them
            while not self._flow_queue.empty():
                sync_flow_task: SyncFlowTask = self._flow_queue.get()

                sync_flow_future = self._submit_sync_flow_task(executor, sync_flow_task)

                # sync_flow_future can be None if the task cannot be submitted currently
                # Put it into deferred_tasks and add all of them at the end to avoid endless loop
                if sync_flow_future:
                    self._running_futures.add(sync_flow_future)
                    LOG.info(self._color.cyan(f"Syncing {sync_flow_future.sync_flow.log_name}..."))
                else:
                    deferred_tasks.append(sync_flow_task)

            # Add tasks that cannot be executed yet
            for task in deferred_tasks:
                self._add_sync_flow_task(task)

        # Check for finished sync flows
        for sync_flow_future in set(self._running_futures):
            if self._handle_result(sync_flow_future, exception_handler):
                self._running_futures.remove(sync_flow_future)

    def _submit_sync_flow_task(
        self, executor: ThreadPoolExecutor, sync_flow_task: SyncFlowTask
    ) -> Optional[SyncFlowFuture]:
        """Submit SyncFlowTask to be executed by ThreadPoolExecutor
        and return its future

        Parameters
        ----------
        executor : ThreadPoolExecutor
            THreadPoolExecutor to be used for execution
        sync_flow_task : SyncFlowTask
            SyncFlowTask to be executed.

        Returns
        -------
        Optional[SyncFlowFuture]
            Returns SyncFlowFuture generated by the SyncFlowTask.
            Can be None if the task cannot be executed yet.
        """
        sync_flow = sync_flow_task.sync_flow

        # Check whether the same sync flow is already running or not
        if sync_flow in [future.sync_flow for future in self._running_futures]:
            return None

        sync_flow_future = SyncFlowFuture(
            sync_flow=sync_flow, future=executor.submit(SyncFlowExecutor._sync_flow_execute_wrapper, sync_flow)
        )

        return sync_flow_future

    def _handle_result(
        self, sync_flow_future: SyncFlowFuture, exception_handler: Optional[Callable[[SyncFlowException], None]]
    ) -> bool:
        """Checks and handles the result of a SyncFlowFuture

        Parameters
        ----------
        sync_flow_future : SyncFlowFuture
            The SyncFlowFuture that needs to be handled
        exception_handler : Optional[Callable[[SyncFlowException], None]]
            Exception handler that will be called if an exception is raised within the SyncFlow

        Returns
        -------
        bool
            Returns True if the SyncFlowFuture was finished and successfully handled, False otherwise.
        """
        future = sync_flow_future.future

        if not future.done():
            return False

        exception = future.exception()

        if exception and isinstance(exception, SyncFlowException) and exception_handler:
            # Exception handling
            exception_handler(exception)
        else:
            # Add dependency sync flows to queue
            sync_flow_result: SyncFlowResult = future.result()
            for dependent_sync_flow in sync_flow_result.dependent_sync_flows:
                self.add_sync_flow(dependent_sync_flow)
            LOG.info(self._color.green(f"Finished syncing {sync_flow_result.sync_flow.log_name}."))
        return True

    @staticmethod
    def _sync_flow_execute_wrapper(sync_flow: SyncFlow) -> SyncFlowResult:
        """Simple wrapper method for executing SyncFlow and converting all Exceptions into SyncFlowException

        Parameters
        ----------
        sync_flow : SyncFlow
            SyncFlow to be executed

        Returns
        -------
        SyncFlowResult
            SyncFlowResult for the SyncFlow executed

        Raises
        ------
        SyncFlowException
        """
        dependent_sync_flows = []
        try:
            dependent_sync_flows = sync_flow.execute()
        except ClientError as e:
            if e.response.get("Error", dict()).get("Code", "") == "ResourceNotFoundException":
                raise SyncFlowException(sync_flow, MissingPhysicalResourceError()) from e
            raise SyncFlowException(sync_flow, e) from e
        except Exception as e:
            raise SyncFlowException(sync_flow, e) from e
        return SyncFlowResult(sync_flow=sync_flow, dependent_sync_flows=dependent_sync_flows)
