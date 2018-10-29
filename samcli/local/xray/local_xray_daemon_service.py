"""
AWS X-ray daemon service.
"""

import logging
import docker

from samcli.local.docker.xray_container import XrayContainer
from samcli.commands.exceptions import UserException

LOG = logging.getLogger(__name__)


class LocalXrayDaemonService(object):
    def __init__(self, container_manager):
        """
        Creates an LocalXrayDaemonService

        :param container_manager samcli.local.docker.manager.ContainerManager:
            Container manager being used to run Lambda invokations.
        """
        self._xray_container = None
        self._container_manager = container_manager

    def create(self, key, secret, region):
        """
        Creates an X-Ray docker container.

        :param string key: AWS access key ID with necessary X-Ray IAM write permissions.
        :param string secret: AWS secret access key.
        :param string region: AWS region where X-Ray segments will be emitted to.

        :raises UserException: If AWS region is missing.
        """
        xray_daemon_envs = {
            'AWS_ACCESS_KEY_ID': key,
            'AWS_SECRET_ACCESS_KEY': secret,
            'AWS_REGION': region
        }

        if not region:
            raise UserException("X-Ray requires an AWS region to be specified using --region or an AWS profile.")

        self._xray_container = XrayContainer(env_vars=xray_daemon_envs)

    def run(self):
        """
        Run an X-Ray docker container.
        """
        self._container_manager.run(self._xray_container)

    def stop(self):
        """
        Stop an X-Ray docker container.
        """
        self._container_manager.stop(self._xray_container)

    def get_daemon_address(self):
        """
        Get IP address of the X-Ray daemon container in the the Docker network.
        """
        client = docker.from_env()
        return client.api.inspect_container(self._xray_container.id)['NetworkSettings']['IPAddress']
