"""
Utility to call cloudformation command with args
"""

import logging
import platform
import subprocess
import sys

LOG = logging.getLogger(__name__)


def execute_command(command, args, template_file):
    LOG.debug("%s command is called", command)
    try:
        aws_cmd = find_executable("aws")

        args = list(args)
        if template_file:
            # Since --template-file was parsed separately, add it here manually
            args.extend(["--template-file", template_file])

        subprocess.check_call([aws_cmd, 'cloudformation', command] + args)
        LOG.debug("%s command successful", command)
    except subprocess.CalledProcessError as e:
        # Underlying aws command will print the exception to the user
        LOG.debug("Exception: %s", e)
        sys.exit(e.returncode)


def find_executable(execname):

    if platform.system().lower() == 'windows':
        options = [
            "{}.cmd".format(execname),
            "{}.exe".format(execname),
            execname
        ]
    else:
        options = [execname]

    for name in options:
        try:
            subprocess.Popen([name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # No exception. Let's pick this
            return name
        except OSError as ex:
            LOG.debug("Unable to find executable %s", name, exc_info=ex)

    raise OSError("Unable to find AWS CLI installation under following names: {}".format(options))
