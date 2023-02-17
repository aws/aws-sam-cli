import logging
import os
import platform
import subprocess
import tempfile

from threading import Thread
from typing import Callable, List, Optional
from collections import namedtuple
from subprocess import Popen, PIPE, TimeoutExpired
from queue import Queue

import shutil
from uuid import uuid4

import psutil

IS_WINDOWS = platform.system().lower() == "windows"
RUNNING_ON_CI = os.environ.get("APPVEYOR", False) or os.environ.get("CI", False)
RUNNING_TEST_FOR_MASTER_ON_CI = os.environ.get("APPVEYOR_REPO_BRANCH", "master") != "master"
CI_OVERRIDE = os.environ.get("APPVEYOR_CI_OVERRIDE", False) or os.environ.get("CI_OVERRIDE", False)
RUN_BY_CANARY = os.environ.get("BY_CANARY", False)

# Tests require docker suffers from Docker Hub request limit
SKIP_DOCKER_TESTS = RUNNING_ON_CI and not RUN_BY_CANARY

# Set to True temporarily if the integration tests require updated build images
# Build images aren't published until after the CLI is released
# The CLI integration tests thus cannot succeed if they require new build images (chicken-egg problem)
SKIP_DOCKER_BUILD = False

SKIP_DOCKER_MESSAGE = "Skipped Docker test: running on CI not in canary or new build images are required"

LOG = logging.getLogger(__name__)

CommandResult = namedtuple("CommandResult", "process stdout stderr")
TIMEOUT = 600
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


def get_sam_command():
    return "samdev" if os.getenv("SAM_CLI_DEV") else "sam"


