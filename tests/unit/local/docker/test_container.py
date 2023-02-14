"""
Unit test for Container class
"""
import docker
from docker.errors import NotFound, APIError
from unittest import TestCase
from unittest.mock import Mock, call, patch, ANY

from requests import RequestException

from samcli.lib.utils.packagetype import IMAGE
from samcli.local.docker.container import Container, ContainerResponseException, ContainerConnectionTimeoutException


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

        self.mock_docker_client = Mock()
        self.mock_docker_client.containers = Mock()
        self.mock_docker_client.containers.create = Mock()
        self.mock_docker_client.networks = Mock()
        self.mock_docker_client.networks.get = Mock()

    def test_must_create_container_with_required_values(self):
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

        container_id = container.create()
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)

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

    def test_must_create_container_including_all_optional_values(self):
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

        container_id = container.create()
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)

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

    @patch("samcli.local.docker.utils.os")
    def test_must_create_container_translate_volume_path(self, os_mock):
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

        container_id = container.create()
        self.assertEqual(container_id, generated_id)
        self.assertEqual(container.id, generated_id)

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

    def test_must_connect_to_network_on_create(self):
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

        container_id = container.create()
        self.assertEqual(container_id, generated_id)

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

    def test_must_connect_to_host_network_on_create(self):
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

        container_id = container.create()
        self.assertEqual(container_id, generated_id)

        self.mock_docker_client.containers.create.assert_called_with(
            self.image,
            command=self.cmd,
            working_dir=self.working_dir,
            ports=self.always_exposed_ports,
            tty=False,
            use_config_proxy=True,
            volumes=expected_volumes,
            network_mode="host",
        )

        self.mock_docker_client.networks.get.assert_not_called()

    def test_must_fail_if_already_created(self):

        container = Container(
            self.image, self.cmd, self.working_dir, self.host_dir, docker_client=self.mock_docker_client
        )

        container.is_created = Mock()
        container.is_created.return_value = True

        with self.assertRaises(RuntimeError):
            container.create()


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

    def test_must_not_support_input_data(self):

        self.container.is_created.return_value = True

        with self.assertRaises(ValueError):
            self.container.start(input_data="some input data")


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

        self.container.is_created = Mock()
        self.timeout = 1

        self.socket_mock = Mock()
        self.socket_mock.connect_ex.return_value = 0

    @patch("socket.socket")
    @patch("samcli.local.docker.container.requests")
    def test_wait_for_result_no_error(self, mock_requests, patched_socket):
        self.container.is_created.return_value = True

        real_container_mock = Mock()
        self.mock_docker_client.containers.get.return_value = real_container_mock

        output_itr = Mock()
        real_container_mock.attach.return_value = output_itr
        self.container._write_container_output = Mock()

        stdout_mock = Mock()
        stderr_mock = Mock()
        response = Mock()
        response.content = b'{"hello":"world"}'
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
            timeout=(self.container.RAPID_CONNECTION_TIMEOUT, None),
        )

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
                    timeout=(self.timeout, None),
                ),
                call(
                    "http://localhost:7077/2015-03-31/functions/function/invocations",
                    data=b"{}",
                    timeout=(self.timeout, None),
                ),
                call(
                    "http://localhost:7077/2015-03-31/functions/function/invocations",
                    data=b"{}",
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

    def test_write_container_output_successful(self):
        stdout_mock = Mock()
        stderr_mock = Mock()

        def _output_iterator():
            yield "Hello", None
            yield None, "World"
            raise ValueError("The pipe has been ended.")

        Container._write_container_output(_output_iterator(), stdout_mock, stderr_mock)
        stdout_mock.assert_has_calls([call.write("Hello")])
        stderr_mock.assert_has_calls([call.write("World")])


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
        self.container._write_container_output.assert_called_with(output_itr, stdout=stdout_mock, stderr=stderr_mock)

    def test_must_skip_if_no_stdout_and_stderr(self):

        self.container.wait_for_logs()
        self.mock_docker_client.containers.get.assert_not_called()

    def test_must_raise_if_container_is_not_created(self):

        self.container.is_created.return_value = False

        with self.assertRaises(RuntimeError):
            self.container.wait_for_logs(stdout=Mock())


class TestContainer_write_container_output(TestCase):
    def setUp(self):
        self.output_itr = [(b"stdout1", None), (None, b"stderr1"), (b"stdout2", b"stderr2"), (None, None)]

        self.stdout_mock = Mock()
        self.stderr_mock = Mock()

    def test_must_write_stdout_and_stderr_data(self):
        # All the invalid frames must be ignored

        Container._write_container_output(self.output_itr, stdout=self.stdout_mock, stderr=self.stderr_mock)

        self.stdout_mock.write.assert_has_calls([call(b"stdout1"), call(b"stdout2")])

        self.stderr_mock.write.assert_has_calls([call(b"stderr1"), call(b"stderr2")])

    def test_must_write_only_stderr(self):
        # All the invalid frames must be ignored

        Container._write_container_output(self.output_itr, stdout=None, stderr=self.stderr_mock)

        self.stdout_mock.write.assert_not_called()

        self.stderr_mock.write.assert_has_calls([call(b"stderr1"), call(b"stderr2")])

    def test_must_write_only_stdout(self):

        Container._write_container_output(self.output_itr, stdout=self.stdout_mock, stderr=None)

        self.stdout_mock.write.assert_has_calls([call(b"stdout1"), call(b"stdout2")])

        self.stderr_mock.write.assert_not_called()  # stderr must never be called


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
        container = Container(image, "cmd", "dir", "dir")

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
        real_container_mock = self.mock_client.containers.get.return_value = Mock()
        real_container_mock.get_archive.return_value = (tar_stream, "ignored")

        tempfile_ctxmgr = tempfile_mock.NamedTemporaryFile.return_value = Mock()
        fp_mock = Mock()
        tempfile_ctxmgr.__enter__ = Mock(return_value=fp_mock)
        tempfile_ctxmgr.__exit__ = Mock()

        self.container.copy(source, dest)

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
