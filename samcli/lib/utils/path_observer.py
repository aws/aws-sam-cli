"""
HandlerObserver and its helper classes.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
    RegexMatchingEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT, ObservedWatch


@dataclass
class PathHandler:
    """PathHandler is an object that can be passed into
    Bundle Observer directly for watching a specific path with
    corresponding EventHandler

    Fields:
        event_handler : FileSystemEventHandler
            Handler for the event
        path : Path
            Path to the folder to be watched
        recursive : bool, optional
            True to watch child folders, by default False
        static_folder : bool, optional
            Should the observed folder name be static, by default False
            See StaticFolderWrapper on the use case.
        self_create : Optional[Callable[[], None]], optional
            Callback when the folder to be observed itself is created, by default None
            This will not be called if static_folder is False
        self_delete : Optional[Callable[[], None]], optional
            Callback when the folder to be observed itself is deleted, by default None
            This will not be called if static_folder is False
    """

    event_handler: FileSystemEventHandler
    path: Path
    recursive: bool = False
    static_folder: bool = False
    self_create: Optional[Callable[[], None]] = None
    self_delete: Optional[Callable[[], None]] = None


class StaticFolderWrapper:
    """This class is used to alter the behavior of watchdog folder watches.
    https://github.com/gorakhargosh/watchdog/issues/415
    By default, if a folder is renamed, the handler will still get triggered for the new folder
    Ex:
        1. Create FolderA
        2. Watch FolderA
        3. Rename FolderA to FolderB
        4. Add file to FolderB
        5. Handler will get event for adding the file to FolderB but with event path still as FolderA
    This class watches the parent folder and if the folder to be watched gets renamed or deleted,
    the watch will be stopped and changes in the renamed folder will not be triggered.
    """

    def __init__(self, observer: "HandlerObserver", initial_watch: ObservedWatch, path_handler: PathHandler):
        """[summary]

        Parameters
        ----------
        observer : HandlerObserver
            HandlerObserver
        initial_watch : ObservedWatch
            Initial watch for the folder to be watched that gets returned by HandlerObserver
        path_handler : PathHandler
            PathHandler of the folder to be watched.
        """
        self._observer = observer
        self._path_handler = path_handler
        self._watch = initial_watch

    def _on_parent_change(self, _: FileSystemEvent) -> None:
        """Callback for changes detected in the parent folder"""

        # When folder is being watched but the folder does not exist
        if self._watch and not self._path_handler.path.exists():
            if self._path_handler.self_delete:
                self._path_handler.self_delete()
            self._observer.unschedule(self._watch)
            self._watch = None
        # When folder is not being watched but the folder does exist
        elif not self._watch and self._path_handler.path.exists():
            if self._path_handler.self_create:
                self._path_handler.self_create()
            self._watch = self._observer.schedule_handler(self._path_handler)

    def get_dir_parent_path_handler(self) -> PathHandler:
        """Get PathHandler that watches the folder changes from the parent folder.

        Returns
        -------
        PathHandler
            PathHandler for the parent folder. This should be added back into the HandlerObserver.
        """
        dir_path = self._path_handler.path.resolve()
        parent_dir_path = dir_path.parent
        parent_folder_handler = RegexMatchingEventHandler(
            regexes=[f"^{re.escape(str(dir_path))}$"],
            ignore_regexes=[],
            ignore_directories=False,
            case_sensitive=True,
        )
        parent_folder_handler.on_any_event = self._on_parent_change
        return PathHandler(path=parent_dir_path, event_handler=parent_folder_handler)


class HandlerObserver(Observer):  # pylint: disable=too-many-ancestors
    """
    Extended WatchDog Observer that takes in a single PathHandler object.
    """

    def __init__(self, timeout=DEFAULT_OBSERVER_TIMEOUT):
        super().__init__(timeout=timeout)

    def schedule_handlers(self, path_handlers: List[PathHandler]) -> List[ObservedWatch]:
        """Schedule a list of PathHandlers

        Parameters
        ----------
        path_handlers : List[PathHandler]
            List of PathHandlers to be scheduled

        Returns
        -------
        List[ObservedWatch]
            List of ObservedWatch corresponding to path_handlers in the same order.
        """
        watches = list()
        for path_handler in path_handlers:
            watches.append(self.schedule_handler(path_handler))
        return watches

    def schedule_handler(self, path_handler: PathHandler) -> ObservedWatch:
        """Schedule a PathHandler

        Parameters
        ----------
        path_handler : PathHandler
            PathHandler to be scheduled

        Returns
        -------
        ObservedWatch
            ObservedWatch corresponding to the PathHandler.
            If static_folder is True, the parent folder watch will be returned instead.
        """
        watch = self.schedule(path_handler.event_handler, str(path_handler.path), path_handler.recursive)
        if path_handler.static_folder:
            static_wrapper = StaticFolderWrapper(self, watch, path_handler)
            parent_path_handler = static_wrapper.get_dir_parent_path_handler()
            watch = self.schedule_handler(parent_path_handler)
        return watch
