"""
Auto loads src files to build destination on changes to source dir
"""
import logging
import os
import shutil
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LOG = logging.getLogger(__name__)
DEFAULT_DEST_DIR = "build/"
WATCHER_SLEEP_TIME = 5


class HotLoader(object):
    """
    Interface for starting starting the hot (re)loader.
    Only currently supports python lambda runtimes.

    Due to the requirement for flat build dir for python lambda functions,
    HotLoader copies all files from the src dir to the build dir.
    """

    def __init__(self, cwd, dest=DEFAULT_DEST_DIR):
        """
        Initialize the HotLoader

        :param cwd: Root directory of sam project that includes the template.yaml and subdirs with source files
        :param dest: Optional, destination directory i.e. 'build' dir
            where sam cli loads and executes lambda source files
        """
        self.cwd = cwd
        self.dest = dest

    def start(self):
        """
        Creates and starts the source file watcher.
        """
        w = Watcher(self.cwd, self.dest)
        w.run()


class Watcher(object):
    def __init__(self, cwd, dest):
        self.observer = Observer()
        self.cwd = cwd
        self.dest = dest

    def run(self):
        event_handler = Handler(self.cwd, self.dest)
        self.observer.schedule(event_handler, self.cwd)
        self.observer.start()
        try:
            while True:
                time.sleep(WATCHER_SLEEP_TIME)
        except Exception as e:
            LOG.info("Watcher stopped: %s", e)
            self.observer.stop()

        self.observer.join()


# TODO: change to Pattern style event handler,
# so we can watch all function subdirs recursively and exclude build dirs.
class Handler(FileSystemEventHandler):
    """
    Handles watcher events. Primarily copies files from cwd to build dest dir.
    """
    def __init__(self, cwd, dest):
        """
        Initialize the Handler

        :param cwd: Root directory of sam project that includes the template.yaml and subdirs with source files
        :param dest: Optional, destination directory i.e. 'build' dir
            where sam cli loads and executes lambda source files
        """
        super(Handler, self).__init__()
        self.cwd = cwd
        self.dest = dest

    def load_src_files(self):
        """
        Copies source files to the build dest directory
        """
        src_files = os.listdir(self.cwd)
        for file_name in src_files:
            full_file_name = os.path.join(self.cwd, file_name)
            if os.path.isfile(full_file_name):
                shutil.copy(full_file_name, self.dest)

    def on_any_event(self, event):
        if event.is_directory:
            return None

        elif event.event_type == "created":
            LOG.info("New file created - %s.", event.src_path)
            self.load_src_files()
            LOG.info("Function updated.")

        elif event.event_type == "modified":
            # Taken any action here when a file is modified.
            LOG.info("File modified - %s.", event.src_path)
            self.load_src_files()
            LOG.info("Function updated.")
