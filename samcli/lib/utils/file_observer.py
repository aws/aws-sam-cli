"""
Wraps watchdog to observe file system for any change.
"""
import logging
import platform
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock, Thread
from typing import Callable, Dict, List, Optional

import docker
from docker import DockerClient
from docker.errors import ImageNotFound
from docker.types import CancellableStream
from watchdog.events import FileSystemEvent, FileSystemEventHandler, PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver, ObservedWatch

from samcli.cli.global_config import Singleton
from samcli.lib.constants import DOCKER_MIN_API_VERSION
from samcli.lib.utils.hash import dir_checksum, file_checksum
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.local.lambdafn.config import FunctionConfig

LOG = logging.getLogger(__name__)
# Windows API error returned when attempting to perform I/O on closed pipe
BROKEN_PIPE_ERROR = 109


class ResourceObserver(ABC):
    @abstractmethod
    def watch(self, resource: str) -> None:
        """
        Start watching the input resource.

        Parameters
        ----------
        resource: str
            The resource that should be observed for modifications

        Raises
        ------
        ObserverException:
            if the input resource is not exist
        """

    @abstractmethod
    def unwatch(self, resource: str) -> None:
        """
        Remove the input resource form the observed resorces

        Parameters
        ----------
        resource: str
            The resource to be unobserved
        """

    @abstractmethod
    def start(self):
        """
        Start Observing.
        """

    @abstractmethod
    def stop(self):
        """
        Stop Observing.
        """


class ObserverException(Exception):
    """
    Exception raised when unable to observe the input Lambda Function.
    """


class LambdaFunctionObserver:
    """
    A class that will observe Lambda Function sources regardless if the source is code or image
    """

    def __init__(self, on_change: Callable) -> None:
        """
        Initialize the Image observer
        Parameters
        ----------
        on_change:
            Reference to the function that will be called if there is a change in aby of the observed image
        """
        self._observers: Dict[str, ResourceObserver] = {
            ZIP: FileObserver(self._on_zip_change),
            IMAGE: ImageObserver(self._on_image_change),
        }

        self._observed_functions: Dict[str, Dict[str, List[FunctionConfig]]] = {
            ZIP: {},
            IMAGE: {},
        }

        def _get_zip_lambda_function_paths(function_config: FunctionConfig) -> List[str]:
            """
            Returns a list of ZIP package type lambda function source code paths

            Parameters
            ----------
            function_config: FunctionConfig
                The lambda function configuration that will be observed

            Returns
            -------
            list[str]
                List of lambda functions' source code paths to be observed
            """
            code_paths = [function_config.code_abs_path]
            if function_config.layers:
                # Non-local layers will not have a codeuri property and don't need to be observed
                code_paths += [layer.codeuri for layer in function_config.layers if layer.codeuri]
            return code_paths

        def _get_image_lambda_function_image_names(function_config: FunctionConfig) -> List[str]:
            """
            Returns a list of Image package type lambda function image names

            Parameters
            ----------
            function_config: FunctionConfig
                The lambda function configuration that will be observed

            Returns
            -------
            list[str]
                List of lambda functions' image names to be observed
            """
            return [function_config.imageuri]

        self.get_resources: Dict[str, Callable] = {
            ZIP: _get_zip_lambda_function_paths,
            IMAGE: _get_image_lambda_function_image_names,
        }

        self._input_on_change: Callable = on_change
        self._watch_lock: Lock = threading.Lock()

    def _on_zip_change(self, paths: List[str]) -> None:
        """
        It got executed once there is a change in one of the watched lambda functions' source code.

        Parameters
        ----------
        paths: list[str]
            the changed lambda functions' source code paths
        """
        self._on_change(paths, ZIP)

    def _on_image_change(self, images: List[str]) -> None:
        """
        It got executed once there is a change in one of the watched lambda functions' images.

        Parameters
        ----------
        images: list[str]
            the changed lambda functions' images names
        """
        self._on_change(images, IMAGE)

    def _on_change(self, resources: List[str], package_type: str) -> None:
        """
        It got executed once there is a change in one of the watched lambda functions' resources.

        Parameters
        ----------
        resources: list[str]
            the changed lambda functions' resources (either source code path pr image names)
        package_type: str
            determine if the changed resource is a source code path or an image name
        """
        with self._watch_lock:
            changed_functions: List[FunctionConfig] = []
            for resource in resources:
                if self._observed_functions[package_type].get(resource, None):
                    changed_functions += self._observed_functions[package_type][resource]
            self._input_on_change(changed_functions)

    def watch(self, function_config: FunctionConfig) -> None:
        """
        Start watching the input lambda function.

        Parameters
        ----------
        function_config: FunctionConfig
            The lambda function configuration that will be observed

        Raises
        ------
        ObserverException:
            if not able to observe the input function source path/image
        """
        with self._watch_lock:
            if self.get_resources.get(function_config.packagetype, None):
                resources = self.get_resources[function_config.packagetype](function_config)
                for resource in resources:
                    functions = self._observed_functions[function_config.packagetype].get(resource, [])
                    functions += [function_config]
                    self._observed_functions[function_config.packagetype][resource] = functions
                    self._observers[function_config.packagetype].watch(resource)

    def unwatch(self, function_config: FunctionConfig) -> None:
        """
        Remove the input lambda function from the observed functions

        Parameters
        ----------
        function_config: FunctionConfig
            The lambda function configuration that will be observed
        """
        if self.get_resources.get(function_config.packagetype, None):
            resources = self.get_resources[function_config.packagetype](function_config)
            for resource in resources:
                functions = self._observed_functions[function_config.packagetype].get(resource, [])
                if function_config in functions:
                    functions.remove(function_config)
                if not functions:
                    self._observed_functions[function_config.packagetype].pop(resource, None)
                    self._observers[function_config.packagetype].unwatch(resource)

    def start(self):
        """
        Start Observing.
        """
        for _, observer in self._observers.items():
            observer.start()

    def stop(self):
        """
        Stop Observing.
        """
        for _, observer in self._observers.items():
            observer.stop()


