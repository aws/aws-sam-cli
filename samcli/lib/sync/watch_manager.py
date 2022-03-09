"""
WatchManager for Sync Watch Logic
"""
import logging
import time
import threading

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from samcli.lib.utils.colors import Colored
from samcli.lib.providers.exceptions import MissingCodeUri, MissingLocalDefinition

from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_all_resource_ids
from samcli.lib.utils.code_trigger_factory import CodeTriggerFactory
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.path_observer import HandlerObserver

from samcli.lib.sync.sync_flow_factory import SyncFlowFactory
from samcli.lib.sync.exceptions import InfraSyncRequiredError, MissingPhysicalResourceError, SyncFlowException
from samcli.lib.utils.resource_trigger import OnChangeCallback, TemplateTrigger
from samcli.lib.sync.continuous_sync_flow_executor import ContinuousSyncFlowExecutor

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.build.build_context import BuildContext

DEFAULT_WAIT_TIME = 1
LOG = logging.getLogger(__name__)


class WatchManager:
    _stacks: Optional[List[Stack]]
    _template: str
    _build_context: "BuildContext"
    _package_context: "PackageContext"
    _deploy_context: "DeployContext"
    _sync_flow_factory: Optional[SyncFlowFactory]
    _sync_flow_executor: ContinuousSyncFlowExecutor
    _executor_thread: Optional[threading.Thread]
    _observer: HandlerObserver
    _trigger_factory: Optional[CodeTriggerFactory]
    _waiting_infra_sync: bool
    _color: Colored
    _auto_dependency_layer: bool

    def __init__(
        self,
        template: str,
        build_context: "BuildContext",
        package_context: "PackageContext",
        deploy_context: "DeployContext",
        auto_dependency_layer: bool,
    ):
        """Manager for sync watch execution logic.
        This manager will observe template and its code resources.
        Automatically execute infra/code syncs when changes are detected.

        Parameters
        ----------
        template : str
            Template file path
        build_context : BuildContext
            BuildContext
        package_context : PackageContext
            PackageContext
        deploy_context : DeployContext
            DeployContext
        """
        self._stacks = None
        self._template = template
        self._build_context = build_context
        self._package_context = package_context
        self._deploy_context = deploy_context
        self._auto_dependency_layer = auto_dependency_layer

        self._sync_flow_factory = None
        self._sync_flow_executor = ContinuousSyncFlowExecutor()
        self._executor_thread = None

        self._observer = HandlerObserver()
        self._trigger_factory = None

        self._waiting_infra_sync = False
        self._color = Colored()

    def queue_infra_sync(self) -> None:
        """Queue up an infra structure sync.
        A simple bool flag is suffice
        """
        self._waiting_infra_sync = True

    def _update_stacks(self) -> None:
        """
        Reloads template and its stacks.
        Update all other member that also depends on the stacks.
        This should be called whenever there is a change to the template.
        """
        self._stacks = SamLocalStackProvider.get_stacks(self._template)[0]
        self._sync_flow_factory = SyncFlowFactory(
            self._build_context, self._deploy_context, self._stacks, self._auto_dependency_layer
        )
        self._sync_flow_factory.load_physical_id_mapping()
        self._trigger_factory = CodeTriggerFactory(self._stacks, Path(self._build_context.base_dir))

    def _add_code_triggers(self) -> None:
        """Create CodeResourceTrigger for all resources and add their handlers to observer"""
        if not self._stacks or not self._trigger_factory:
            return
        resource_ids = get_all_resource_ids(self._stacks)
        for resource_id in resource_ids:
            try:
                trigger = self._trigger_factory.create_trigger(resource_id, self._on_code_change_wrapper(resource_id))
            except (MissingCodeUri, MissingLocalDefinition):
                LOG.debug("CodeTrigger not created as CodeUri or DefinitionUri is missing for %s.", str(resource_id))
                continue

            if not trigger:
                continue
            self._observer.schedule_handlers(trigger.get_path_handlers())

    def _add_template_trigger(self) -> None:
        """Create TemplateTrigger and add its handlers to observer"""
        template_trigger = TemplateTrigger(self._template, lambda _=None: self.queue_infra_sync())
        self._observer.schedule_handlers(template_trigger.get_path_handlers())

    def _execute_infra_context(self) -> None:
        """Execute infrastructure sync"""
        self._build_context.set_up()
        self._build_context.run()
        self._package_context.run()
        self._deploy_context.run()

    def _start_code_sync(self) -> None:
        """Start SyncFlowExecutor in a separate thread."""
        if not self._executor_thread or not self._executor_thread.is_alive():
            self._executor_thread = threading.Thread(
                target=lambda: self._sync_flow_executor.execute(
                    exception_handler=self._watch_sync_flow_exception_handler
                )
            )
            self._executor_thread.start()

    def _stop_code_sync(self) -> None:
        """Blocking call that stops SyncFlowExecutor and waits for it to finish."""
        if self._executor_thread and self._executor_thread.is_alive():
            self._sync_flow_executor.stop()
            self._executor_thread.join()

    def start(self) -> None:
        """Start WatchManager and watch for changes to the template and its code resources."""

        # The actual execution is done in _start()
        # This is a wrapper for gracefully handling Ctrl+C or other termination cases.
        try:
            self.queue_infra_sync()
            self._start()
        except KeyboardInterrupt:
            LOG.info(self._color.cyan("Shutting down sync watch..."))
            self._observer.stop()
            self._stop_code_sync()
            LOG.info(self._color.green("Sync watch stopped."))

    def _start(self) -> None:
        """Start WatchManager and watch for changes to the template and its code resources."""
        self._observer.start()
        while True:
            if self._waiting_infra_sync:
                self._execute_infra_sync()
            time.sleep(1)

    def _execute_infra_sync(self) -> None:
        LOG.info(self._color.cyan("Queued infra sync. Wating for in progress code syncs to complete..."))
        self._waiting_infra_sync = False
        self._stop_code_sync()
        try:
            LOG.info(self._color.cyan("Starting infra sync."))
            self._execute_infra_context()
        except Exception as e:
            LOG.error(
                self._color.red("Failed to sync infra. Code sync is paused until template/stack is fixed."),
                exc_info=e,
            )
            # Unschedule all triggers and only add back the template one as infra sync is incorrect.
            self._observer.unschedule_all()
            self._add_template_trigger()
        else:
            # Update stacks and repopulate triggers
            # Trigger are not removed until infra sync is finished as there
            # can be code changes during infra sync.
            self._observer.unschedule_all()
            self._update_stacks()
            self._add_template_trigger()
            self._add_code_triggers()
            self._start_code_sync()
            LOG.info(self._color.green("Infra sync completed."))

    def _on_code_change_wrapper(self, resource_id: ResourceIdentifier) -> OnChangeCallback:
        """Wrapper method that generates a callback for code changes.

        Parameters
        ----------
        resource_id : ResourceIdentifier
            Resource that associates to the callback

        Returns
        -------
        OnChangeCallback
            Callback function
        """

        def on_code_change(_=None):
            sync_flow = self._sync_flow_factory.create_sync_flow(resource_id)
            if sync_flow and not self._waiting_infra_sync:
                self._sync_flow_executor.add_delayed_sync_flow(sync_flow, dedup=True, wait_time=DEFAULT_WAIT_TIME)

        return on_code_change

    def _watch_sync_flow_exception_handler(self, sync_flow_exception: SyncFlowException) -> None:
        """Exception handler for watch.
        Simply logs unhandled exceptions instead of failing the entire process.

        Parameters
        ----------
        sync_flow_exception : SyncFlowException
            SyncFlowException
        """
        exception = sync_flow_exception.exception
        if isinstance(exception, MissingPhysicalResourceError):
            LOG.warning(self._color.yellow("Missing physical resource. Infra sync will be started."))
            self.queue_infra_sync()
        elif isinstance(exception, InfraSyncRequiredError):
            LOG.warning(
                self._color.yellow(
                    f"Infra sync is required for {exception.resource_identifier} due to: "
                    + f"{exception.reason}. Infra sync will be started."
                )
            )
            self.queue_infra_sync()
        else:
            LOG.error(self._color.red("Code sync encountered an error."), exc_info=exception)
