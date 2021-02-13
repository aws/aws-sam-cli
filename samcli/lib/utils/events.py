"""
Utility function to handle events from STDIN and paths
"""

import logging

import click

STDIN_FILE_NAME = "-"
LOG = logging.getLogger(__name__)


def get_event(event_file_name):
    """
    Read the event JSON data from the given file. If no file is provided, read the event from stdin.

    :param string event_file_name: Path to event file, or '-' for stdin
    :return string: Contents of the event file or stdin
    """

    if event_file_name == STDIN_FILE_NAME:
        # If event is empty, listen to stdin for event data until EOF
        LOG.info("Reading invoke payload from stdin (you can also pass it from file with --event)")

    # click.open_file knows to open stdin when filename is '-'. This is safer than manually opening streams, and
    # accidentally closing a standard stream
    with click.open_file(event_file_name, "r", encoding="utf-8") as fp:
        return fp.read()