class ImageObserverException(ObserverException):
    """
    Exception raised when unable to observe the input image.
    """


def broken_pipe_handler(func: Callable) -> Callable:
    """
    Decorator to handle the Windows API BROKEN_PIPE_ERROR error.

    Parameters
    ----------
    func: Callable
        The method to wrap around
    """

    # NOTE: As of right now, this checks for the Windows API error 109
    # specifically. This could be abstracted to potentially utilize a
    # callback method to further customize this.

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exception:
            # handle a pywintypes exception that gets thrown when trying to exit
            # from a command that utilizes ImageObserver(s) in
            # EAGER container mode (start-api, start-lambda)

            # all containers would have been stopped, and deleted, however
            # the pipes to those containers are still loaded somewhere

            if not platform.system() == "Windows":
                raise

            win_error = getattr(exception, "winerror", None)

            if not win_error == BROKEN_PIPE_ERROR:
                raise

            LOG.debug("Handling BROKEN_PIPE_ERROR pywintypes, exception ignored gracefully")

    return wrapper


class ImageObserver(ResourceObserver):
    """
    A class that will observe some docker images for any change.
    """

    def __init__(self, on_change: Callable) -> None:
        """
        Initialize the Image observer
        Parameters
        ----------
        on_change:
            Reference to the function that will be called if there is a change in aby of the observed image
        """
        self._observed_images: Dict[str, str] = {}
        self._input_on_change: Callable = on_change
        self.docker_client: DockerClient = docker.from_env(version=DOCKER_MIN_API_VERSION)
        self.events: CancellableStream = self.docker_client.events(filters={"type": "image"}, decode=True)
        self._images_observer_thread: Optional[Thread] = None
        self._lock: Lock = threading.Lock()

    @broken_pipe_handler
    def _watch_images_events(self):
        for event in self.events:
            if event.get("Action", None) != "tag":
                continue
            image_name = event["Actor"]["Attributes"]["name"]
            if self._observed_images.get(image_name, None):
                new_image_id = event["id"]
                if new_image_id != self._observed_images[image_name]:
                    self._observed_images[image_name] = new_image_id
                    self._input_on_change([image_name])

    def watch(self, resource: str) -> None:
        """
        Start watching the input image.

        Parameters
        ----------
        resource: str
            The container image name that will be observed

        Raises
        ------
        ImageObserverException:
            if the input image_name is not exist
        """
        try:
            image = self.docker_client.images.get(resource)
            self._observed_images[resource] = image.id
        except ImageNotFound as exc:
            raise ImageObserverException("Can not observe non exist image") from exc

    def unwatch(self, resource: str) -> None:
        """
        Remove the input image form the observed images

        Parameters
        ----------
        resource: str
            The container image name to be unobserved
        """
        self._observed_images.pop(resource, None)

    def start(self):
        """
        Start Observing.
        """
        with self._lock:
            if not self._images_observer_thread:
                self._images_observer_thread = threading.Thread(target=self._watch_images_events, daemon=True)
                self._images_observer_thread.start()

    def stop(self):
        """
        Stop Observing.
        """
        with self._lock:
            self.events.close()
            # wait until the images observer thread got stopped
            while self._images_observer_thread and self._images_observer_thread.is_alive():
                pass


