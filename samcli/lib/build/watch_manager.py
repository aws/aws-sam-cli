"""
BuildWatchManager for Build Watch Logic
"""

import logging
import platform
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from watchdog.events import EVENT_TYPE_MODIFIED, EVENT_TYPE_OPENED, FileSystemEvent

from samcli.lib.providers.exceptions import MissingCodeUri, MissingLocalDefinition
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_all_resource_ids
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.code_trigger_factory import CodeTriggerFactory
from samcli.lib.utils.colors import Colored, Colors
from samcli.lib.utils.path_observer import HandlerObserver
from samcli.lib.utils.resource_trigger import OnChangeCallback
from samcli.local.lambdafn.exceptions import ResourceNotFound

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.build.build_context import BuildContext

DEFAULT_BUILD_WAIT_TIME = 1
LOG = logging.getLogger(__name__)


class BuildWatchManager:
    """Manager for build watch execution logic.
    This manager will observe template and its code resources.
    Automatically execute builds when changes are detected.
    
    Follows the same patterns as WatchManager but adapted for build operations.
    """
    
    _stacks: Optional[List[Stack]]
    _template: str
    _build_context: "BuildContext"
    _observer: HandlerObserver
    _trigger_factory: Optional[CodeTriggerFactory]
    _waiting_build: bool
    _build_timer: Optional[threading.Timer]
    _build_lock: threading.Lock
    _color: Colored
    _watch_exclude: Dict[str, List[str]]

    def __init__(
        self,
        template: str,
        build_context: "BuildContext",
        watch_exclude: Dict[str, List[str]],
    ):
        """Manager for build watch execution logic.
        This manager will observe template and its code resources.
        Automatically execute builds when changes are detected.

        Parameters
        ----------
        template : str
            Template file path
        build_context : BuildContext
            BuildContext for build operations
        watch_exclude : Dict[str, List[str]]
            Dictionary of watch exclusion patterns per resource
        """
        self._stacks = None
        self._template = template
        self._build_context = build_context
        
        self._observer = HandlerObserver()
        self._trigger_factory = None
        
        self._waiting_build = False
        self._build_timer = None
        self._build_lock = threading.Lock()
        self._color = Colored()
        
        # Build smart exclusions based on build configuration
        self._watch_exclude = self._build_smart_exclusions(build_context, watch_exclude)
        
        # Validate safety upfront
        self._validate_watch_safety(build_context)

    def _build_smart_exclusions(
        self, build_context: "BuildContext", watch_exclude: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Build exclusions that prevent recursion based on build config"""
        from samcli.lib.utils.resource_trigger import DEFAULT_WATCH_IGNORED_RESOURCES
        
        # Base exclusions from resource_trigger.py
        base_exclusions = [*DEFAULT_WATCH_IGNORED_RESOURCES]
        
        # Add build-specific exclusions
        if build_context.build_in_source:
            base_exclusions.extend([
                r"^.*\.pyc$",           # Python bytecode
                r"^.*__pycache__.*$",   # Python cache
                r"^.*\.class$",         # Java classes  
                r"^.*target/.*$",       # Maven target
                r"^.*build/.*$",        # Gradle build
            ])
        
        # Exclude cache directory if under project
        cache_exclusions = self._get_cache_exclusions(build_context)
        base_exclusions.extend(cache_exclusions)
        
        # Exclude build directory if under project
        build_exclusions = self._get_build_exclusions(build_context)
        base_exclusions.extend(build_exclusions)
        
        # Apply base exclusions to all resources, merging with user-provided exclusions
        result = {}
        for resource_id, user_excludes in watch_exclude.items():
            result[resource_id] = base_exclusions + user_excludes
        
        # For resources not specified by user, use base exclusions
        return result if result else {"*": base_exclusions}

    def _get_cache_exclusions(self, build_context: "BuildContext") -> List[str]:
        """Exclude cache directory from watching"""
        cache_dir = Path(build_context.cache_dir).resolve()
        base_dir = Path(build_context.base_dir).resolve()
        
        try:
            # If cache_dir is under base_dir, add it to exclusions  
            rel_cache_path = cache_dir.relative_to(base_dir)
            return [f"^.*{re.escape(str(rel_cache_path))}.*$"]
        except ValueError:
            # cache_dir is outside base_dir, no need to exclude
            return []

    def _get_build_exclusions(self, build_context: "BuildContext") -> List[str]:
        """Exclude build directory from watching"""
        build_dir = Path(build_context.build_dir).resolve()
        base_dir = Path(build_context.base_dir).resolve()
        
        try:
            # If build_dir is under base_dir, add it to exclusions  
            rel_build_path = build_dir.relative_to(base_dir)
            return [f"^.*{re.escape(str(rel_build_path))}.*$"]
        except ValueError:
            # build_dir is outside base_dir, no need to exclude
            return []

    def _validate_watch_safety(self, build_context: "BuildContext") -> None:
        """Validate that watch won't cause recursion issues"""
        base_dir = Path(build_context.base_dir).resolve()
        cache_dir = Path(build_context.cache_dir).resolve()
        build_dir = Path(build_context.build_dir).resolve()
        
        warnings = []
        
        # Check if cache dir is under a source directory
        if build_context.build_in_source:
            try:
                if base_dir in cache_dir.parents:
                    warnings.append(
                        f"Cache directory {cache_dir} is under project directory {base_dir}. "
                        "This may cause build loops."
                    )
            except (OSError, ValueError):
                pass
        
        # Check if build dir is under base dir when not using default
        default_build_dir = base_dir / ".aws-sam" / "build"
        if build_dir != default_build_dir:
            try:
                if base_dir in build_dir.parents:
                    warnings.append(
                        f"Custom build directory {build_dir} is under project directory. "
                        "This may cause watch recursion."
                    )
            except (OSError, ValueError):
                pass
        
        # Log warnings but don't fail - let users proceed with caution
        for warning in warnings:
            LOG.warning(self._color.yellow(f"Build watch safety warning: {warning}"))

    def queue_build(self) -> None:
        """Queue up a build operation.
        A simple bool flag is sufficient for immediate builds (like initial build or template changes)
        """
        self._waiting_build = True

    def queue_debounced_build(self, wait_time: float = DEFAULT_BUILD_WAIT_TIME) -> None:
        """Queue up a debounced build operation to handle rapid file changes.
        
        Parameters
        ----------
        wait_time : float
            Time to wait before executing build (allows for batching multiple changes)
        """
        with self._build_lock:
            # Cancel any pending build timer
            if self._build_timer and self._build_timer.is_alive():
                self._build_timer.cancel()
            
            # Schedule new build after wait_time
            self._build_timer = threading.Timer(wait_time, self._execute_debounced_build)
            self._build_timer.start()
            LOG.debug(f"Debounced build scheduled in {wait_time} seconds")

    def _execute_debounced_build(self) -> None:
        """Execute the debounced build by setting the waiting flag"""
        with self._build_lock:
            self._waiting_build = True
            LOG.debug("Debounced build timer triggered")

    def _update_stacks(self) -> None:
        """
        Reloads template and its stacks.
        Update all other members that also depend on the stacks.
        This should be called whenever there is a change to the template.
        """
        self._stacks = SamLocalStackProvider.get_stacks(self._template, use_sam_transform=False)[0]
        self._trigger_factory = CodeTriggerFactory(self._stacks, Path(self._build_context.base_dir))

    def _add_code_triggers(self) -> None:
        """Create CodeResourceTrigger for all resources and add their handlers to observer"""
        if not self._stacks or not self._trigger_factory:
            return
        resource_ids = get_all_resource_ids(self._stacks)
        for resource_id in resource_ids:
            try:
                # Get exclusions for this specific resource, or use global exclusions
                additional_excludes = self._watch_exclude.get(str(resource_id), self._watch_exclude.get("*", []))
                trigger = self._trigger_factory.create_trigger(
                    resource_id, self._on_code_change_wrapper(resource_id), additional_excludes
                )
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
            except ResourceNotFound:
                LOG.warning(
                    self._color.color_log(
                        msg="CodeTrigger not created as %s is not found or is with a S3 Location.",
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
        """Create template file watcher with polling fallback"""
        from watchdog.events import FileSystemEventHandler
        
        template_path = Path(self._template).resolve()
        LOG.info(f"Setting up template monitoring for {template_path}")
        
        # Create a custom event handler class
        class TemplateEventHandler(FileSystemEventHandler):
            def __init__(self, manager: "BuildWatchManager", template_path: Path):
                self.manager = manager
                self.template_path = template_path
            
            def on_any_event(self, event: FileSystemEvent) -> None:
                if event and hasattr(event, 'src_path'):
                    event_path = Path(event.src_path).resolve()
                    if event_path == self.template_path:
                        LOG.info(
                            self.manager._color.color_log(
                                msg=f"Template change detected: {event.event_type} on {event.src_path}",
                                color=Colors.PROGRESS
                            ),
                            extra=dict(markup=True)
                        )
                        self.manager.queue_build()
        
        template_handler = TemplateEventHandler(self, template_path)
        
        # Create PathHandler for the template directory
        from samcli.lib.utils.path_observer import PathHandler
        template_path_handler = PathHandler(
            path=template_path.parent,
            event_handler=template_handler,
            recursive=False
        )
        
        self._observer.schedule_handlers([template_path_handler])
        LOG.info(f"Template pattern watcher registered for {template_path}")
        
        # Add periodic template check as fallback
        self._start_template_polling()
    
    def _start_template_polling(self) -> None:
        """Start periodic template file checking as fallback"""
        template_path = Path(self._template).resolve()
        
        if not hasattr(self, '_template_mtime'):
            try:
                self._template_mtime = template_path.stat().st_mtime
            except OSError:
                self._template_mtime = 0
        
        def check_template_periodically() -> None:
            while True:
                try:
                    current_mtime = template_path.stat().st_mtime
                    if current_mtime != self._template_mtime:
                        LOG.info(
                            self._color.color_log(
                                msg="Template modification detected via polling. Starting build...",
                                color=Colors.PROGRESS
                            ),
                            extra=dict(markup=True)
                        )
                        self._template_mtime = current_mtime
                        self.queue_build()
                except OSError:
                    pass
                time.sleep(2)  # Check every 2 seconds
        
        # Start polling in a daemon thread
        polling_thread = threading.Thread(target=check_template_periodically, daemon=True)
        polling_thread.start()
        LOG.debug("Template polling fallback started")

    def start(self) -> None:
        """Start BuildWatchManager and watch for changes to the template and its code resources."""

        # The actual execution is done in _start()
        # This is a wrapper for gracefully handling Ctrl+C or other termination cases.
        try:
            self.queue_build()
            self._start_watch()
            LOG.info(
                self._color.color_log(msg="Build watch started.", color=Colors.SUCCESS), extra=dict(markup=True)
            )
            self._start()
        except KeyboardInterrupt:
            LOG.info(
                self._color.color_log(
                    msg="Shutting down build watch...", color=Colors.PROGRESS
                ), extra=dict(markup=True)
            )
            self._observer.stop()
            # Cancel any pending build timer
            with self._build_lock:
                if self._build_timer and self._build_timer.is_alive():
                    self._build_timer.cancel()
            LOG.info(self._color.color_log(msg="Build watch stopped.", color=Colors.SUCCESS), extra=dict(markup=True))

    def _start(self) -> None:
        """Start BuildWatchManager and watch for changes to the template and its code resources."""
        first_build = True
        self._observer.start()
        while True:
            if self._waiting_build:
                self._execute_build(first_build)
            first_build = False
            time.sleep(1)

    def _start_watch(self) -> None:
        """Update stacks and populate all triggers"""
        self._observer.unschedule_all()
        self._update_stacks()
        self._add_template_triggers()
        self._add_code_triggers()

    def _execute_build(self, first_build: bool = False) -> None:
        """Logic to execute build."""
        if first_build:
            LOG.info(
                self._color.color_log(msg="Starting initial build.", color=Colors.PROGRESS), extra=dict(markup=True)
            )
        else:
            LOG.info(
                self._color.color_log(
                    msg="File changes detected. Starting build.", color=Colors.PROGRESS
                ), extra=dict(markup=True)
            )
        
        self._waiting_build = False
        
        try:
            # CRITICAL FIX: Re-parse template BEFORE building to pick up new resources
            if not first_build:
                LOG.debug("Refreshing build context with latest template data")
                self._build_context.set_up()
            
            self._build_context.run()
            LOG.info(self._color.color_log(msg="Build completed.", color=Colors.SUCCESS), extra=dict(markup=True))
        except Exception as e:
            LOG.error(
                self._color.color_log(
                    msg="Build failed. Watching for file changes to retry.", color=Colors.FAILURE
                ),
                exc_info=e,
                extra=dict(markup=True),
            )
            # Don't stop watching on build failure - let users fix the issue and retry
        
        # Update stacks and repopulate triggers after build
        # This ensures we pick up any template changes from the build
        self._start_watch()

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

        def on_code_change(event: Optional[FileSystemEvent] = None) -> None:
            """
            Custom event handling to create a new build if a file was modified.

            Parameters
            ----------
            event: Optional[FileSystemEvent]
                The event that triggered the change
            """
            if event and event.event_type == EVENT_TYPE_OPENED:
                # Ignore all file opened events since this event is
                # added in addition to a create or modified event,
                # causing an infinite loop of build executions
                LOG.debug("Ignoring file system OPENED event")
                return

            if (
                platform.system().lower() == "linux"
                and event
                and event.event_type == EVENT_TYPE_MODIFIED
                and event.is_directory
            ):
                # Linux machines appear to emit an additional event when
                # a file gets updated; a folder modified event
                # If folder/file.txt gets updated, there will be two events:
                #   1. file.txt modified event
                #   2. folder modified event
                # We want to ignore the second event
                LOG.debug(f"Ignoring file system MODIFIED event for folder {event.src_path!r}")
                return

            # Queue up debounced build for the detected change
            LOG.debug(f"Code change detected for resource {resource_id}")
            self.queue_debounced_build()

        return on_code_change
