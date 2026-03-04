"""
Unit test for Utils
"""

import os
from parameterized import parameterized
from unittest import TestCase
from unittest.mock import patch, Mock
import docker

from samcli.lib.utils.architecture import InvalidArchitecture
from samcli.local.docker.utils import (
    to_posix_path,
    find_free_port,
    get_rapid_name,
    get_docker_platform,
    get_image_arch,
    is_image_current,
    get_local_image_digest,
    get_remote_image_digest,
)
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


class TestImageDigestUtils(TestCase):
    def setUp(self):
        self.mock_docker_client = Mock()
        self.image_name = "public.ecr.aws/ubuntu/ubuntu:24.04"
        self.test_digest = "sha256:abcd1234"

    def test_get_local_image_digest_success(self):
        """Test getting local image digest successfully"""
        mock_image = Mock()
        mock_image.attrs = {"RepoDigests": [f"{self.image_name}@{self.test_digest}"]}
        self.mock_docker_client.images.get.return_value = mock_image

        result = get_local_image_digest(self.mock_docker_client, self.image_name)

        self.assertEqual(result, self.test_digest)
        self.mock_docker_client.images.get.assert_called_once_with(self.image_name)

    def test_get_local_image_digest_no_repo_digests(self):
        """Test getting local image digest when RepoDigests is empty"""
        mock_image = Mock()
        mock_image.attrs = {"RepoDigests": []}
        self.mock_docker_client.images.get.return_value = mock_image

        result = get_local_image_digest(self.mock_docker_client, self.image_name)

        self.assertIsNone(result)

    def test_get_local_image_digest_image_not_found(self):
        """Test getting local image digest when image doesn't exist"""
        self.mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        result = get_local_image_digest(self.mock_docker_client, self.image_name)

        self.assertIsNone(result)

    def test_get_remote_image_digest_success(self):
        """Test getting remote image digest successfully"""
        mock_registry_data = Mock()
        mock_registry_data.attrs = {"Descriptor": {"digest": self.test_digest}}
        self.mock_docker_client.images.get_registry_data.return_value = mock_registry_data

        result = get_remote_image_digest(self.mock_docker_client, self.image_name)

        self.assertEqual(result, self.test_digest)
        self.mock_docker_client.images.get_registry_data.assert_called_once_with(self.image_name)

    def test_get_remote_image_digest_no_descriptor(self):
        """Test getting remote image digest when descriptor is missing"""
        mock_registry_data = Mock()
        mock_registry_data.attrs = {}
        self.mock_docker_client.images.get_registry_data.return_value = mock_registry_data

        result = get_remote_image_digest(self.mock_docker_client, self.image_name)

        self.assertIsNone(result)

    def test_get_remote_image_digest_exception(self):
        """Test getting remote image digest when an exception occurs"""
        self.mock_docker_client.images.get_registry_data.side_effect = Exception("Network error")

        result = get_remote_image_digest(self.mock_docker_client, self.image_name)

        self.assertIsNone(result)

    def test_is_image_current_when_digests_match(self):
        """Test is_image_current returns True when digests match"""
        mock_image = Mock()
        mock_image.attrs = {"RepoDigests": [f"{self.image_name}@{self.test_digest}"]}
        self.mock_docker_client.images.get.return_value = mock_image

        mock_registry_data = Mock()
        mock_registry_data.attrs = {"Descriptor": {"digest": self.test_digest}}
        self.mock_docker_client.images.get_registry_data.return_value = mock_registry_data

        result = is_image_current(self.mock_docker_client, self.image_name)

        self.assertTrue(result)

    def test_is_image_current_when_digests_differ(self):
        """Test is_image_current returns False when digests differ"""
        mock_image = Mock()
        mock_image.attrs = {"RepoDigests": [f"{self.image_name}@sha256:old1234"]}
        self.mock_docker_client.images.get.return_value = mock_image

        mock_registry_data = Mock()
        mock_registry_data.attrs = {"Descriptor": {"digest": "sha256:new5678"}}
        self.mock_docker_client.images.get_registry_data.return_value = mock_registry_data

        result = is_image_current(self.mock_docker_client, self.image_name)

        self.assertFalse(result)

    def test_is_image_current_when_local_digest_none(self):
        """Test is_image_current returns False when local digest is None"""
        self.mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        mock_registry_data = Mock()
        mock_registry_data.attrs = {"Descriptor": {"digest": self.test_digest}}
        self.mock_docker_client.images.get_registry_data.return_value = mock_registry_data

        result = is_image_current(self.mock_docker_client, self.image_name)

        self.assertFalse(result)
