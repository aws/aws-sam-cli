"""
Unit test for Utils
"""

import os
from parameterized import parameterized
from unittest import TestCase
from unittest.mock import patch, Mock
from samcli.lib.utils.architecture import InvalidArchitecture
from samcli.local.docker.utils import to_posix_path, find_free_port, get_rapid_name, get_docker_platform, get_image_arch
from samcli.local.docker.exceptions import NoFreePortsError


class TestPosixPath(TestCase):
    def setUp(self):
        self.ntpath = "C:\\Users\\UserName\\AppData\\Local\\Temp\\temp1337"
        self.posixpath = "/c/Users/UserName/AppData/Local/Temp/temp1337"
        self.current_working_dir = os.getcwd()

    @patch("samcli.local.docker.utils.os")
    def test_convert_posix_path_if_windows_style_path(self, mock_os):
        mock_os.name = "nt"
        self.assertEqual(self.posixpath, to_posix_path(self.ntpath))

    @patch("samcli.local.docker.utils.os")
    def test_do_not_convert_posix_path(self, mock_os):
        mock_os.name = "posix"
        self.assertEqual(self.current_working_dir, to_posix_path(self.current_working_dir))


class TestFreePorts(TestCase):
    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_first_attempt(self, network_interface, mock_random, mock_socket):
        mock_random.randrange = Mock(side_effect=[3093] * 1000)
        port = find_free_port(network_interface, start=3000, end=4000)
        self.assertEqual(port, 3093)

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_second_attempt(self, network_interface, mock_random, mock_socket):
        mock_socket.socket.return_value.bind.side_effect = [OSError, None]
        mock_random.randrange = Mock(side_effect=[3093, 3094] * 1000)
        port = find_free_port(network_interface, start=3000, end=4000)
        self.assertEqual(port, 3094)

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_no_free_ports(self, network_interface, mock_random, mock_socket):
        mock_socket.socket.return_value.bind.side_effect = OSError
        mock_random.randrange = Mock(side_effect=[3093] * 1000)
        with self.assertRaises(NoFreePortsError):
            find_free_port(network_interface, start=3000, end=4000)


class TestGetRapidName(TestCase):
    @parameterized.expand([("x86_64", "aws-lambda-rie-x86_64"), ("arm64", "aws-lambda-rie-arm64")])
    def test_get_rapid_name(self, architecture, expected_name):
        self.assertEqual(get_rapid_name(architecture), expected_name)

    def test_get_rapid_name_invalid_architecture(self):
        with self.assertRaises(InvalidArchitecture):
            get_rapid_name("invalid")


class TestImageArch(TestCase):
    @parameterized.expand([("x86_64", "amd64"), ("arm64", "arm64")])
    def test_get_image_arch(self, architecture, expected_arch):
        self.assertEqual(get_image_arch(architecture), expected_arch)

    def test_get_image_arch_invalid_architecture(self):
        with self.assertRaises(InvalidArchitecture):
            get_image_arch("invalid")


class TestGetDockerPlatform(TestCase):
    @parameterized.expand([("x86_64", "linux/amd64"), ("arm64", "linux/arm64")])
    def test_get_docker_platform(self, architecture, expected_platform):
        self.assertEqual(get_docker_platform(architecture), expected_platform)

    def test_get_docker_platform_invalid_architecture(self):
        with self.assertRaises(InvalidArchitecture):
            get_docker_platform("invalid")
