"""
Represents an AWS X-Ray daemon container.
"""

from .container import Container


class XrayContainer(Container):
    """
    Represents an AWS X-Ray daemon container.
    """

    _IMAGE_REPO_NAME = "tanbouz/aws-xray-daemon:3.x"
    _WORKING_DIR = "/var/task"

    def __init__(self, memory_mb=128, env_vars=None):
        """
        Initializes the class

        :param int memory_mb: Optional. Max limit of memory in MegaBytes this X-Ray daemon can use.
        :param dict env_vars: Pass X-Ray daemon AWS credentials and AWS region using env variables.
        """

        xray_daemon_options = " ".join(["--local-mode",
                                        "--bind 0.0.0.0:2000",
                                        "--bind-tcp 0.0.0.0:2000"])

        # Expose port to host so SAM CLI can access X-Ray daemon
        # for simulating service integrations with X-Ray locally.
        # TODO: make exposed port user configurable
        super(XrayContainer, self).__init__(self._IMAGE_REPO_NAME,
                                            xray_daemon_options,
                                            self._WORKING_DIR,
                                            exposed_ports={'2000/udp': 2000},
                                            memory_limit_mb=memory_mb,
                                            env_vars=env_vars)
