from unittest import TestCase
from unittest.mock import patch, Mock


from samcli.lib.utils.system_info import (
    gather_system_info,
    gather_additional_dependencies_info,
    _gather_cdk_info,
    _gather_docker_info,
    _gather_terraform_info,
)


class TestSystemInfo(TestCase):
    @patch("platform.platform")
    @patch("platform.python_version")
    def test_gather_system_info(self, python_version_mock, platform_mock):
        python_version_mock.return_value = "1.2.3"
        platform_mock.return_value = "some_system"
        result = gather_system_info()
        self.assertEqual(result, {"python": "1.2.3", "os": "some_system"})

    @patch("samcli.lib.utils.system_info._gather_docker_info")
    @patch("samcli.lib.utils.system_info._gather_cdk_info")
    @patch("samcli.lib.utils.system_info._gather_terraform_info")
    def test_gather_additional_dependencies_info(self, terraform_info_mock, cdk_info_mock, docker_info_mock):
        docker_info_mock.return_value = "1.1.1"
        cdk_info_mock.return_value = "2.2.2"
        terraform_info_mock.return_value = "3.3.3"
        result = gather_additional_dependencies_info()
        self.assertEqual(result, {"docker_engine": "1.1.1", "aws_cdk": "2.2.2", "terraform": "3.3.3"})

    @patch("docker.from_env")
    @patch("samcli.local.docker.utils.is_docker_reachable")
    def test_gather_docker_info_when_client_is_reachable(self, is_docker_reachable_mock, from_env_mock):
        docker_client_mock = Mock()
        is_docker_reachable_mock.return_value = True
        docker_client_mock.version.return_value = {"Version": "1.1.1"}
        from_env_mock.return_value = docker_client_mock
        result = _gather_docker_info()
        self.assertEqual(result, "1.1.1")

    @patch("docker.from_env")
    @patch("samcli.local.docker.utils.is_docker_reachable")
    def test_gather_docker_info_when_client_is_not_reachable(self, is_docker_reachable_mock, from_env_mock):
        is_docker_reachable_mock.return_value = False
        result = _gather_docker_info()
        self.assertEqual(result, "Not available")

    @patch("subprocess.run")
    def test_gather_cdk_info_when_cdk_is_available(self, run_mock):
        process_mock = Mock()
        process_mock.stdout = "1.1.1\n"
        run_mock.return_value = process_mock
        result = _gather_cdk_info()
        self.assertEqual(result, "1.1.1")

    @patch("subprocess.run")
    def test_gather_cdk_info_when_cdk_is_not_available(self, run_mock):
        run_mock.side_effect = FileNotFoundError
        result = _gather_cdk_info()
        self.assertEqual(result, "Not available")

    @patch("subprocess.run")
    def test_gather_terraform_info_when_terraform_is_available(self, run_mock):
        process_mock = Mock()
        process_mock.stdout = """
        {
            "terraform_version": "1.1.1"
        }"""
        run_mock.return_value = process_mock
        result = _gather_terraform_info()
        self.assertEqual(result, "1.1.1")

    @patch("subprocess.run")
    def test_gather_terraform_info_when_terraform_is_not_available(self, process_mock):
        process_mock.side_effect = FileNotFoundError
        result = _gather_terraform_info()
        self.assertEqual(result, "Not available")
