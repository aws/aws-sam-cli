from unittest import TestCase

from samcli.local.docker.container_engine import ContainerEngine


class TestContainerEngine(TestCase):
    def test_enum_values(self):
        """Test that enum values are correct"""
        self.assertEqual(ContainerEngine.FINCH.value, "finch")
        self.assertEqual(ContainerEngine.DOCKER.value, "docker")

    def test_enum_membership(self):
        """Test enum membership checks"""
        supported_runtimes = {runtime.value for runtime in ContainerEngine}
        self.assertIn("finch", supported_runtimes)
        self.assertIn("docker", supported_runtimes)
        self.assertNotIn("podman", supported_runtimes)
        self.assertNotIn("containerd", supported_runtimes)
