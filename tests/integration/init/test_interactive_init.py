import logging
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from threading import Thread, Lock
from typing import List, Optional, Tuple
from unittest import TestCase

from tests.testing_utils import get_sam_command

LOG = logging.getLogger()


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
            parent_selection.append(f"{self.value} - {self.name}")
            return parent_selection
        return []

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
    lock: Lock
    dead_end: bool

    def __init__(self, root_option: Option, lock: Lock):
        self.current_option = root_option
        self.lock = lock
        self.dead_end = False

    def test_init_flow(self) -> Optional[Tuple[int, int, List[str]]]:
        sam_cmd = get_sam_command()
        with tempfile.TemporaryDirectory() as working_dir:
            working_dir = Path(working_dir)
            init_process = Popen([sam_cmd, "init"], cwd=working_dir, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
            t = Thread(target=self.output_reader, args=(init_process,), daemon=True)
            t.start()
            init_process.wait(100)

            if self.dead_end:
                return None

            # validate_process = Popen([sam_cmd, "validate", "--no-lint"], cwd=working_dir.joinpath("sam-app"), stdout=PIPE, stderr=STDOUT)
            # validate_process.wait(100)

            return init_process.returncode, 0, self.current_option.get_selection_path()


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
                    proc.stdin.writelines([b"\n"])
                    proc.stdin.flush()
                    line = ""
                    project_generated = True

                if project_generated:
                    continue

                if "[y/N]: " in line:
                    option_name = line
                    if "most popular runtime" in line:
                        option_name = "Python Shortcut"
                    if "X-Ray" in line:
                        option_name = "XRay"
                    if "cloudwatch-application-insights" in line:
                        option_name = "AppInsights"
                    with self.lock:
                        self.current_option.add_option(f"{option_name}-y", "y")
                        self.current_option.add_option(f"{option_name}-n", "n")
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
                    return
        self.dead_end = True
        proc.kill()

class DynamicInteractiveInitTests(TestCase):

    def setUp(self) -> None:
        self.root_option = Option(ROOT, ROOT)

    def test(self):
        total_tests: List[List[str]] = []
        lock = Lock()
        while not self.root_option.exhausted():
            futures = []
            with ThreadPoolExecutor(max_workers=8) as executor:
                with lock:
                    unvisited_node_count = self.root_option.get_unvisited_node_count()
                for _ in range(unvisited_node_count):
                    worker = Worker(self.root_option, lock)
                    futures.append(executor.submit(worker.test_init_flow))
                self.root_option.visited = True

                for future in as_completed(futures):
                    (init_return_code, validate_return_code, test_path) = future.result() or (0, 0, [])
                    if not test_path:
                        continue
                    self.assertEqual(init_return_code, 0)
                    self.assertEqual(validate_return_code, 0)
                    total_tests.append(test_path)
                    LOG.info("Completed %s", test_path)

        LOG.info("Total %s test cases have been passed!", len(total_tests))