class FileObserverException(ObserverException):
    """
    Exception raised when unable to observe the input path.
    """


class FileObserver(ResourceObserver):
    """
    A class that will Wrap the Singleton File Observer.
    """

    def __init__(self, on_change: Callable) -> None:
        """
        Initialize the file observer
        Parameters
        ----------
        on_change:
            Reference to the function that will be called if there is a change in aby of the observed paths
        """
        self._group = str(uuid.uuid4())
        self._single_file_observer = SingletonFileObserver()
        self._single_file_observer.add_group(self._group, on_change)

    def watch(self, resource: str) -> None:
        self._single_file_observer.watch(resource, self._group)

    def unwatch(self, resource: str) -> None:
        self._single_file_observer.unwatch(resource, self._group)

    def start(self):
        self._single_file_observer.start()

    def stop(self):
        self._single_file_observer.stop()


class SingletonFileObserver(metaclass=Singleton):
    """
    A Singleton class that will observe some file system paths for any change for multiple purposes.
    """

    def __init__(self) -> None:
        """
        Initialize the file observer
        """
        self._observed_paths_per_group: Dict[str, Dict[str, str]] = {}
        self._observed_groups_handlers: Dict[str, Callable] = {}
        self._observed_watches: Dict[str, ObservedWatch] = {}
        self._watch_dog_observed_paths: Dict[str, List[str]] = {}
        self._observer: BaseObserver = Observer()
        self._code_modification_handler: PatternMatchingEventHandler = PatternMatchingEventHandler(
            patterns=["*"], ignore_patterns=[], ignore_directories=False
        )

        self._code_deletion_handler: PatternMatchingEventHandler = PatternMatchingEventHandler(
            patterns=["*"], ignore_patterns=[], ignore_directories=False
        )

        self._code_modification_handler.on_modified = self.on_change
        self._code_deletion_handler.on_deleted = self.on_change
        self._watch_lock = threading.Lock()
        self._lock: Lock = threading.Lock()

    def on_change(self, event: FileSystemEvent) -> None:
        """
        It got executed once there is a change in one of the paths that watchdog is observing.
        This method will check if any of the input paths is really changed, and based on that it will
        invoke the input on_change function with the changed paths

        Parameters
        ----------
        event: watchdog.events.FileSystemEvent
            Determines that there is a change happened to some file/dir in the observed paths
        """
        with self._watch_lock:
            LOG.debug("a %s change got detected in path %s", event.event_type, event.src_path)
            for group, _observed_paths in self._observed_paths_per_group.items():
                if event.event_type == "deleted":
                    observed_paths = [
                        path
                        for path in _observed_paths
                        if path == event.src_path
                        or path in self._watch_dog_observed_paths.get(f"{event.src_path}_False", [])
                    ]
                else:
                    observed_paths = [path for path in _observed_paths if event.src_path.startswith(path)]

                if not observed_paths:
                    continue

                LOG.debug("affected paths of this change %s", observed_paths)
                changed_paths = []
                for path in observed_paths:
                    path_obj = Path(path)
                    # The path got deleted
                    if not path_obj.exists():
                        _observed_paths.pop(path, None)
                        changed_paths += [path]
                    else:
                        new_checksum = calculate_checksum(path)
                        if new_checksum and new_checksum != _observed_paths.get(path, None):
                            changed_paths += [path]
                            _observed_paths[path] = new_checksum
                        else:
                            LOG.debug("the path %s content does not change", path)

                if changed_paths:
                    self._observed_groups_handlers[group](changed_paths)

    def add_group(self, group: str, on_change: Callable) -> None:
        """
        Add new group to file observer. This enable FileObserver to watch the same path for
        multiple purposes.

        Parameters
        ----------
        group: str
            unique string define a new group of paths to be watched.

        on_change: Callable
            The method to be called in case if any path related to this group got changed.
        """
        if group in self._observed_paths_per_group:
            raise Exception(f"The group {group} of paths is already watched")
        self._observed_paths_per_group[group] = {}
        self._observed_groups_handlers[group] = on_change

    def watch(self, resource: str, group: str) -> None:
        """
        Start watching the input path. File Observer will keep track of the input path with its hash, to check it later
        if it got really changed or not.
        File Observer will send the parent path to watchdog for to be observed to avoid the missing events if the input
        paths got deleted.

        Parameters
        ----------
        resource: str
            The file/dir path to be observed

        group: str
            unique string define a new group of paths to be watched.

        Raises
        ------
        FileObserverException:
            if the input path is not exist
        """
        with self._watch_lock:
            path_obj = Path(resource)
            if not path_obj.exists():
                raise FileObserverException("Can not observe non exist path")

            _observed_paths = self._observed_paths_per_group[group]
            _check_sum = calculate_checksum(resource)
            if not _check_sum:
                raise Exception(f"Failed to calculate the hash of resource {resource}")
            _observed_paths[resource] = _check_sum

            LOG.debug("watch resource %s", resource)
            # recursively watch the input path, and all child path for any modification
            self._watch_path(resource, resource, self._code_modification_handler, True)

            LOG.debug("watch resource %s's parent %s", resource, str(path_obj.parent))
            # watch only the direct parent path child directories for any deletion
            # Parent directory watching is needed, as if the input path got deleted,
            # watchdog will not send an event for it
            self._watch_path(str(path_obj.parent), resource, self._code_deletion_handler, False)

    def _watch_path(
        self, watch_dog_path: str, original_path: str, watcher_handler: FileSystemEventHandler, recursive: bool
    ) -> None:
        """
        update the observed paths data structure, and call watch dog observer to observe the input watch dog path
        if it is not observed before

        Parameters
        ----------
        watch_dog_path: str
            The file/dir path to be observed by watch dog
        original_path: str
            The original input file/dir path to be observed
        watcher_handler: FileSystemEventHandler
            The watcher event handler
        recursive: bool
            determines if we need to watch the path, and all children paths recursively, or just the direct children
            paths
        """

        # Allow watching the same path in 2 Modes recursivly, and non-recusrsivly.
        # here, we need to only watch the input path in a specific recursive mode
        original_watch_dog_path = watch_dog_path
        watch_dog_path = f"{watch_dog_path}_{recursive}"
        child_paths = self._watch_dog_observed_paths.get(watch_dog_path, [])
        first_time = not bool(child_paths)
        if original_path not in child_paths:
            child_paths += [original_path]
        self._watch_dog_observed_paths[watch_dog_path] = child_paths
        if first_time:
            LOG.debug("Create Observer for resource %s with recursive %s", original_watch_dog_path, recursive)
            self._observed_watches[watch_dog_path] = self._observer.schedule(
                watcher_handler, original_watch_dog_path, recursive=recursive
            )

    def unwatch(self, resource: str, group: str) -> None:
        """
        Remove the input path form the observed paths, and stop watching this path.

        Parameters
        ----------
        resource: str
            The file/dir path to be unobserved
        group: str
            unique string define a new group of paths to be watched.
        """
        path_obj = Path(resource)

        LOG.debug("unwatch resource %s", resource)
        # unwatch input path
        self._unwatch_path(resource, resource, group, True)

        LOG.debug("unwatch resource %s's parent %s", resource, str(path_obj.parent))
        # unwatch parent path
        self._unwatch_path(str(path_obj.parent), resource, group, False)

    def _unwatch_path(self, watch_dog_path: str, original_path: str, group: str, recursive: bool) -> None:
        """
        update the observed paths data structure, and call watch dog observer to unobserve the input watch dog path
        if it is not observed before

        Parameters
        ----------
        watch_dog_path: str
            The file/dir path to be unobserved by watch dog
        original_path: str
            The original input file/dir path to be unobserved
        group: str
            unique string define a new group of paths to be watched.
        recursive: bool
            determines if we need to watch the path, and all children paths recursively, or just the direct children
            paths
        """

        # Allow watching the same path in 2 Modes recursivly, and non-recusrsivly.
        # here, we need to only stop watching the input path in a specific recursive mode
        original_watch_dog_path = watch_dog_path
        watch_dog_path = f"{watch_dog_path}_{recursive}"
        _observed_paths = self._observed_paths_per_group[group]
        child_paths = self._watch_dog_observed_paths.get(watch_dog_path, [])
        if original_path in child_paths:
            child_paths.remove(original_path)
            _observed_paths.pop(original_path, None)
        if not child_paths:
            self._watch_dog_observed_paths.pop(watch_dog_path, None)
            if self._observed_watches.get(watch_dog_path, None):
                LOG.debug("Unschedule Observer for resource %s with recursive %s", original_watch_dog_path, recursive)
                self._observer.unschedule(self._observed_watches[watch_dog_path])
                self._observed_watches.pop(watch_dog_path, None)

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


def calculate_checksum(path: str) -> Optional[str]:
    try:
        path_obj = Path(path)
        if path_obj.is_file():
            checksum = file_checksum(path)
        else:
            checksum = dir_checksum(path)
        return checksum
    except Exception:
        return None
