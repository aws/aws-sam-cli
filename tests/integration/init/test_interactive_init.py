import logging
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from threading import Thread, Lock
from typing import List, Optional
from unittest import TestCase

from tests.testing_utils import get_sam_command

LOG = logging.getLogger(__name__)


OUTPUT_WAIT_THRESHOLD = 2
DEFAULT_OPTION_REGEX = re.compile(r"\t(\d+) - (.*)")
ROOT = "Root"

class Option:
    parent: Optional["Option"]
    name: str
    value: str
    visited: bool
    options: List["Option"]

    def __init__(self, name: str, value: str, parent: Optional["Option"] = None):
        self.parent = parent
        self.name = name
        self.value = value
        self.visited = False
        self.options = []

    def add_option(self, name: str, value: str):
        for option in self.options:
            if option.name == name:
                return

        self.options.append(Option(name, value, self))

    def exhausted(self) -> bool:
        for option in self.options:
            if not option.exhausted():
                return False

        return self.visited

    def get_selection_path(self) -> List[str]:
        if self.parent:
            parent_selection = self.parent.get_selection_path()
            parent_selection.append(self.value)
            return parent_selection
        return [self.value]

    def get_unvisited_node_count(self) -> int:
        total_unvisited = 0
        for option in self.options:
            total_unvisited += option.get_unvisited_node_count()

        if not self.visited:
            total_unvisited += 1
        return total_unvisited

    def __repr__(self):
        return f"{self.name}:{self.value} - {self.options}"

class Worker:
    current_option: Option

    def __init__(self, root_option: Option, lock: Lock):
        self.current_option = root_option
        self.lock = lock

    def test_init_flow(self):
        sam_cmd = get_sam_command()
        with tempfile.TemporaryDirectory() as working_dir:
            working_dir = Path(working_dir)
            init_process = Popen([sam_cmd, "init"], cwd=working_dir, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
            t = Thread(target=self.output_reader, args=(init_process,), daemon=True)
            t.start()
            init_process.wait(100)
        LOG.info("Init completed with following selection path: %s", self.current_option.get_selection_path())

    def output_reader(self, proc: Popen):
        line = ""
        project_generated = False
        while proc.poll() is None:
            data = proc.stdout.read(1).decode()
            if data == "\n":
                # LOG.info(line)

                if DEFAULT_OPTION_REGEX.match(line):
                    (option_value, option_text) = DEFAULT_OPTION_REGEX.findall(line)[0]
                    if "Custom Template Location" in option_text or "EventBridge App from scratch" in option_text:
                        continue
                    with self.lock:
                        self.current_option.add_option(option_text, option_value)

                line = ""
            else:
                line += data
                # LOG.info(line)
                if "Project name [sam-app]: " in line:
                    proc.kill()
                    proc.stdin.writelines([b"\n"])
                    proc.stdin.flush()
                    line = ""
                    project_generated = True

                if project_generated:
                    continue

                if "[y/N]: " in line:
                    with self.lock:
                        self.current_option.add_option(f"{line}-y", "y")
                        self.current_option.add_option(f"{line}-n", "n")
                    self.branch_out(proc)
                    line = ""

                if "Choice: " in line or "Template: " in line or "Runtime: " in line or "Package type: " in line or "Dependency manager: " in line:
                    self.branch_out(proc)
                    line = ""

    def branch_out(self, proc: Popen):
        with self.lock:
            for possible_option in self.current_option.options:
                if not possible_option.exhausted():
                    possible_option.visited = True
                    self.current_option = possible_option
                    option_value = possible_option.value
                    proc.stdin.writelines([f"{option_value}\n".encode("utf-8")])
                    proc.stdin.flush()
                    break

class DynamicInteractiveInitTests(TestCase):

    def setUp(self) -> None:
        self.root_option = Option(ROOT, ROOT)

    def test(self):
        lock = Lock()
        while not self.root_option.exhausted():
            with ThreadPoolExecutor() as executor:
                with lock:
                    unvisited_node_count = self.root_option.get_unvisited_node_count()
                for _ in range(unvisited_node_count):
                    worker = Worker(self.root_option, lock)
                    executor.submit(worker.test_init_flow)
                self.root_option.visited = True

