"""
Unit test for Container class
"""

import base64
import json
import threading
import time
from unittest import TestCase
from unittest.mock import MagicMock, Mock, call, patch, ANY
from parameterized import parameterized

import docker
from docker.errors import NotFound, APIError
from requests import RequestException

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker.container import (
    Container,
    ContainerContext,
    ContainerResponseException,
    ContainerConnectionTimeoutException,
    PortAlreadyInUse,
)


class TestContainer_init(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"
        self.memory_mb = 123
        self.exposed_ports = {123: 123}
        self.entrypoint = ["a", "b", "c"]
        self.env_vars = {"key": "value"}

        self.mock_docker_client = Mock()

    def test_init_must_store_all_values(self):
        container = Container(
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

        self.assertEqual(self.image, container._image)
        self.assertEqual(self.cmd, container._cmd)
        self.assertEqual(self.working_dir, container._working_dir)
        self.assertEqual(self.host_dir, container._host_dir)
        self.assertEqual(self.exposed_ports, container._exposed_ports)
        self.assertEqual(self.entrypoint, container._entrypoint)
        self.assertEqual(self.env_vars, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)
        self.assertEqual(None, container._network_id)
        self.assertEqual(None, container.id)
        self.assertIsNone(container._concurrency_semaphore)
        self.assertEqual(self.mock_docker_client, container.docker_client)


class TestContainer_create(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"
        self.memory_mb = 123
        self.exposed_ports = {123: 123}
        self.always_exposed_ports = {Container.RAPID_PORT_CONTAINER: ANY}
        self.entrypoint = ["a", "b", "c"]
        self.env_vars = {"key": "value"}
        self.container_opts = {"container": "opts"}
        self.additional_volumes = {"/somepath": {"blah": "blah value"}}
        self.container_host = "localhost"
        self.container_host_interface = "127.0.0.1"
        self.container_context = ContainerContext.BUILD

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.create = Mock()
        self.mock_docker_client.networks = Mock()
        self.mock_docker_client.networks.get = Mock()

    @patch("samcli.local.docker.container.Container._create_mapped_symlink_files")
    def test_must_create_container_with_required_values(self, mock_resolve_symlinks):
        """
        Create a container with only required values. Optional values are not provided
        :return:
        """

        expected_volumes = {self.host_dir: {"bind": self.working_dir, "mode": "ro,delegated"}}
        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            self.host_dir,
            docker_client=self.mock_docker_client,
            exposed_ports=self.exposed_ports,
        )

        container_id = container.create(ContainerContext.INVOKE)
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)
        self.assertIsNotNone(container._concurrency_semaphore)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            volumes=expected_volumes,
            tty=False,
            ports={
                container_port: ("127.0.0.1", host_port)
                for container_port, host_port in {**self.exposed_ports, **self.always_exposed_ports}.items()
            },
            use_config_proxy=True,
        )
        self.mock_docker_client.networks.get.assert_not_called()
        mock_resolve_symlinks.assert_called_with()  # When context is INVOKE

    @patch("samcli.local.docker.container.Container._create_mapped_symlink_files")
    def test_must_create_container_including_all_optional_values(self, mock_resolve_symlinks):
        """
        Create a container with required and optional values.
        :return:
        """

        expected_volumes = {
            self.host_dir: {"bind": self.working_dir, "mode": "ro,delegated"},
            "/somepath": {"blah": "blah value"},
        }
        expected_memory = "{}m".format(self.memory_mb)

        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            self.host_dir,
            memory_limit_mb=self.memory_mb,
            exposed_ports=self.exposed_ports,
            entrypoint=self.entrypoint,
            env_vars=self.env_vars,
            docker_client=self.mock_docker_client,
            container_opts=self.container_opts,
            additional_volumes=self.additional_volumes,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
        )

        container_id = container.create(ContainerContext.BUILD)
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)
        self.assertIsNotNone(container._concurrency_semaphore)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            volumes=expected_volumes,
            tty=False,
            use_config_proxy=True,
            environment=self.env_vars,
            ports={
                container_port: (self.container_host_interface, host_port)
                for container_port, host_port in {**self.exposed_ports, **self.always_exposed_ports}.items()
            },
            entrypoint=self.entrypoint,
            mem_limit=expected_memory,
            container="opts",
        )
        self.mock_docker_client.networks.get.assert_not_called()
        mock_resolve_symlinks.assert_not_called()  # When context is BUILD
        self.assertIsNotNone(container._concurrency_semaphore)

    @patch("samcli.local.docker.utils.os")
    @patch("samcli.local.docker.container.Container._create_mapped_symlink_files")
    def test_must_create_container_translate_volume_path(self, mock_resolve_symlinks, os_mock):
        """
        Create a container with required and optional values, with windows style volume mount.
        :return:
        """

        os_mock.name = "nt"
        host_dir = "C:\\Users\\Username\\AppData\\Local\\Temp\\tmp1337"
        additional_volumes = {"C:\\Users\\Username\\AppData\\Local\\Temp\\tmp1338": {"blah": "blah value"}}

        translated_volumes = {
            "/c/Users/Username/AppData/Local/Temp/tmp1337": {"bind": self.working_dir, "mode": "ro,delegated"}
        }

        translated_additional_volumes = {"/c/Users/Username/AppData/Local/Temp/tmp1338": {"blah": "blah value"}}

        translated_volumes.update(translated_additional_volumes)
        expected_memory = "{}m".format(self.memory_mb)

        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            host_dir,
            memory_limit_mb=self.memory_mb,
            exposed_ports=self.exposed_ports,
            entrypoint=self.entrypoint,
            env_vars=self.env_vars,
            docker_client=self.mock_docker_client,
            container_opts=self.container_opts,
            additional_volumes=additional_volumes,
        )

        container_id = container.create(self.container_context)
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)
        self.assertIsNotNone(container._concurrency_semaphore)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            volumes=translated_volumes,
            tty=False,
            use_config_proxy=True,
            environment=self.env_vars,
            ports={
                container_port: ("127.0.0.1", host_port)
                for container_port, host_port in {**self.exposed_ports, **self.always_exposed_ports}.items()
            },
            entrypoint=self.entrypoint,
            mem_limit=expected_memory,
            container="opts",
        )
        self.mock_docker_client.networks.get.assert_not_called()

    @patch("samcli.local.docker.container.Container._create_mapped_symlink_files")
    def test_must_connect_to_network_on_create(self, mock_resolve_symlinks):
        """
        Create a container with only required values. Optional values are not provided
        :return:
        """
        expected_volumes = {self.host_dir: {"bind": self.working_dir, "mode": "ro,delegated"}}

        network_id = "some id"
        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        network_mock = Mock()
        self.mock_docker_client.networks.get.return_value = network_mock
        network_mock.connect = Mock()

        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )

        container.network_id = network_id

        container_id = container.create(self.container_context)
        self.assertEqual(container_id, generated_id)
        self.assertIsNotNone(container._concurrency_semaphore)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            tty=False,
            use_config_proxy=True,
            volumes=expected_volumes,
            ports=self.always_exposed_ports,
        )

        self.mock_docker_client.networks.get.assert_called_with(network_id)
        network_mock.connect.assert_called_with(container_id)

    @patch("samcli.local.docker.container.Container._initialize_concurrency_control")
    def test_must_initialize_concurrency_control(self, mock_concurrency_control):
        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        # Configure the mock to set _concurrency_semaphore when called
        def side_effect(container_obj=None):
            # This simulates what the real method would do
            self.container._concurrency_semaphore = threading.Semaphore(1)
            return self.container._concurrency_semaphore

        mock_concurrency_control.side_effect = side_effect

        container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            self.host_dir,
            docker_client=self.mock_docker_client,
            exposed_ports=self.exposed_ports,
        )

        # Store the container for the side_effect to use
        self.container = container
        container_id = container.create(ContainerContext.INVOKE)
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)
        mock_concurrency_control.assert_called_once()
        self.assertIsNotNone(container._concurrency_semaphore)

        mock_concurrency_control.assert_called_once()

    @patch("samcli.local.docker.container.Container._create_mapped_symlink_files")
    def test_must_connect_to_host_network_on_create(self, mock_resolve_symlinks):
        """
        Create a container with only required values. Optional values are not provided
        :return:
        """
        expected_volumes = {self.host_dir: {"bind": self.working_dir, "mode": "ro,delegated"}}

        network_id = "host"
        generated_id = "fooobar"
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = generated_id

        network_mock = Mock()
        self.mock_docker_client.networks.get.return_value = network_mock
        network_mock.connect = Mock()

        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )

        container.network_id = network_id

        container_id = container.create(self.container_context)
        self.assertEqual(container_id, generated_id)
        self.assertIsNotNone(container._concurrency_semaphore)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            ports=self.always_exposed_ports,
            tty=False,
            use_config_proxy=True,
            volumes=expected_volumes,
        )

        self.mock_docker_client.networks.get.assert_not_called()

    def test_must_fail_if_already_created(self):
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )

        container.is_created = Mock()
        container.is_created.return_value = True

        with self.assertRaises(RuntimeError):
            container.create(self.container_context)
        self.assertIsNone(container._concurrency_semaphore)

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_must_make_host_tmp_dir_if_mount_with_write_container_build(self, mock_makedirs, mock_exists):
        """Test that create() method creates host tmp directory when mount_with_write is True"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "host_tmp_dir"

        # Mock filesystem operations to ensure complete isolation
        mock_exists.return_value = False

        # Mock the docker client create method to avoid actual container creation
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = "test_id"

        container.create(self.container_context)
        mock_makedirs.assert_called_once_with(container._host_tmp_dir)
        mock_exists.assert_called_once_with(container._host_tmp_dir)

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_no_action_when_mount_with_write_false(self, mock_makedirs, mock_exists):
        """Test that create() method takes no action when mount_with_write is False"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = False
        container._host_tmp_dir = "host_tmp_dir"

        # Mock the docker client create method to avoid actual container creation
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = "test_id"

        container.create(self.container_context)

        # Should not check if directory exists or create it
        mock_exists.assert_not_called()
        mock_makedirs.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_no_action_when_host_tmp_dir_none(self, mock_makedirs, mock_exists):
        """Test that create() method takes no action when host_tmp_dir is None"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = None

        # Mock the docker client create method to avoid actual container creation
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = "test_id"

        container.create(self.container_context)

        # Should not check if directory exists or create it
        mock_exists.assert_not_called()
        mock_makedirs.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_no_action_when_directory_already_exists(self, mock_makedirs, mock_exists):
        """Test that create() method takes no action when directory already exists"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "host_tmp_dir"
        mock_exists.return_value = True  # Directory already exists

        # Mock the docker client create method to avoid actual container creation
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = "test_id"

        container.create(self.container_context)

        # Should check if directory exists but not create it
        mock_exists.assert_called_once_with(container._host_tmp_dir)
        mock_makedirs.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_permission_error_during_directory_creation(self, mock_makedirs, mock_exists):
        """Test that create() method propagates permission errors during directory creation"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "/root/restricted_dir"

        # Mock filesystem operations to ensure complete isolation
        mock_exists.return_value = False
        mock_makedirs.side_effect = PermissionError("Permission denied: '/root/restricted_dir'")

        with self.assertRaises(PermissionError) as context:
            container.create(self.container_context)

        self.assertIn("Permission denied", str(context.exception))
        mock_makedirs.assert_called_once_with(container._host_tmp_dir)
        mock_exists.assert_called_once_with(container._host_tmp_dir)
        # Docker client should not be called since directory creation failed
        self.mock_docker_client.containers.create.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_os_error_during_directory_creation(self, mock_makedirs, mock_exists):
        """Test that create() method propagates OS errors during directory creation"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "/invalid/path/with/nonexistent/parent"

        # Mock filesystem operations to ensure complete isolation
        mock_exists.return_value = False
        mock_makedirs.side_effect = OSError("No such file or directory")

        with self.assertRaises(OSError) as context:
            container.create(self.container_context)

        self.assertIn("No such file or directory", str(context.exception))
        mock_makedirs.assert_called_once_with(container._host_tmp_dir)
        mock_exists.assert_called_once_with(container._host_tmp_dir)
        # Docker client should not be called since directory creation failed
        self.mock_docker_client.containers.create.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_invalid_path_scenarios(self, mock_makedirs, mock_exists):
        """Test that create() method handles invalid path scenarios appropriately"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "/invalid\x00path"  # Path with null character

        # Mock filesystem operations to ensure complete isolation
        mock_exists.return_value = False
        mock_makedirs.side_effect = ValueError("embedded null character")

        # The ValueError should be raised before we even try to create the container
        with self.assertRaises(ValueError) as context:
            container.create(self.container_context)

        self.assertIn("embedded null character", str(context.exception))
        mock_makedirs.assert_called_once_with(container._host_tmp_dir)
        mock_exists.assert_called_once_with(container._host_tmp_dir)
        # Docker client should not be called since directory creation failed
        self.mock_docker_client.containers.create.assert_not_called()

    @patch("samcli.local.docker.container.os.path.exists")
    @patch("samcli.local.docker.container.os.makedirs")
    def test_create_file_exists_error_handled_gracefully(self, mock_makedirs, mock_exists):
        """Test that create() method handles FileExistsError gracefully (race condition scenario)"""
        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        container._mount_with_write = True
        container._host_tmp_dir = "host_tmp_dir"

        # Mock filesystem operations to ensure complete isolation
        mock_exists.return_value = False
        # Simulate race condition where directory is created between exists check and makedirs call
        mock_makedirs.side_effect = FileExistsError("Directory already exists")

        # Mock the docker client create method to avoid actual container creation
        self.mock_docker_client.containers.create.return_value = Mock()
        self.mock_docker_client.containers.create.return_value.id = "test_id"

        # Should not raise an exception - FileExistsError should be handled gracefully
        container_id = container.create(self.container_context)
        self.assertEqual(container_id, "test_id")

        mock_makedirs.assert_called_once_with(container._host_tmp_dir)
        mock_exists.assert_called_once_with(container._host_tmp_dir)


class TestContainer_stop(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()

        self.container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        self.container.id = "someid"

        self.container.is_created = Mock()

    def test_stop_with_timeout(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock
        real_container_mock.remove = Mock()

        self.container.stop(timeout=3)

        self.mock_docker_client.containers.get.assert_called_with("someid")
        real_container_mock.stop.assert_called_with(timeout=3)

        # Ensure ID remains set
        self.assertIsNotNone(self.container.id)

    def test_must_work_when_container_is_not_found(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.side_effect = NotFound("msg")
        real_container_mock.remove = Mock()

        self.container.stop()

        self.mock_docker_client.containers.get.assert_called_with("someid")
        real_container_mock.remove.assert_not_called()

        # Ensure ID remains set
        self.assertIsNotNone(self.container.id)

    def test_must_raise_unknown_docker_api_errors(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock
        real_container_mock.stop = Mock()
        real_container_mock.stop.side_effect = APIError("some error")

        with self.assertRaises(APIError):
            self.container.stop()

        # Ensure ID remains set
        self.assertIsNotNone(self.container.id)

    def test_must_skip_if_container_is_not_created(self):
        self.container.is_created.return_value = False
        self.container.stop()
        self.mock_docker_client.containers.get.assert_not_called()


class TestContainer_delete(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()

        self.container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        self.container.id = "someid"

        self.container.is_created = Mock()

    def test_must_delete(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock
        real_container_mock.remove = Mock()

        self.container.delete()

        self.mock_docker_client.containers.get.assert_called_with("someid")
        real_container_mock.remove.assert_called_with(force=True)

        # Must reset ID to None because container is now gone
        self.assertIsNone(self.container.id)

    def test_must_work_when_container_is_not_found(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.side_effect = NotFound("msg")
        real_container_mock.remove = Mock()

        self.container.delete()

        self.mock_docker_client.containers.get.assert_called_with("someid")
        real_container_mock.remove.assert_not_called()

        # Must reset ID to None because container is now gone
        self.assertIsNone(self.container.id)

    def test_must_work_if_container_delete_is_in_progress(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock
        real_container_mock.remove = Mock()
        real_container_mock.remove.side_effect = APIError("removal of container is already in progress")

        self.container.delete()

        self.mock_docker_client.containers.get.assert_called_with("someid")
        real_container_mock.remove.assert_called_with(force=True)

        # Must reset ID to None because container is now gone
        self.assertIsNone(self.container.id)

    def test_must_raise_unknown_docker_api_errors(self):
        self.container.is_created.return_value = True
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock
        real_container_mock.remove = Mock()
        real_container_mock.remove.side_effect = APIError("some error")

        with self.assertRaises(APIError):
            self.container.delete()

        # Must *NOT* reset ID because Docker API raised an exception
        self.assertIsNotNone(self.container.id)

    def test_must_skip_if_container_is_not_created(self):
        self.container.is_created.return_value = False
        self.container.delete()
        self.mock_docker_client.containers.get.assert_not_called()

    @patch("samcli.local.docker.container.pathlib.Path.exists")
    @patch("samcli.local.docker.container.shutil")
    def test_must_remove_host_tmp_dir_after_mount_with_write_container_build(self, mock_shutil, mock_exists):
        self.container.is_created.return_value = True
        self.container._mount_with_write = True
        self.container._host_tmp_dir = "host_tmp_dir"

        mock_exists.return_value = True
        self.container.delete()
        mock_shutil.rmtree.assert_called_with(self.container._host_tmp_dir)


class TestContainer_start(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()

        self.container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        self.container.id = "someid"

        self.container.is_created = Mock()

    def test_must_start_container(self):
        self.container.is_created.return_value = True

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start = Mock()

        self.container.start()

        self.mock_docker_client.containers.get.assert_called_with(self.container.id)
        container_mock.start.assert_called_with()

    def test_must_not_start_if_container_is_not_created(self):
        self.container.is_created.return_value = False

        with self.assertRaises(RuntimeError):
            self.container.start()

    def test_docker_raises_port_inuse_error(self):
        self.container.is_created.return_value = True

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start.side_effect = PortAlreadyInUse()

        with self.assertRaises(PortAlreadyInUse):
            self.container.start()

    def test_docker_raises_api_error(self):
        self.container.is_created.return_value = True

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start.side_effect = APIError("Mock Error")

        with self.assertRaises(APIError):
            self.container.start()

    def test_must_not_support_input_data(self):
        self.container.is_created.return_value = True

        with self.assertRaises(ValueError):
            self.container.start(input_data="some input data")

    @patch("samcli.local.docker.container.os.path")
    @patch("samcli.local.docker.container.os")
    def test_start_no_longer_creates_directories(self, mock_os, mock_path):
        """Test that start() method no longer creates directories"""
        self.container.is_created.return_value = True
        self.container._mount_with_write = True
        self.container._host_tmp_dir = "host_tmp_dir"
        mock_path.exists.return_value = False  # Directory doesn't exist

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start = Mock()

        # Should not raise an exception, just log a warning
        self.container.start()

        # Should not create the directory
        mock_os.makedirs.assert_not_called()

        # Should still start the container
        container_mock.start.assert_called_with()

    @patch("samcli.local.docker.container.os.path")
    def test_start_works_when_directory_already_exists(self, mock_path):
        """Test that start() method works correctly when directory already exists"""
        self.container.is_created.return_value = True
        self.container._mount_with_write = True
        self.container._host_tmp_dir = "host_tmp_dir"
        mock_path.exists.return_value = True  # Directory exists

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start = Mock()

        # Should work without any issues
        self.container.start()

        # Should start the container
        container_mock.start.assert_called_with()

    @patch("samcli.local.docker.container.os.path")
    def test_start_works_when_mount_with_write_false(self, mock_path):
        """Test that start() method works correctly when mount_with_write is False"""
        self.container.is_created.return_value = True
        self.container._mount_with_write = False
        self.container._host_tmp_dir = "host_tmp_dir"

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start = Mock()

        # Should work without checking directory existence
        self.container.start()

        # Should not check if directory exists
        mock_path.exists.assert_not_called()

        # Should start the container
        container_mock.start.assert_called_with()

    @patch("samcli.local.docker.container.os.path")
    def test_start_works_when_host_tmp_dir_none(self, mock_path):
        """Test that start() method works correctly when host_tmp_dir is None"""
        self.container.is_created.return_value = True
        self.container._mount_with_write = True
        self.container._host_tmp_dir = None

        container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = container_mock
        container_mock.start = Mock()

        # Should work without checking directory existence
        self.container.start()

        # Should not check if directory exists
        mock_path.exists.assert_not_called()

        # Should start the container
        container_mock.start.assert_called_with()


class TestContainer_wait_for_result(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.name = "function_name"
        self.event = "{}"
        self.cmd = ["cmd"]
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"
        self.container_host = "localhost"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()
        self.container = Container(
            self.image,
            self.cmd,
            self.working_dir,
            self.host_dir,
            docker_client=self.mock_docker_client,
            container_host=self.container_host,
        )
        self.container.id = "someid"
        self.container._initialize_concurrency_control()

        self.container.is_created = Mock()
        self.timeout = 1

        self.socket_mock = Mock()
        self.socket_mock.connect_ex.return_value = 0

    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    def test_wait_for_result_no_error_image_response(self, mock_requests, patched_socket):
        self.container.is_created.return_value = True

        rie_response = b"\xff\xab"
        resp_headers = {
            "Date": "Tue, 02 Jan 2024 21:23:31 GMT",
            "Content-Type": "image/jpeg",
            "Transfer-Encoding": "chunked",
        }

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()
        self.container.start_logs_thread_if_not_alive = Mock()
        self.container._create_threading_event = Mock()
        mock_event = Mock()
        self.container._create_threading_event.return_value = mock_event
        self.container._logs_thread_event = mock_event

        stdout_mock = Mock()
        stdout_mock.write_bytes = Mock()
        stderr_mock = Mock()
        response = Mock()
        response.content = rie_response
        response.headers = resp_headers
        mock_requests.post.return_value = response

        patched_socket.return_value = self.socket_mock

        start_timer = Mock()
        timer = Mock()
        start_timer.return_value = timer

        self.container.wait_for_result(
            event=self.event, full_path=self.name, stdout=stdout_mock, stderr=stderr_mock, start_timer=start_timer
        )

        # since we passed in a start_timer function, ensure it's called and
        # the timer is cancelled once execution is done
        start_timer.assert_called()
        timer.cancel.assert_called()

        # make sure we wait for the same host+port that we make the post request to
        host = self.container._container_host
        port = self.container.rapid_port_host
        self.socket_mock.connect_ex.assert_called_with((host, port))
        mock_requests.post.assert_called_with(
            self.container.URL.format(host=host, port=port, function_name="function"),
            data=b"{}",
            headers={"Content-Type": "application/json"},
            timeout=(self.container.RAPID_CONNECTION_TIMEOUT, None),
        )
        stdout_mock.write_bytes.assert_called_with(rie_response)

        # Verify start_logs_thread_if_not_alive is called with stderr mock only
        self.container.start_logs_thread_if_not_alive.assert_called_once_with(stderr_mock)

    @parameterized.expand(
        [
            (True, b'{"hello":"world"}', {"Date": "Tue, 02 Jan 2024 21:23:31 GMT", "Content-Type": "text"}),
            (
                False,
                b"non-json-deserializable",
                {"Date": "Tue, 02 Jan 2024 21:23:31 GMT", "Content-Type": "text/plain"},
            ),
            (False, b"", {"Date": "Tue, 02 Jan 2024 21:23:31 GMT", "Content-Type": "text/plain"}),
        ]
    )
    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    def test_wait_for_result_no_error(
        self, response_deserializable, rie_response, resp_headers, mock_requests, patched_socket
    ):
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()
        self.container._create_threading_event = Mock()
        self.container._create_threading_event.return_value = Mock()

        stdout_mock = Mock()
        stdout_mock.write_str = Mock()
        stderr_mock = Mock()
        response = Mock()
        response.content = rie_response
        response.headers = resp_headers
        mock_requests.post.return_value = response

        patched_socket.return_value = self.socket_mock

        start_timer = Mock()
        timer = Mock()
        start_timer.return_value = timer

        self.container.wait_for_result(
            event=self.event, full_path=self.name, stdout=stdout_mock, stderr=stderr_mock, start_timer=start_timer
        )

        # since we passed in a start_timer function, ensure it's called and
        # the timer is cancelled once execution is done
        start_timer.assert_called()
        timer.cancel.assert_called()

        # make sure we wait for the same host+port that we make the post request to
        host = self.container._container_host
        port = self.container.rapid_port_host
        self.socket_mock.connect_ex.assert_called_with((host, port))
        mock_requests.post.assert_called_with(
            self.container.URL.format(host=host, port=port, function_name="function"),
            data=b"{}",
            headers={"Content-Type": "application/json"},
            timeout=(self.container.RAPID_CONNECTION_TIMEOUT, None),
        )
        if response_deserializable:
            stdout_mock.write_str.assert_called_with(json.dumps(json.loads(rie_response), ensure_ascii=False))
        else:
            stdout_mock.write_str.assert_called_with(rie_response.decode("utf-8"))

    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    @patch("time.sleep")
    def test_wait_for_result_error_retried(self, patched_sleep, mock_requests, patched_socket):
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()
        stdout_mock = Mock()
        stderr_mock = Mock()
        self.container.rapid_port_host = "7077"
        mock_requests.post.side_effect = [RequestException(), RequestException(), RequestException()]

        patched_socket.return_value = self.socket_mock

        with self.assertRaises(ContainerResponseException):
            self.container.wait_for_result(
                event=self.event, full_path=self.name, stdout=stdout_mock, stderr=stderr_mock
            )

        self.assertEqual(mock_requests.post.call_count, 3)
        calls = mock_requests.post.call_args_list
        self.assertEqual(
            calls,
            [
                call(
                    "http://localhost:7077/2015-03-31/functions/function/invocations",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    timeout=(self.timeout, None),
                ),
                call(
                    "http://localhost:7077/2015-03-31/functions/function/invocations",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    timeout=(self.timeout, None),
                ),
                call(
                    "http://localhost:7077/2015-03-31/functions/function/invocations",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    timeout=(self.timeout, None),
                ),
            ],
        )

    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    @patch("time.sleep")
    def test_wait_for_result_error(self, patched_sleep, mock_requests, patched_socket):
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()
        self.container._create_threading_event = Mock()
        self.container._create_threading_event.return_value = Mock()

        stdout_mock = Mock()
        stderr_mock = Mock()
        mock_requests.post.side_effect = ContainerResponseException()

        patched_socket.return_value = self.socket_mock
        with self.assertRaises(ContainerResponseException):
            self.container.wait_for_result(
                event=self.event, full_path=self.name, stdout=stdout_mock, stderr=stderr_mock
            )

    # set timeout to be 0.1ms
    @patch("samcli.local.docker.container.CONTAINER_CONNECTION_TIMEOUT", 0.0001)
    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    @patch("time.sleep")
    def test_wait_for_result_waits_for_socket_before_post_request(self, patched_time, mock_requests, patched_socket):
        self.container.is_created.return_value = True
        mock_requests.post = Mock(return_value=None)
        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()

        stdout_mock = Mock()
        stderr_mock = Mock()

        unsuccessful_socket_mock = Mock()
        unsuccessful_socket_mock.connect_ex.return_value = 22
        patched_socket.return_value = unsuccessful_socket_mock
        with self.assertRaises(ContainerConnectionTimeoutException):
            self.container.wait_for_result(
                event=self.event, full_path=self.name, stdout=stdout_mock, stderr=stderr_mock
            )

        self.assertEqual(mock_requests.post.call_count, 0)

    @parameterized.expand(
        [
            (True, b'{"result": "success"}', {"Content-Type": "application/json"}),
        ]
    )
    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    def test_wait_for_result_with_tenant_id(
        self, response_deserializable, rie_response, resp_headers, mock_requests, patched_socket
    ):
        """Test that tenant_id is passed as header when provided"""
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()
        self.container._create_threading_event = Mock()
        self.container._create_threading_event.return_value = Mock()

        stdout_mock = Mock()
        stdout_mock.write_str = Mock()
        stderr_mock = Mock()
        response = Mock()
        response.content = rie_response
        response.headers = resp_headers
        mock_requests.post.return_value = response

        patched_socket.return_value = self.socket_mock

        tenant_id = "test-tenant-123"

        self.container.wait_for_result(
            event=self.event,
            full_path=self.name,
            stdout=stdout_mock,
            stderr=stderr_mock,
            tenant_id=tenant_id,
        )

        # Verify that the POST request was called with tenant_id header
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertIn("headers", call_args.kwargs)
        self.assertEqual(call_args.kwargs["headers"]["X-Amz-Tenant-Id"], tenant_id)

    def test_write_container_output_successful(self):
        stdout_mock = Mock(spec=StreamWriter)
        stderr_mock = Mock(spec=StreamWriter)

        def _output_iterator():
            yield b"Hello", None
            yield None, b"World"
            raise ValueError("The pipe has been ended.")

        Container._write_container_output(_output_iterator(), stdout_mock, stderr_mock)
        stdout_mock.assert_has_calls([call.write_str("Hello")])
        stderr_mock.assert_has_calls([call.write_str("World")])


class TestContainer_wait_for_logs(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = ["cmd"]
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()

        self.container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        self.container.id = "someid"

        self.container.is_created = Mock()

    def test_must_fetch_stdout_and_stderr_data(self):
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()

        stdout_mock = Mock()
        stderr_mock = Mock()

        self.container.wait_for_logs(stdout=stdout_mock, stderr=stderr_mock)

        real_container_mock.attach.assert_called_with(stream=True, logs=True, demux=True)
        self.container._write_container_output.assert_called_with(
            output_itr, stdout=stdout_mock, stderr=stderr_mock, event=None
        )

    def test_must_skip_if_no_stdout_and_stderr(self):
        self.container.wait_for_logs()
        self.mock_docker_client.containers.get.assert_not_called()

    def test_must_raise_if_container_is_not_created(self):
        self.container.is_created.return_value = False

        with self.assertRaises(RuntimeError):
            self.container.wait_for_logs(stdout=Mock())

    @patch("samcli.local.docker.container.threading")
    def test_start_logs_thread_if_not_alive_creates_new_thread_when_none_exists(self, mock_threading):
        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.is_alive.return_value = False

        stderr_mock = Mock()

        self.container.start_logs_thread_if_not_alive(stderr_mock)

        mock_threading.Thread.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch("samcli.local.docker.container.threading")
    def test_start_logs_thread_if_not_alive_reuses_existing_thread_when_alive(self, mock_threading):
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.container._logs_thread = mock_thread

        stderr_mock = Mock()

        self.container.start_logs_thread_if_not_alive(stderr_mock)

        mock_threading.Thread.assert_not_called()
        mock_thread.start.assert_not_called()


class TestContainer_write_container_output(TestCase):
    def setUp(self):
        self.output_itr = [(b"stdout1", None), (None, b"stderr1"), (b"stdout2", b"stderr2"), (None, None)]

        self.stdout_mock = Mock(spec=StreamWriter)
        self.stderr_mock = Mock(spec=StreamWriter)

    def test_must_write_stdout_and_stderr_data(self):
        # All the invalid frames must be ignored

        Container._write_container_output(self.output_itr, stdout=self.stdout_mock, stderr=self.stderr_mock)

        self.stdout_mock.write_str.assert_has_calls([call("stdout1"), call("stdout2")])

        self.stderr_mock.write_str.assert_has_calls([call("stderr1"), call("stderr2")])

    def test_must_write_only_stderr(self):
        # All the invalid frames must be ignored

        Container._write_container_output(self.output_itr, stdout=None, stderr=self.stderr_mock)

        self.stdout_mock.write_str.assert_not_called()

        self.stderr_mock.write_str.assert_has_calls([call("stderr1"), call("stderr2")])

    def test_must_write_only_stdout(self):
        Container._write_container_output(self.output_itr, stdout=self.stdout_mock, stderr=None)

        self.stdout_mock.write_str.assert_has_calls([call("stdout1"), call("stdout2")])

        self.stderr_mock.write_str.assert_not_called()  # stderr must never be called


class TestContainer_wait_for_socket_connection(TestCase):
    def setUp(self):
        self.image = IMAGE
        self.cmd = "cmd"
        self.working_dir = "working_dir"
        self.host_dir = "host_dir"

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.get = Mock()

        self.container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )
        self.container.id = "someid"

    @patch("samcli.local.docker.container.CONTAINER_CONNECTION_TIMEOUT", 0)
    @patch("socket.socket")
    def test_times_out_if_unable_to_connect(self, patched_socket):
        socket_mock = Mock()
        socket_mock.connect_ex.return_value = 22
        patched_socket.return_value = socket_mock

        with self.assertRaises(
            ContainerConnectionTimeoutException,
            msg=(
                "Timed out while attempting to establish a connection to the container. "
                "You can increase this timeout by setting the "
                "SAM_CLI_CONTAINER_CONNECTION_TIMEOUT environment variable. The current timeout is 0 (seconds)."
            ),
        ):
            self.container._wait_for_socket_connection()

    @patch("socket.socket")
    def test_does_not_time_out_if_able_to_connect(self, patched_socket):
        socket_mock = Mock()
        socket_mock.connect_ex.return_value = 0
        patched_socket.return_value = socket_mock

        self.container._wait_for_socket_connection()


class TestContainer_image(TestCase):
    def test_must_return_image_value(self):
        image = "myimage"
        mock_docker_client = Mock()
        container = Container(image, "cmd", "dir", "dir", docker_client=mock_docker_client)

        self.assertEqual(image, container.image)


class TestContainer_copy(TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.container = Container(IMAGE, "cmd", "dir", "dir", docker_client=self.mock_client)
        self.container.id = "containerid"

    @patch("samcli.local.docker.container.tempfile")
    @patch("samcli.local.docker.container.extract_tarfile")
    def test_must_copy_files_from_container(self, extract_tarfile_mock, tempfile_mock):
        source = "source"
        dest = "dest"

        tar_stream = [1, 2, 3]

        # Mock the container client's get_archive method
        self.mock_client.get_archive.return_value = (tar_stream, "ignored")

        tempfile_ctxmgr = tempfile_mock.NamedTemporaryFile.return_value = Mock()
        fp_mock = Mock()
        tempfile_ctxmgr.__enter__ = Mock(return_value=fp_mock)
        tempfile_ctxmgr.__exit__ = Mock()

        self.container.copy(source, dest)

        # Verify get_archive was called with container ID and source path
        self.mock_client.get_archive.assert_called_with("containerid", source)

        extract_tarfile_mock.assert_called_with(file_obj=fp_mock, unpack_dir=dest)

        # Make sure archive data is written to the file
        fp_mock.write.assert_has_calls([call(x) for x in tar_stream], any_order=False)

        # Make sure we open the tarfile right and extract to right location

    def test_raise_if_container_is_not_created(self):
        source = "source"
        dest = "dest"

        self.container.is_created = Mock()
        self.container.is_created.return_value = False

        with self.assertRaises(RuntimeError):
            self.container.copy(source, dest)


class TestContainer_is_created(TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.container = Container("image", "cmd", "dir", "dir", docker_client=self.mock_client)

    def test_container_id_is_none_return_false(self):
        self.container.id = None
        self.assertFalse(self.container.is_created())

    def test_real_container_is_not_exist_return_false(self):
        self.container.id = "not_exist"
        self.mock_client.containers.get.side_effect = docker.errors.NotFound("")
        self.assertFalse(self.container.is_created())

    def test_real_container_exist_return_true(self):
        self.container.id = "not_exist"
        self.assertTrue(self.container.is_created())


class TestContainer_is_running(TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.container = Container("image", "cmd", "dir", "dir", docker_client=self.mock_client)

    def test_container_id_is_none_return_false(self):
        self.container.id = None
        self.assertFalse(self.container.is_running())

    def test_real_container_is_not_exist_return_false(self):
        self.container.id = "not_exist"
        self.mock_client.containers.get.side_effect = docker.errors.NotFound("")
        self.assertFalse(self.container.is_running())

    def test_real_container_status_is_not_running_return_false(self):
        self.container.id = "not_exist"
        real_container_mock = Mock()
        real_container_mock.status = "stopped"
        self.mock_client.containers.get.return_value = real_container_mock

        self.assertFalse(self.container.is_running())

    def test_real_container_is_running_return_true(self):
        self.container.id = "not_exist"
        real_container_mock = Mock()
        real_container_mock.status = "running"
        self.mock_client.containers.get.return_value = real_container_mock
        self.assertTrue(self.container.is_created())


class TestContainer_create_mapped_symlink_files(TestCase):
    def setUp(self):
        self.container = Container(Mock(), Mock(), Mock(), "host_dir", docker_client=Mock())

        self.mock_symlinked_file = MagicMock()
        self.mock_symlinked_file.is_symlink.return_value = True

        self.mock_regular_file = MagicMock()
        self.mock_regular_file.is_symlink.return_value = False

    @patch("samcli.local.docker.container.pathlib.Path.exists")
    @patch("samcli.local.docker.container.os.scandir")
    def test_no_symlinks_returns_empty(self, mock_scandir, mock_exists):
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=[self.mock_regular_file])
        mock_scandir.return_value = mock_context
        mock_exists.return_value = True

        volumes = self.container._create_mapped_symlink_files()

        self.assertEqual(volumes, {})

    @patch("samcli.local.docker.container.pathlib.Path.exists")
    def test_host_dir_does_not_exist_returns_empty_symlinks(self, mock_exists):
        mock_exists.return_value = False
        volumes = self.container._create_mapped_symlink_files()

        self.assertEqual(volumes, {})

    @patch("samcli.local.docker.container.os.scandir")
    @patch("samcli.local.docker.container.os.path.basename")
    @patch("samcli.local.docker.container.os.path.realpath")
    @patch("samcli.local.docker.container.pathlib.Path")
    def test_resolves_symlink(self, mock_path, mock_realpath, mock_basename, mock_scandir):
        host_path = Mock()
        container_path = Mock()

        mock_realpath.return_value = host_path
        mock_basename.return_value = "node_modules"
        mock_as_posix = Mock()
        mock_as_posix.as_posix = Mock(return_value=container_path)
        mock_path.return_value = mock_as_posix

        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=[self.mock_symlinked_file])
        mock_scandir.return_value = mock_context

        volumes = self.container._create_mapped_symlink_files()

        self.assertEqual(volumes, {host_path: {"bind": container_path, "mode": ANY}})


class TestContainer_concurrency_control(TestCase):
    def setUp(self):
        self.container = Container(
            image="test-image",
            cmd=["test-cmd"],
            working_dir="/test",
            host_dir="/host",
            memory_limit_mb=128,
            exposed_ports={"8080": "8080"},
            entrypoint=["test-entrypoint"],
            env_vars={"TEST_VAR": "test_value"},
            docker_client=Mock(),
            container_host="127.0.0.1",
            container_host_interface="127.0.0.1",
        )
        self.assertIsNone(self.container._concurrency_semaphore)

    def test_initialize_concurrency_control_default(self):
        """Test concurrency control initialization with default values"""
        # No AWS_LAMBDA_MAX_CONCURRENCY in env vars
        self.container._env_vars = {}

        self.container._initialize_concurrency_control()

        self.assertEqual(self.container._max_concurrency, 1)
        self.assertIsNotNone(self.container._concurrency_semaphore)
        self.assertEqual(self.container._concurrency_semaphore._value, 1)

    def test_initialize_concurrency_control_with_max_concurrency(self):
        """Test concurrency control initialization with AWS_LAMBDA_MAX_CONCURRENCY"""
        # Set AWS_LAMBDA_MAX_CONCURRENCY in env vars
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "8"}

        self.container._initialize_concurrency_control()

        self.assertEqual(self.container._max_concurrency, 8)
        self.assertIsNotNone(self.container._concurrency_semaphore)
        self.assertEqual(self.container._concurrency_semaphore._value, 8)

    def test_initialize_concurrency_control_invalid_value(self):
        """Test concurrency control initialization with invalid AWS_LAMBDA_MAX_CONCURRENCY"""
        # Set invalid AWS_LAMBDA_MAX_CONCURRENCY in env vars
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "invalid"}

        with patch("samcli.local.docker.container.LOG") as mock_log:
            self.container._initialize_concurrency_control()

            # Should default to 1 and log warning
            self.assertEqual(self.container._max_concurrency, 1)
            self.assertIsNotNone(self.container._concurrency_semaphore)
            self.assertEqual(self.container._concurrency_semaphore._value, 1)
            mock_log.warning.assert_called_once()

    def test_initialize_concurrency_control_idempotent(self):
        """Test that concurrency control initialization is idempotent (safe to call multiple times)"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "4"}

        # Initialize once
        self.container._initialize_concurrency_control()
        first_semaphore = self.container._concurrency_semaphore

        # Initialize again - should not create a new semaphore
        self.container._initialize_concurrency_control()
        second_semaphore = self.container._concurrency_semaphore

        # Should be the same semaphore object
        self.assertIs(first_semaphore, second_semaphore)
        self.assertEqual(self.container._max_concurrency, 4)
        self.assertEqual(self.container._concurrency_semaphore._value, 4)

    def test_initialize_concurrency_control_debug_mode_forces_concurrency_one(self):
        """Test that debug mode forces concurrency to 1 regardless of AWS_LAMBDA_MAX_CONCURRENCY"""

        # Set high concurrency in env vars
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "10"}

        # Set debug options with debug ports (indicating debug mode)
        debug_options = DebugContext(
            debug_ports=[5858], debugger_path="/path/to/debugger", debug_args="--debug", debug_function="test_func"
        )
        self.container.debug_options = debug_options

        with patch("samcli.local.docker.container.LOG") as mock_log:
            self.container._initialize_concurrency_control()

            # Should force concurrency to 1 in debug mode
            self.assertEqual(self.container._max_concurrency, 1)
            self.assertIsNotNone(self.container._concurrency_semaphore)
            self.assertEqual(self.container._concurrency_semaphore._value, 1)

            # Should log container initialization
            mock_log.debug.assert_any_call("Initialized container %s with max_concurrency=%d", "unknown", 1)

    def test_initialize_concurrency_control_no_debug_mode_uses_env_var(self):
        """Test that non-debug mode uses AWS_LAMBDA_MAX_CONCURRENCY normally"""

        # Set high concurrency in env vars
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "8"}

        # Set debug options without debug ports (not in debug mode)
        debug_options = DebugContext(debug_ports=None, debugger_path=None, debug_args=None, debug_function="test_func")
        self.container.debug_options = debug_options

        self.container._initialize_concurrency_control()

        # Should use the env var value since not in debug mode
        self.assertEqual(self.container._max_concurrency, 8)
        self.assertIsNotNone(self.container._concurrency_semaphore)
        self.assertEqual(self.container._concurrency_semaphore._value, 8)

    def test_get_max_concurrency(self):
        """Test get_max_concurrency method"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "6"}

        # Initialize concurrency control (simulating what create() does)
        self.container._initialize_concurrency_control()

        # Should return max concurrency without additional initialization
        max_concurrency = self.container.get_max_concurrency()

        self.assertEqual(max_concurrency, 6)
        self.assertIsNotNone(self.container._concurrency_semaphore)

    @patch("samcli.local.docker.container.requests.post")
    def test_wait_for_http_response_single_thread(self, mock_post):
        """Test HTTP response with single thread (traditional function)"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "1"}

        # Initialize concurrency control (simulating what create() does)
        self.container._initialize_concurrency_control()

        # Mock response properly
        mock_response = Mock()
        mock_response.text = "response"
        mock_response.content = b'{"result": "success"}'
        mock_response.headers = {}
        mock_post.return_value = mock_response

        # Mock container properties
        self.container.id = "test-container-id"
        self.container.rapid_port_host = 8080
        self.container._container_host = "127.0.0.1"

        with patch("samcli.local.docker.container.LOG") as mock_log:
            response, is_error = self.container.wait_for_http_response("test-function", "test-event", Mock())

            self.assertEqual(response, '{"result": "success"}')
            self.assertFalse(is_error)

            # Should log semaphore acquisition
            mock_log.debug.assert_called()

    @patch("samcli.local.docker.container.requests.post")
    def test_wait_for_http_response_multi_thread(self, mock_post):
        """Test HTTP response with multiple threads (lmi function)"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "3"}

        # Initialize concurrency control (simulating what create() does)
        self.container._initialize_concurrency_control()

        # Mock response properly
        mock_response = Mock()
        mock_response.text = "response"
        mock_response.content = b'{"result": "success"}'
        mock_response.headers = {}
        mock_post.return_value = mock_response

        # Mock container properties
        self.container.id = "test-container-id"
        self.container.rapid_port_host = 8080
        self.container._container_host = "127.0.0.1"

        results = []
        errors = []

        def make_request(event_data):
            try:
                response, is_error = self.container.wait_for_http_response(
                    "test-function", f"event-{event_data}", Mock()
                )
                results.append((response, is_error))
            except Exception as e:
                errors.append(e)

        # Start multiple concurrent requests
        threads = []
        for i in range(5):  # More threads than max concurrency
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should complete successfully
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)

        # All should return the same response
        for response, is_error in results:
            self.assertEqual(response, '{"result": "success"}')
            self.assertFalse(is_error)

    @patch("samcli.local.docker.container.requests.post")
    def test_concurrency_semaphore_limiting(self, mock_post):
        """Test that semaphore properly limits concurrent requests"""
        max_concurrency = 2
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": str(max_concurrency)}

        # Initialize concurrency control (simulating what create() does)
        self.container._initialize_concurrency_control()

        # Track concurrent executions inside the semaphore
        concurrent_count = 0
        max_concurrent_observed = 0
        lock = threading.Lock()

        # Mock slow response to test concurrency limiting
        def slow_response(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent_observed
            with lock:
                concurrent_count += 1
                max_concurrent_observed = max(max_concurrent_observed, concurrent_count)

            time.sleep(0.1)  # Simulate slow response

            with lock:
                concurrent_count -= 1

            response = Mock()
            response.text = "response"
            response.content = b'{"result": "success"}'
            response.headers = {}
            return response

        mock_post.side_effect = slow_response

        # Mock container properties
        self.container.id = "test-container-id"
        self.container.rapid_port_host = 8080
        self.container._container_host = "127.0.0.1"

        def make_request():
            self.container.wait_for_http_response("test-function", "test-event", Mock())

        # Start more threads than max concurrency
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should never exceed max concurrency
        self.assertLessEqual(max_concurrent_observed, max_concurrency)

    @patch("samcli.local.docker.container.requests.post")
    def test_semaphore_fallback_warning(self, mock_post):
        """Test fallback behavior when semaphore is not available (edge case)"""
        # Mock response properly
        mock_response = Mock()
        mock_response.text = "response"
        mock_response.content = b'{"result": "success"}'
        mock_response.headers = {}
        mock_post.return_value = mock_response

        # Mock container properties
        self.container.id = "test-container-id"
        self.container.rapid_port_host = 8080
        self.container._container_host = "127.0.0.1"
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "1"}

        with patch("samcli.local.docker.container.LOG") as mock_log:
            response, is_error = self.container.wait_for_http_response("test-function", "test-event", Mock())

            self.assertEqual(response, '{"result": "success"}')
            self.assertFalse(is_error)

            # Should log warning about fallback
            mock_log.warning.assert_called_with(
                "Container concurrency control not initiated properly during container creation"
            )

    @parameterized.expand(
        [
            ("1", 1),
            ("4", 4),
            ("8", 8),
            ("16", 16),
        ]
    )
    def test_various_concurrency_levels(self, concurrency_str, expected_concurrency):
        """Test various concurrency levels"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": concurrency_str}

        self.container._initialize_concurrency_control()

        self.assertEqual(self.container._max_concurrency, expected_concurrency)
        self.assertEqual(self.container._concurrency_semaphore._value, expected_concurrency)

    def test_concurrency_control_logging(self):
        """Test that concurrency control logs appropriate debug information"""
        self.container._env_vars = {"AWS_LAMBDA_MAX_CONCURRENCY": "4"}
        self.container.id = "test-container-id"

        with patch("samcli.local.docker.container.LOG") as mock_log:
            self.container._initialize_concurrency_control()

            # Should log initialization
            mock_log.debug.assert_called_with(
                "Initialized container %s with max_concurrency=%d", "test-container-id", 4
            )

    def test_concurrency_without_env_vars(self):
        """Test concurrency control when no environment variables are set"""
        self.container._env_vars = None

        self.container._initialize_concurrency_control()

        self.assertEqual(self.container._max_concurrency, 1)
        self.assertIsNotNone(self.container._concurrency_semaphore)
        self.assertEqual(self.container._concurrency_semaphore._value, 1)
