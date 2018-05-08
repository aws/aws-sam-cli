import docker

from unittest import TestCase
from samcli.local.docker.manager import ContainerManager


class TestContainerManager(TestCase):
    """
    Verifies functionality of ContainerManager by calling Docker APIs
    """
    IMAGE = "busybox"  # small sized Linux container

    @classmethod
    def setUpClass(cls):
        # Make sure we start with a clean slate
        docker_client = docker.from_env()
        TestContainerManager._remove_image(docker_client)

    def setUp(self):
        self.manager = ContainerManager()
        self.docker_client = docker.from_env()

    def tearDown(self):
        self._remove_image(self.docker_client)

    def test_pull_image(self):
        # Image should not exist
        self.assertFalse(self.manager.has_image(self.IMAGE))

        # Pull the image
        self.manager.pull_image(self.IMAGE)

        # Image should be available now
        self.assertTrue(self.manager.has_image(self.IMAGE))

    @classmethod
    def _remove_image(cls, docker_client):
        try:
            docker_client.images.remove(cls.IMAGE)
        except docker.errors.ImageNotFound:
            pass
