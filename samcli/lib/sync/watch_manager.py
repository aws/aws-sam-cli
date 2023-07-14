"""
WatchManager for Sync Watch Logic
"""
import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Set

from samcli.lib.providers.exceptions import InvalidTemplateFile, MissingCodeUri, MissingLocalDefinition
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_all_resource_ids
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.sync.continuous_sync_flow_executor import ContinuousSyncFlowExecutor
from samcli.lib.sync.exceptions import InfraSyncRequiredError, MissingPhysicalResourceError, SyncFlowException
from samcli.lib.sync.infra_sync_executor import InfraSyncExecutor, InfraSyncResult
from samcli.lib.sync.sync_flow_factory import SyncFlowFactory
from samcli.lib.utils.code_trigger_factory import CodeTriggerFactory
from samcli.lib.utils.colors import Colored, Colors
from samcli.lib.utils.path_observer import HandlerObserver
from samcli.lib.utils.resource_trigger import OnChangeCallback, TemplateTrigger

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.sync.sync_context import SyncContext

DEFAULT_WAIT_TIME = 1
LOG = logging.getLogger(__name__)


class WatchManager:
    _stacks: Optional[List[Stack]]
    _template: str
    _build_context: "BuildContext"
    _package_context: "PackageContext"
    _deploy_context: "DeployContext"
    _sync_context: "SyncContext"
    _sync_flow_factory: Optional[SyncFlowFactory]
    _sync_flow_executor: ContinuousSyncFlowExecutor
    _executor_thread: Optional[threading.Thread]
    _observer: HandlerObserver
    _trigger_factory: Optional[CodeTriggerFactory]
    _waiting_infra_sync: bool
    _color: Colored
    _auto_dependency_layer: bool
    _disable_infra_syncs: bool

    def __init__(
        self,
        template: str,
        build_context: "BuildContext",
        package_context: "PackageContext",
        deploy_context: "DeployContext",
        sync_context: "SyncContext",
        auto_dependency_layer: bool,
        disable_infra_syncs: bool,
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
        self._sync_context = sync_context
        self._auto_dependency_layer = auto_dependency_layer
        self._disable_infra_syncs = disable_infra_syncs

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
        if self._disable_infra_syncs:
            LOG.info(
                self._color.color_log(
                    msg="You have enabled the --code flag, which limits sam sync updates to code changes only. To do a "
                    "complete infrastructure and code sync, remove the --code flag.",
                    color=Colors.WARNING,
                ),
                extra=dict(markup=True),
            )
            return
        self._waiting_infra_sync = True

    def _update_stacks(self) -> None:
        """
        Reloads template and its stacks.
        Update all other member that also depends on the stacks.
        This should be called whenever there is a change to the template.
        """
        self._stacks = SamLocalStackProvider.get_stacks(self._template, use_sam_transform=False)[0]
        self._sync_flow_factory = SyncFlowFactory(
            self._build_context,
            self._deploy_context,
            self._sync_context,
            self._stacks,
            self._auto_dependency_layer,
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
                LOG.warning(
                    self._color.color_log(
                        msg="CodeTrigger not created as CodeUri or DefinitionUri is missing for %s.",
                        color=Colors.WARNING,
                    ),
                    str(resource_id),
                    extra=dict(markup=True),
                )
                continue

            if not trigger:
                continue
            self._observer.schedule_handlers(trigger.get_path_handlers())

    def _add_template_triggers(self) -> None:
        """Create TemplateTrigger and add its handlers to observer"""
        stacks = SamLocalStackProvider.get_stacks(self._template, use_sam_transform=False)[0]
        for stack in stacks:
            template = stack.location
            template_trigger = TemplateTrigger(template, stack.name, lambda _=None: self.queue_infra_sync())
            try:
                template_trigger.validate_template()
            except InvalidTemplateFile:
                LOG.warning(
                    self._color.color_log(msg="Template validation failed for %s in %s", color=Colors.WARNING),
                    template,
                    stack.name,
                    extra=dict(markup=True),
                )

            self._observer.schedule_handlers(template_trigger.get_path_handlers())

    def _execute_infra_context(self, first_sync: bool = False) -> InfraSyncResult:
        """Execute infrastructure sync

        Returns
        ----------
        InfraSyncResult
            Returns information containing whether infra sync executed plus resources to do code sync on
        """
        self._infra_sync_executor = InfraSyncExecutor(
            self._build_context, self._package_context, self._deploy_context, self._sync_context
        )
        return self._infra_sync_executor.execute_infra_sync(first_sync)

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
            if self._disable_infra_syncs:
                self._start_sync()
                LOG.info(
                    self._color.color_log(msg="Sync watch started.", color=Colors.SUCCESS), extra=dict(markup=True)
                )
            self._start()
        except KeyboardInterrupt:
            LOG.info(
                self._color.color_log(msg="Shutting down sync watch...", color=Colors.PROGRESS), extra=dict(markup=True)
            )
            self._observer.stop()
            self._stop_code_sync()
            LOG.info(self._color.color_log(msg="Sync watch stopped.", color=Colors.SUCCESS), extra=dict(markup=True))

    def _start(self) -> None:
        """Start WatchManager and watch for changes to the template and its code resources."""
        first_sync = True
        self._observer.start()
        while True:
            if self._waiting_infra_sync:
                self._execute_infra_sync(first_sync)
            first_sync = False
            time.sleep(1)

    def _start_sync(self) -> None:
        """Update stacks and populate all triggers"""
        self._observer.unschedule_all()
        self._update_stacks()
        self._add_template_triggers()
        self._add_code_triggers()
        self._start_code_sync()

    def _execute_infra_sync(self, first_sync: bool = False) -> None:
        """Logic to execute infra sync."""
        LOG.info(
            self._color.color_log(
                msg="Queued infra sync. Waiting for in progress code syncs to complete...", color=Colors.PROGRESS
            ),
            extra=dict(markup=True),
        )
        self._waiting_infra_sync = False
        self._stop_code_sync()
        try:
            LOG.info(self._color.color_log(msg="Starting infra sync.", color=Colors.PROGRESS), extra=dict(markup=True))
            infra_sync_result = self._execute_infra_context(first_sync)
        except Exception as e:
            LOG.error(
                self._color.color_log(
                    msg="Failed to sync infra. Code sync is paused until template/stack is fixed.", color=Colors.FAILURE
                ),
                exc_info=e,
                extra=dict(markup=True),
            )
            # Unschedule all triggers and only add back the template one as infra sync is incorrect.
            self._observer.unschedule_all()
            self._add_template_triggers()
        else:
            # Update stacks and repopulate triggers
            # Trigger are not removed until infra sync is finished as there
            # can be code changes during infra sync.
            self._start_sync()

            if not infra_sync_result.infra_sync_executed:
                # This is for initiating code sync for all resources
                # To improve: only initiate code syncs for ones with template changes
                self._queue_up_code_syncs(infra_sync_result.code_sync_resources)
                LOG.info(
                    self._color.color_log(
                        msg="Skipped infra sync as the local template is in sync with the cloud template.",
                        color=Colors.SUCCESS,
                    ),
                    extra=dict(markup=True),
                )
                if len(infra_sync_result.code_sync_resources) != 0:
                    LOG.info("Required code syncs are queued up.")
            else:
                LOG.info(
                    self._color.color_log(msg="Infra sync completed.", color=Colors.SUCCESS), extra=dict(markup=True)
                )

    def _queue_up_code_syncs(self, resource_ids_with_code_sync: Set[ResourceIdentifier]) -> None:
        """
        For ther given resource IDs, create sync flow tasks in the queue

        Parameters
        ----------
        resource_ids_with_code_sync: Set[ResourceIdentifier]
            The set of resource IDs to be synced
        """
        if not self._sync_flow_factory:
            return
        for resource_id in resource_ids_with_code_sync:
            sync_flow = self._sync_flow_factory.create_sync_flow(resource_id, self._build_context.build_result)
            if sync_flow:
                self._sync_flow_executor.add_delayed_sync_flow(sync_flow)

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
            LOG.warning(
                self._color.color_log(
                    msg="Missing physical resource. Infra sync will be started.", color=Colors.WARNING
                ),
                extra=dict(markup=True),
            )
            self.queue_infra_sync()
        elif isinstance(exception, InfraSyncRequiredError):
            LOG.warning(
                self._color.yellow(
                    f"Infra sync is required for {exception.resource_identifier} due to: "
                    + f"{exception.reason}. Infra sync will be started."
                ),
                extra=dict(markup=True),
            )
            self.queue_infra_sync()
        else:
            LOG.error(
                self._color.color_log(msg="Code sync encountered an error.", color=Colors.FAILURE),
                exc_info=exception,
                extra=dict(markup=True),
            )
