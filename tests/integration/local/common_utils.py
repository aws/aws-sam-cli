# Common utils between local tests
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

LOG = logging.getLogger(__name__)

START_WAIT_TIME_SECONDS = 300


class InvalidAddressException(Exception):
    pass


def wait_for_local_process(process, port, collect_output=False) -> str:
    start_time = time.time()
    output = ""
    while True:
        if time.time() - start_time > START_WAIT_TIME_SECONDS:
            # Couldn't match any output string during the max allowed wait time
            raise ValueError("Ran out of time attempting to start api/lambda process")
        line = process.stderr.readline()
        line_as_str = str(line.decode("utf-8")).strip()
        if line_as_str:
            LOG.info(f"{line_as_str}")
            if collect_output:
                output += f"{line_as_str}\n"
        if "Address already in use" in line_as_str or "port is already allocated" in line_as_str:
            LOG.info(f"Attempted to start port on {port} but it is already in use, restarting on a new port.")
            raise InvalidAddressException()
        if "Press CTRL+C to quit" in line_as_str or "Error: " in line_as_str:
            break

    return output


def random_port():
    return random.randint(30000, 40000)


def send_concurrent_requests(request_func: Callable, count: int, timeout: int = 300) -> List:
    """
    Send multiple concurrent requests using ThreadPoolExecutor.

    Args:
        request_func: Callable that performs a single request (e.g., lambda: requests.post(url))
        count: Number of concurrent requests to send
        timeout: Timeout for the entire operation in seconds

    Returns:
        List of results from all requests

    Example:
        results = send_concurrent_requests(
            lambda: requests.post(url + "/endpoint", timeout=300),
            count=3
        )
    """
    with ThreadPoolExecutor(max_workers=count) as thread_pool:
        futures = [thread_pool.submit(request_func) for _ in range(count)]
        results = [future.result() for future in as_completed(futures, timeout=timeout)]
    return results
