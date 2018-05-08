"""
Utility to call cloudformation command with args
"""

import logging
import platform
import subprocess
import sys

LOG = logging.getLogger(__name__)


def execute_command(command, args):
    LOG.debug("%s command is called", command)
    try:
        aws_cmd = 'aws' if platform.system().lower() != 'windows' else 'aws.cmd'
        subprocess.check_call([aws_cmd, 'cloudformation', command] + list(args))
        LOG.debug("%s command successful", command)
    except subprocess.CalledProcessError as e:
        # Underlying aws command will print the exception to the user
        LOG.debug("Exception: %s", e)
        sys.exit(e.returncode)
