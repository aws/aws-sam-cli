"""
Wraps watchdog to observe file system for any change.
"""
import logging
import threading

from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from samcli.lib.utils.hash import dir_checksum, file_checksum

LOG = logging.getLogger(__name__)


class FileObserverException(Exception):
    """
    Exception raised when unable to observe the input path.
    """


class FileObserver:
    """
    A class that will observe some file system paths for any change.
    """

    def __init__(self, on_change):
        """
        Initialize the file observer
        Parameters
        ----------
        on_change:
            Reference to the function that will be called if there is a change in aby of the observed paths
        """
        self._observed_paths = {}
        self._observed_watches = {}
        self._watch_dog_observed_paths = {}
        self._observer = Observer()
        self._code_change_handler = PatternMatchingEventHandler(
            patterns=["*"], ignore_patterns=[], ignore_directories=False
        )
        self._code_change_handler.on_modified = self.on_change
        self._input_on_change = on_change
        self._lock = threading.Lock()

    def on_change(self, event):
        """
        It got executed once there is a change in one of the paths that watchdog is observing.
        This method will check if any of the input paths is really changed, and based on that it will
        invoke the input on_change function with the changed paths

        Parameters
        ----------
        event: watchdog.events.FileSystemEventHandler
            Determines that there is a change happened to some file/dir in the observed paths
        """
        event_path = event.src_path
        observed_paths = []

        for watchdog_path, child_observed_paths in self._watch_dog_observed_paths.items():
            if event_path.startswith(watchdog_path):
                observed_paths += child_observed_paths

        if not observed_paths:
            return

        changed_paths = []
        for path in observed_paths:
            path_obj = Path(path)
            # The path got deleted
            if not path_obj.exists():
                self._observed_paths.pop(path, None)
                changed_paths += [path]
            else:
                new_checksum = calculate_checksum(path)
                if new_checksum != self._observed_paths.get(path, None):
                    changed_paths += [path]
                    self._observed_paths[path] = new_checksum
        if changed_paths:
            self._input_on_change(changed_paths)

    def watch(self, path):
        """
        Start watching the input path. File Observer will keep track of the input path with its hash, to check it later
        if it got really changed or not.
        File Observer will send the parent path to watchdog for to be observed to avoid the missing events if the input
        paths got deleted.

        Parameters
        ----------
        path: str
            The file/dir path to be observed

        Raises
        ------
        FileObserverException:
            if the input path is not exist
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileObserverException("Can not observe non exist path")

        self._observed_paths[path] = calculate_checksum(path)

        # Watchdog will observe the path's parent path to make sure not missing the event if the path itself got deleted
        parent_path = str(path_obj.parent)
        child_paths = self._watch_dog_observed_paths.get(parent_path, [])
        first_time = not bool(child_paths)
        if path not in child_paths:
            child_paths += [path]
        self._watch_dog_observed_paths[parent_path] = child_paths
        if first_time:
            self._observed_watches[parent_path] = self._observer.schedule(
                self._code_change_handler, parent_path, recursive=True
            )

    def unwatch(self, path):
        """
        Remove the input path form the observed paths, and stop watching this path.

        Parameters
        ----------
        path: str
            The file/dir path to be unobserved
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileObserverException("Can not unwatch non exist path")
        parent_path = str(path_obj.parent)
        child_paths = self._watch_dog_observed_paths.get(parent_path, [])
        if path in child_paths:
            child_paths.remove(path)
            self._observed_paths.pop(path, None)
        if not child_paths:
            self._watch_dog_observed_paths.pop(parent_path, None)
            if self._observed_watches[parent_path]:
                self._observer.unschedule(self._observed_watches[parent_path])
                self._observed_watches.pop(parent_path, None)

    def start(self):
        """
        Start Observing.
        """
        with self._lock:
            if not self._observer.is_alive():
                self._observer.start()

    def stop(self):
        """
        Stop Observing.
        """
        with self._lock:
            if self._observer.is_alive():
                self._observer.stop()


def calculate_checksum(path):
    path_obj = Path(path)
    if path_obj.is_file():
        checksum = file_checksum(path)
    else:
        checksum = dir_checksum(path)
    return checksum
