from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.utils.packagetype import IMAGE
from samcli.local.docker.container import Container
from samcli.local.docker.container_analyzer import ContainerAnalyzer, ContainerState
from samcli.local.docker.manager import ContainerManager


class TestContainerAnalyzer(TestCase):
    def setUp(self) -> None:
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"
        self.memory_mb = 123
        self.exposed_ports = {123: 123}
        self.entrypoint = ["a", "b", "c"]
        self.env_vars = {"key": "value"}

        self.mock_docker_client = Mock()

        self.container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            self.host_dir,
            self.memory_mb,
            self.exposed_ports,
            self.entrypoint,
            self.env_vars,
            self.mock_docker_client,
        )

    @patch("samcli.local.docker.container_analyzer.LOG")
    def test_inspect_returns_container_state(self, mock_log):
        self.container.id = "id"
        manager = ContainerManager()
        manager.inspect = Mock()
        manager.inspect.return_value = {"State": {"OOMKilled": True}}

        analyzer = ContainerAnalyzer(container_manager=manager, container=self.container)
        state = analyzer.inspect()

        manager.inspect.assert_called_once_with("id")
        mock_log.debug.assert_called_once_with("[Container state] OOMKilled %s", True)
        self.assertEqual(state, ContainerState(out_of_memory=True))

    def test_inspect_no_container_id(self):
        manager = ContainerManager()
        manager.inspect = Mock()

        analyzer = ContainerAnalyzer(container_manager=manager, container=self.container)
        state = analyzer.inspect()

        manager.inspect.assert_not_called()
        self.assertEqual(state, ContainerState(out_of_memory=False))

    def test_inspect_docker_call_fails(self):
        self.container.id = "id"
        manager = ContainerManager()
        manager.inspect = Mock()
        manager.inspect.return_value = False

        analyzer = ContainerAnalyzer(container_manager=manager, container=self.container)
        state = analyzer.inspect()

        manager.inspect.assert_called_once_with("id")
        self.assertEqual(state, ContainerState(out_of_memory=False))
