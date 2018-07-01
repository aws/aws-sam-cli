"""
Wrapper to Docker Attach API
"""

import struct
import logging
from socket import timeout
from docker.utils.socket import read, read_exactly, SocketError

LOG = logging.getLogger(__name__)


def attach(docker_client, container, stdout=True, stderr=True, logs=False):
    """

    Implements a method that wraps Docker Attach API to attach to a container and demux stdout and stderr data from the
    single data stream that Docker API returns.

    The signature of this method is intentionally similar to Docker Python SDK's ``attach()`` method except for the
    addition of one parameter called `demux` which, if set to True, will return an iterator that provides the stream
    data along with a stream type identifier. Caller can handle the data appropriately.

    Parameters
    ----------
    docker_client : docker.Client
        Docker client used to talk to Docker daemon

    container : docker.container
        Instance of the container to attach to

    stdout : bool
        Do you want to get stdout data?

    stderr : bool
        Do you want to get stderr data?

    logs : bool
        Do you want to include the container's previous output?
    """

    headers = {
        "Connection": "Upgrade",
        "Upgrade": "tcp"
    }

    query_params = {
        "stdout": 1 if stdout else 0,
        "stderr": 1 if stderr else 0,
        "logs": 1 if logs else 0,
        "stream": 1,  # Yes, we always stream
        "stdin": 0,  # We don't support stdin
    }

    # API client is a lower level Docker client that wraps the Docker APIs. It has methods that will help us
    # talk to the API directly. It is an instance of ``docker.APIClient``. We are going to use private methods of
    # class here because it is sometimes more convenient.
    api_client = docker_client.api

    # URL where the Docker daemon is running
    url = "{}/containers/{}/attach".format(api_client.base_url, container.id)

    # Send out the attach request and read the socket for response
    response = api_client._post(url, headers=headers, params=query_params, stream=True)  # pylint: disable=W0212
    socket = api_client._get_raw_response_socket(response)  # pylint: disable=W0212

    return _read_socket(socket)


def _read_socket(socket):
    """
    The stdout and stderr data from the container multiplexed into one stream of response from the Docker API.
    It follows the protocol described here https://docs.docker.com/engine/api/v1.30/#operation/ContainerAttach.
    The stream starts with a 8 byte header that contains the frame type and also payload size. Follwing that is the
    actual payload of given size. Once you read off this payload, we are ready to read the next header.

    This method will follow this protocol to read payload from the stream and return an iterator that returns
    a tuple containing the frame type and frame data. Callers can handle the data appropriately based on the frame
    type.

        Stdout => Frame Type = 1
        Stderr => Frame Type = 2


    Parameters
    ----------
    socket
        Socket to read responses from

    Yields
    -------
    int
        Type of the stream (1 => stdout, 2 => stderr)
    str
        Data in the stream
    """

    # Keep reading the stream until the stream terminates
    while True:

        try:

            payload_type, payload_size = _read_header(socket)
            if payload_size < 0:
                # Something is wrong with the data stream. Payload size can't be less than zero
                break

            for data in _read_payload(socket, payload_size):
                yield payload_type, data

        except timeout:
            # Timeouts are normal during debug sessions and long running tasks
            LOG.debug("Ignoring docker socket timeout")

        except SocketError:
            # There isn't enough data in the stream. Probably the socket terminated
            break


def _read_payload(socket, payload_size):
    """
    From the given socket, reads and yields payload of the given size. With sockets, we don't receive all data at
    once. Therefore this method will yield each time we read some data from the socket until the payload_size has
    reached or socket has no more data.

    Parameters
    ----------
    socket
        Socket to read from

    payload_size : int
        Size of the payload to read. Exactly these many bytes are read from the socket before stopping the yield.

    Yields
    -------
    int
        Type of the stream (1 => stdout, 2 => stderr)
    str
        Data in the stream
    """

    remaining = payload_size
    while remaining > 0:

        # Try and read as much as possible
        data = read(socket, remaining)
        if data is None:
            # ``read`` will terminate with an empty string. This is just a transient state where we didn't get any data
            continue

        if len(data) == 0:  # pylint: disable=C1801
            # Empty string. Socket does not have any more data. We are done here even if we haven't read full payload
            break

        remaining -= len(data)
        yield data


def _read_header(socket):
    """
    Reads the header from socket stream to determine the size of next frame to read. Header is 8 bytes long, where
    the first byte is the stream type and last four bytes (bigendian) is size of the payload

        header := [8]byte{STREAM_TYPE, 0, 0, 0, SIZE1, SIZE2, SIZE3, SIZE4}

    Parameters
    ----------
    socket
        Socket to read the responses from

    Returns
    -------
    int
        Type of the frame
    int
        Size of the payload
    """

    data = read_exactly(socket, 8)

    # >BxxxL is the struct notation to unpack data in correct header format in big-endian
    return struct.unpack('>BxxxL', data)