def method_to_stack_name(method_name):
    """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
    method_name = method_name.split(".")[-1]
    stack_name = f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}-{uuid4().hex}"
    if not stack_name.startswith("test"):
        stack_name = f"test-{stack_name}"
    return stack_name[:128]


def run_command(command_list, cwd=None, env=None, timeout=TIMEOUT) -> CommandResult:
    LOG.info("Running command: %s", " ".join(command_list))
    process_execute = Popen(command_list, cwd=cwd, env=env, stdout=PIPE, stderr=PIPE)
    try:
        stdout_data, stderr_data = process_execute.communicate(timeout=timeout)
        LOG.info(f"Stdout: {stdout_data.decode('utf-8')}")
        LOG.info(f"Stderr: {stderr_data.decode('utf-8')}")
        return CommandResult(process_execute, stdout_data, stderr_data)
    except TimeoutExpired:
        LOG.error(f"Command: {command_list}, TIMED OUT")
        LOG.error(f"Return Code: {process_execute.returncode}")
        process_execute.kill()
        raise


def run_command_with_input(command_list, stdin_input, timeout=TIMEOUT, cwd=None) -> CommandResult:
    LOG.info("Running command: %s", " ".join(command_list))
    LOG.info("With input: %s", stdin_input)
    process_execute = Popen(command_list, cwd=cwd, stdout=PIPE, stderr=PIPE, stdin=PIPE)
    try:
        stdout_data, stderr_data = process_execute.communicate(stdin_input, timeout=timeout)
        LOG.info(f"Stdout: {stdout_data.decode('utf-8')}")
        LOG.info(f"Stderr: {stderr_data.decode('utf-8')}")
        return CommandResult(process_execute, stdout_data, stderr_data)
    except TimeoutExpired:
        LOG.error(f"Command: {command_list}, TIMED OUT")
        LOG.error(f"Return Code: {process_execute.returncode}")
        process_execute.kill()
        raise


def run_command_with_inputs(command_list: List[str], inputs: List[str], timeout=TIMEOUT) -> CommandResult:
    return run_command_with_input(command_list, ("\n".join(inputs) + "\n").encode(), timeout)


def start_persistent_process(
    command_list: List[str],
    cwd: Optional[str] = None,
) -> Popen:
    """Start a process with parameters that are suitable for persistent execution."""
    return Popen(
        command_list,
        stdout=PIPE,
        stderr=subprocess.STDOUT,
        stdin=PIPE,
        encoding="utf-8",
        bufsize=1,
        cwd=cwd,
    )


def kill_process(process: Popen) -> None:
    """Kills a process and it's children.
    This loop ensures orphaned children are killed as well.
    https://psutil.readthedocs.io/en/latest/#kill-process-tree
    Raises ValueError if some processes are alive"""
    root_process = psutil.Process(process.pid)
    all_processes = root_process.children(recursive=True)
    all_processes.append(root_process)
    for process_to_kill in all_processes:
        try:
            process_to_kill.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(all_processes, timeout=10)
    if alive:
        raise ValueError(f"Processes: {alive} are still alive.")


def read_until_string(process: Popen, expected_output: str, timeout: int = 30) -> None:
    """Read output from process until a line equals to expected_output has shown up or reaching timeout.
    Throws TimeoutError if times out
    """

    def _compare_output(output, _: List[str]) -> bool:
        return bool(expected_output in output)

    try:
        read_until(process, _compare_output, timeout)
    except TimeoutError as ex:
        expected_output_bytes = expected_output.encode("utf-8")
        raise TimeoutError(
            f"Did not get expected output after {timeout} seconds. Expected output: {expected_output_bytes!r}"
        ) from ex


def read_until(process: Popen, callback: Callable[[str, List[str]], bool], timeout: int = 5):
    """Read output from process until callback returns True or timeout is reached

    Parameters
    ----------
    process : Popen
    callback : Callable[[str, List[str]], None]
        Call when a new line is read from the process.
    timeout : int, optional
        By default 5

    Raises
    ------
    TimeoutError
        Raises when timeout is reached
    """
    result_queue: Queue = Queue()

    def _read_output():
        try:
            outputs = list()
            for output in process.stdout:
                outputs.append(output)
                LOG.info(output.encode("utf-8"))
                if callback(output, outputs):
                    result_queue.put(True)
                    return
        except Exception as ex:
            result_queue.put(ex)

    reading_thread = Thread(target=_read_output, daemon=True)
    reading_thread.start()
    reading_thread.join(timeout=timeout)
    if reading_thread.is_alive():
        raise TimeoutError(f"Did not get expected output after {timeout} seconds.")
    if result_queue.qsize() > 0:
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
    else:
        raise ValueError()


class FileCreator(object):
    def __init__(self):
        self.rootdir = tempfile.mkdtemp()

    def remove_all(self):
        if os.path.exists(self.rootdir):
            shutil.rmtree(self.rootdir)

    def create_file(self, filename, contents, mtime=None, mode="w"):
        """Creates a file in a tmpdir
        ``filename`` should be a relative path, e.g. "foo/bar/baz.txt"
        It will be translated into a full path in a tmp dir.
        If the ``mtime`` argument is provided, then the file's
        mtime will be set to the provided value (must be an epoch time).
        Otherwise the mtime is left untouched.
        ``mode`` is the mode the file should be opened either as ``w`` or
        `wb``.
        Returns the full path to the file.
        """
        full_path = os.path.join(self.rootdir, filename)
        if not os.path.isdir(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path))
        with open(full_path, mode) as f:
            f.write(contents)
        current_time = os.path.getmtime(full_path)
        # Subtract a few years off the last modification date.
        os.utime(full_path, (current_time, current_time - 100000000))
        if mtime is not None:
            os.utime(full_path, (mtime, mtime))
        return full_path

    def append_file(self, filename, contents):
        """Append contents to a file
        ``filename`` should be a relative path, e.g. "foo/bar/baz.txt"
        It will be translated into a full path in a tmp dir.
        Returns the full path to the file.
        """
        full_path = os.path.join(self.rootdir, filename)
        if not os.path.isdir(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path))
        with open(full_path, "a") as f:
            f.write(contents)
        return full_path

    def full_path(self, filename):
        """Translate relative path to full path in temp dir.
        f.full_path('foo/bar.txt') -> /tmp/asdfasd/foo/bar.txt
        """
        return os.path.join(self.rootdir, filename)
