"""
Wraps watchdog to observe file system for any change.
"""
import logging
import threading
from abc import ABC, abstractmethod

from pathlib import Path
from threading import Thread, Lock
from typing import Callable, List, Dict, Optional

import docker
from docker import DockerClient
from docker.errors import ImageNotFound
from docker.types import CancellableStream
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent, FileSystemEventHandler
from watchdog.observers.api import ObservedWatch, BaseObserver

from samcli.lib.utils.hash import dir_checksum, file_checksum
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.local.lambdafn.config import FunctionConfig

LOG = logging.getLogger(__name__)


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
                code_paths += [layer.codeuri for layer in function_config.layers]
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
        self.docker_client: DockerClient = docker.from_env()
        self.events: CancellableStream = self.docker_client.events(filters={"type": "image"}, decode=True)
        self._images_observer_thread: Optional[Thread] = None
        self._lock: Lock = threading.Lock()

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
            while self._images_observer_thread.is_alive():
                pass


class FileObserverException(ObserverException):
    """
    Exception raised when unable to observe the input path.
    """


class FileObserver(ResourceObserver):
    """
    A class that will observe some file system paths for any change.
    """

    def __init__(self, on_change: Callable) -> None:
        """
        Initialize the file observer
        Parameters
        ----------
        on_change:
            Reference to the function that will be called if there is a change in aby of the observed paths
        """
        self._observed_paths: Dict[str, str] = {}
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
        self._input_on_change: Callable = on_change
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
        observed_paths = [path for path in self._observed_paths if event.src_path.startswith(path)]
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

    def watch(self, resource: str) -> None:
        """
        Start watching the input path. File Observer will keep track of the input path with its hash, to check it later
        if it got really changed or not.
        File Observer will send the parent path to watchdog for to be observed to avoid the missing events if the input
        paths got deleted.

        Parameters
        ----------
        resource: str
            The file/dir path to be observed

        Raises
        ------
        FileObserverException:
            if the input path is not exist
        """
        path_obj = Path(resource)
        if not path_obj.exists():
            raise FileObserverException("Can not observe non exist path")

        self._observed_paths[resource] = calculate_checksum(resource)

        # recursively watch the input path, and all child path for any modification
        self._watch_path(resource, resource, self._code_modification_handler, True)

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
        child_paths = self._watch_dog_observed_paths.get(watch_dog_path, [])
        first_time = not bool(child_paths)
        if original_path not in child_paths:
            child_paths += [original_path]
        self._watch_dog_observed_paths[watch_dog_path] = child_paths
        if first_time:
            self._observed_watches[watch_dog_path] = self._observer.schedule(
                watcher_handler, watch_dog_path, recursive=recursive
            )

    def unwatch(self, resource: str) -> None:
        """
        Remove the input path form the observed paths, and stop watching this path.

        Parameters
        ----------
        resource: str
            The file/dir path to be unobserved
        """
        path_obj = Path(resource)

        # unwatch input path
        self._unwatch_path(resource, resource)

        # unwatch parent path
        self._unwatch_path(str(path_obj.parent), resource)

    def _unwatch_path(self, watch_dog_path: str, original_path: str) -> None:
        """
        update the observed paths data structure, and call watch dog observer to unobserve the input watch dog path
        if it is not observed before

        Parameters
        ----------
        watch_dog_path: str
            The file/dir path to be unobserved by watch dog
        original_path: str
            The original input file/dir path to be unobserved
        """
        child_paths = self._watch_dog_observed_paths.get(watch_dog_path, [])
        if original_path in child_paths:
            child_paths.remove(original_path)
            self._observed_paths.pop(original_path, None)
        if not child_paths:
            self._watch_dog_observed_paths.pop(watch_dog_path, None)
            if self._observed_watches.get(watch_dog_path, None):
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


def calculate_checksum(path: str) -> str:
    path_obj = Path(path)
    if path_obj.is_file():
        checksum = file_checksum(path)
    else:
        checksum = dir_checksum(path)
    return checksum
