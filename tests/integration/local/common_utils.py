# Common utils between local tests
import logging
import os
import random
import time

LOG = logging.getLogger(__name__)

START_WAIT_TIME_SECONDS = 300

PYTEST_WORKER_COUNT = int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", 4))
PYTEST_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", 0)


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
        if "Address already in use" in line_as_str:
            LOG.info(f"Attempted to start port on {port} but it is already in use, restarting on a new port.")
            raise InvalidAddressException()
        if "Press CTRL+C to quit" in line_as_str or "Error: " in line_as_str:
            break

    return output


def get_pytest_worker_id():
    try:
        return int(PYTEST_WORKER_ID[2:])
    except TypeError:
        return 0


def random_port():
    start_port = 30000
    end_port = 40000

    port_window = (end_port - start_port) / PYTEST_WORKER_COUNT
    port_worker_start = int(start_port + (get_pytest_worker_id() * port_window))
    port_worker_end = int(port_worker_start + port_window)
    return random.randint(port_worker_start, port_worker_end)
