import logging
import re
import sys
import tempfile
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

    def __repr__(self):
        return f"{self.name}:{self.value} - {self.options}"

class DynamicInteractiveInitTests(TestCase):

    def setUp(self) -> None:
        self.lock = Lock()
        self.answers = []
        self.root_option = Option(ROOT, ROOT)
        self.current_option = self.root_option

    def output_reader(self, proc: Popen):
        line = ""
        project_generated = False
        while proc.poll() is None:
            data = proc.stdout.read(1).decode()
            if data == "\n":
                #LOG.info(line)

                if DEFAULT_OPTION_REGEX.match(line):
                    (option_value, option_text) = DEFAULT_OPTION_REGEX.findall(line)[0]
                    if "Custom Template Location" in option_text or "EventBridge App from scratch" in option_text:
                        continue
                    self.current_option.add_option(option_text, option_value)

                line = ""
            else:
                line += data
                #LOG.info(line)
                if "Project name [sam-app]: " in line:
                    proc.stdin.writelines([b"\n"])
                    proc.stdin.flush()
                    line = ""
                    project_generated = True

                if project_generated:
                    continue

                if "[y/N]: " in line:
                    self.current_option.add_option(f"{line}-y", "y")
                    self.current_option.add_option(f"{line}-n", "n")
                    self.branch_out(proc)
                    line = ""

                if "Choice: " in line or "Template: " in line or "Runtime: " in line or "Package type: " in line or "Dependency manager: " in line:
                    self.branch_out(proc)
                    line = ""

    def branch_out(self, proc: Popen):
        for possible_option in self.current_option.options:
            if not possible_option.exhausted():
                possible_option.visited = True
                self.current_option = possible_option
                option_value = possible_option.value
                proc.stdin.writelines([f"{option_value}\n".encode("utf-8")])
                proc.stdin.flush()
                break



    def test(self):
        while not self.root_option.exhausted():
            self.current_option = self.root_option
            sam_cmd = get_sam_command()
            with tempfile.TemporaryDirectory() as working_dir:
                working_dir = Path(working_dir)
                init_process = Popen([sam_cmd, "init"], cwd=working_dir, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
                t = Thread(target=self.output_reader, args=(init_process,), daemon=True)
                t.start()
                init_process.wait(100)
                self.assertEqual(init_process.returncode, 0)

                LOG.info("Init completed with following selection path: %s", self.current_option.get_selection_path())

                # validate_process = Popen([sam_cmd, "validate", "--no-lint"], cwd=working_dir.joinpath("sam-app"), stdout=sys.stdout, stderr=STDOUT)
                # validate_process.wait(100)
