# Common utils between local tests
import logging
import random
import time

LOG = logging.getLogger(__name__)

START_WAIT_TIME_SECONDS = 60


class InvalidAddressException(Exception):
    pass


def wait_for_local_process(process, port):
    start_time = time.time()
    while True:
        if time.time() - start_time > START_WAIT_TIME_SECONDS:
            # Couldn't match any output string during the max allowed wait time
            raise ValueError("Ran out of time attempting to start api/lambda process")
        line = process.stderr.readline()
        line_as_str = str(line.decode("utf-8")).strip()
        if line_as_str:
            LOG.info(f"{line_as_str}")
        if "Address already in use" in line_as_str:
            LOG.info(f"Attempted to start port on {port} but it is already in use, restarting on a new port.")
            raise InvalidAddressException()
        if "(Press CTRL+C to quit)" in line_as_str:
            break


def random_port():
    return random.randint(30000, 40000)
