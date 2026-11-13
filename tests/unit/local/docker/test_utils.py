"""
Unit test for Utils
"""

import errno
import os
import socket as real_socket
import samcli.local.docker.utils
from parameterized import parameterized
from unittest import TestCase
from unittest.mock import call, patch, Mock
import docker

from samcli.lib.utils.architecture import InvalidArchitecture
from samcli.local.docker.utils import (
    WSAEADDRNOTAVAIL,
    WSAEAFNOSUPPORT,
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


def resolved_address(address, family=real_socket.AF_INET):
    """
    One socket.getaddrinfo entry for a numeric address, in the shape find_free_port unpacks.

    The IPv6 sockaddr carries flowinfo and scope id, which is how fe80::1%eth0 reaches bind().
    """
    sockaddr = (address, 0) if family == real_socket.AF_INET else (address, 0, 0, 7)
    return [(family, real_socket.SOCK_STREAM, real_socket.IPPROTO_TCP, "", sockaddr)]


def probe_socket(mock_socket):
    """
    Wires a patched socket module the way a real socket behaves: __enter__ returns the socket
    itself, so a bind side effect set here applies inside find_free_port's `with` block and
    every bind call is recorded on one object. Idempotent, so assertions may call it too.
    """
    sock = mock_socket.socket.return_value
    sock.__enter__.return_value = sock
    return sock


class TestFreePorts(TestCase):
    def setUp(self):
        # The warn-once set is module state that outlives a single test.
        samcli.local.docker.utils._UNPROBEABLE_INTERFACES.clear()

    tearDown = setUp

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_first_attempt(self, network_interface, mock_random, mock_socket):
        mock_socket.getaddrinfo.return_value = resolved_address(network_interface)
        mock_random.randrange = Mock(side_effect=[3093] * 1000)
        port = find_free_port(network_interface, start=3000, end=4000)
        self.assertEqual(port, 3093)

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_second_attempt(self, network_interface, mock_random, mock_socket):
        mock_socket.getaddrinfo.return_value = resolved_address(network_interface)
        probe_socket(mock_socket).bind.side_effect = [OSError, None]
        mock_random.randrange = Mock(side_effect=[3093, 3094] * 1000)
        port = find_free_port(network_interface, start=3000, end=4000)
        self.assertEqual(port, 3094)

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_no_free_ports(self, network_interface, mock_random, mock_socket):
        mock_socket.getaddrinfo.return_value = resolved_address(network_interface)
        probe_socket(mock_socket).bind.side_effect = OSError
        mock_random.randrange = Mock(side_effect=[3093] * 1000)
        with self.assertRaises(NoFreePortsError):
            find_free_port(network_interface, start=3000, end=4000)

    @parameterized.expand(
        [
            # POSIX "Cannot assign requested address".
            (errno.EADDRNOTAVAIL,),
            # Winsock WSAEADDRNOTAVAIL: CPython passes Winsock codes through unchanged, so
            # this is what errno carries on Windows. Exercised on every platform.
            (WSAEADDRNOTAVAIL,),
        ]
    )
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_returns_unprobed_port_when_interface_is_not_local(
        self, address_not_available_errno, mock_random, mock_socket
    ):
        # The interface belongs to the machine running the container engine, so binding it here
        # fails for every candidate. Report that and hand back a port rather than declaring
        # the whole range busy; the daemon's bind is the real check.
        mock_socket.getaddrinfo.return_value = resolved_address("172.17.0.1")
        probe_socket(mock_socket).bind.side_effect = OSError(
            address_not_available_errno, "Cannot assign requested address"
        )
        mock_random.randrange = Mock(side_effect=[3093, 3094] * 1000)

        with self.assertLogs("samcli.local.docker.utils", level="WARNING") as log_ctx:
            port = find_free_port("172.17.0.1", start=3000, end=4000)

        self.assertEqual(port, 3093)
        # Exactly one bind was attempted, and never against all interfaces.
        self.assertEqual(probe_socket(mock_socket).bind.call_args_list, [call(("172.17.0.1", 3093))])
        self.assertTrue(any("172.17.0.1" in message and "without checking it" in message for message in log_ctx.output))
        # The message must not tell the user to change the interface: for a remote daemon
        # the other startup warning asks for an address that cannot be bound here, and the
        # two instructions together would be a loop.
        self.assertFalse(any("--container-host-interface" in message for message in log_ctx.output))
        # Nor may it promise a named port-allocation error. Mapping the daemon's refusal to
        # PortAlreadyInUse lives in Container.start, which this change does not touch, so on
        # a merge-base checkout that promise would be false.
        self.assertFalse(any("port allocation error" in message for message in log_ctx.output))

    @parameterized.expand(
        [
            # POSIX "Address family not supported by protocol".
            (errno.EAFNOSUPPORT,),
            # Winsock WSAEAFNOSUPPORT. On Windows errno.EAFNOSUPPORT is 102 and a socket
            # error never carries it, so without this value an IPv6 interface on a host
            # with IPv6 off scanned the whole range and raised NoFreePortsError. Exercised
            # on every platform.
            (WSAEAFNOSUPPORT,),
        ]
    )
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_returns_unprobed_port_when_address_family_is_unavailable(
        self, address_family_unsupported_errno, mock_random, mock_socket
    ):
        # A host booted with IPv6 off raises EAFNOSUPPORT when the AF_INET6 socket is
        # CREATED, so the error comes from socket.socket() and never reaches bind. The
        # answer is the same for every candidate port, so this reports and hands back a
        # port rather than scanning the range to the same misleading NoFreePortsError.
        mock_socket.getaddrinfo.return_value = resolved_address("::1", family=real_socket.AF_INET6)
        mock_socket.socket.side_effect = OSError(
            address_family_unsupported_errno, "Address family not supported by protocol"
        )
        mock_random.randrange = Mock(side_effect=[3093, 3094] * 1000)

        with self.assertLogs("samcli.local.docker.utils", level="WARNING") as log_ctx:
            port = find_free_port("::1", start=3000, end=4000)

        self.assertEqual(port, 3093)
        # Exactly one attempt: creating the socket fails identically for every candidate.
        self.assertEqual(mock_socket.socket.call_count, 1)
        self.assertTrue(any("::1" in message and "without checking it" in message for message in log_ctx.output))
        # The warning is shared with the address-not-available path, so it must not name a
        # cause that is wrong here: IPv6 being off locally is not the engine running
        # elsewhere, and the address does exist on this machine.
        self.assertFalse(any("does not exist on this machine" in message for message in log_ctx.output))
        self.assertFalse(any("runs elsewhere" in message for message in log_ctx.output))

    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_probes_ipv6_interface_on_an_ipv6_socket(self, mock_random, mock_socket):
        # An IPv6 value cannot be probed on the AF_INET socket socket.socket() returns: the
        # bind fails during address resolution with a negative gaierror errno, which is not
        # an address-not-available errno, so every candidate "failed" and the range was
        # reported busy. Resolving the address first picks the family, and carries the
        # flowinfo and scope id that a link-local address needs.
        sock = probe_socket(mock_socket)
        mock_socket.getaddrinfo.return_value = resolved_address("fe80::1", family=real_socket.AF_INET6)
        mock_random.randrange = Mock(side_effect=[3093] * 1000)

        port = find_free_port("fe80::1%eth0", start=3000, end=4000)

        self.assertEqual(port, 3093)
        mock_socket.socket.assert_called_once_with(
            real_socket.AF_INET6, real_socket.SOCK_STREAM, real_socket.IPPROTO_TCP
        )
        self.assertEqual(sock.bind.call_args_list, [call(("fe80::1", 3093, 0, 7))])

    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_returns_unprobed_port_when_address_does_not_resolve(self, mock_random, mock_socket):
        # A value that does not resolve here cannot be probed here either, and the answer does
        # not change per candidate: scanning the range would spend 1000 lookups to arrive at
        # the same misleading NoFreePortsError.
        mock_socket.getaddrinfo.side_effect = real_socket.gaierror(-2, "Name or service not known")
        mock_random.randrange = Mock(side_effect=[3093] * 1000)

        with self.assertLogs("samcli.local.docker.utils", level="WARNING") as log_ctx:
            port = find_free_port("daemon-host.internal", start=3000, end=4000)

        self.assertEqual(port, 3093)
        mock_socket.socket.assert_not_called()
        self.assertTrue(
            any("daemon-host.internal" in message and "without checking it" in message for message in log_ctx.output)
        )

    @patch("samcli.local.docker.utils.random")
    def test_free_port_returns_unprobed_port_for_unencodable_interface(self, mock_random):
        # getaddrinfo idna-encodes the name first, which raises UnicodeError - a ValueError,
        # NOT an OSError - for a label over 63 characters. A mistyped flag value must not
        # escape as a traceback from a function whose whole job is to pick a port. The real
        # socket module is used deliberately: a mock cannot show which exception type is
        # raised, and that type is the entire point of this test.
        mock_random.randrange = Mock(side_effect=[3093] * 1000)

        with self.assertLogs("samcli.local.docker.utils", level="WARNING") as log_ctx:
            port = find_free_port("a" * 64, start=3000, end=4000)

        self.assertEqual(port, 3093)
        self.assertTrue(any("without checking it" in message for message in log_ctx.output))

    def test_free_port_probes_an_empty_interface_for_real(self):
        # An empty interface means "all interfaces", which bind("") probed for real before
        # this function resolved anything. It must stay probed rather than short-circuiting
        # to the unprobeable path. The real socket module is used on purpose, so no candidate
        # port is pinned: pinning one makes the test fail on any machine already holding it.
        with patch("samcli.local.docker.utils.LOG") as log_mock:
            port = find_free_port("", start=3000, end=4000)

        self.assertIn(port, range(3000, 4000))
        log_mock.warning.assert_not_called()

    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_probes_an_empty_interface_on_ipv4(self, mock_random, mock_socket):
        # The family matters and is not observable from the returned port. getaddrinfo's
        # wildcard order is platform-dependent - IPv4 first on Linux, IPv6 first on macOS -
        # so deriving the family from it probed IPv6 on macOS, where the stacks are separate
        # and an IPv6 wildcard bind succeeds while the IPv4 wildcard is taken. That reported
        # a port free which the engine could not then publish. Asserted through a mock so it
        # holds on every platform, not only the one running the suite.
        mock_socket.AF_INET = real_socket.AF_INET
        mock_socket.SOCK_STREAM = real_socket.SOCK_STREAM
        sock = probe_socket(mock_socket)
        mock_random.randrange = Mock(side_effect=[3093] * 1000)

        port = find_free_port("", start=3000, end=4000)

        self.assertEqual(port, 3093)
        mock_socket.socket.assert_called_once_with(real_socket.AF_INET, real_socket.SOCK_STREAM, 0)
        self.assertEqual(sock.bind.call_args_list, [call(("", 3093))])
        # Nothing is resolved for the wildcard, so platform ordering cannot leak back in.
        mock_socket.getaddrinfo.assert_not_called()

    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_warns_once_per_interface(self, mock_random, mock_socket):
        # find_free_port runs once per container creation, i.e. once per invoke in
        # cold-container mode, and the condition cannot change while the process lives.
        mock_socket.getaddrinfo.side_effect = lambda host, *_args, **_kwargs: resolved_address(host)
        probe_socket(mock_socket).bind.side_effect = OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address")
        # A callable rather than a list: each call builds a candidate list of end-start
        # entries, so four calls would exhaust a fixed side_effect sequence.
        mock_random.randrange = Mock(side_effect=lambda _start, _end: 3093)

        with self.assertLogs("samcli.local.docker.utils", level="WARNING") as log_ctx:
            find_free_port("172.17.0.1", start=3000, end=4000)
            find_free_port("172.17.0.1", start=3000, end=4000)
            find_free_port("172.17.0.1", start=3000, end=4000)
            # A different interface is a different report.
            find_free_port("172.18.0.1", start=3000, end=4000)

        warnings = [message for message in log_ctx.output if message.startswith("WARNING")]
        self.assertEqual(len(warnings), 2)
        self.assertIn("172.17.0.1", warnings[0])
        self.assertIn("172.18.0.1", warnings[1])

    @parameterized.expand([("0.0.0.0",), ("127.0.0.1",)])
    @patch("samcli.local.docker.utils.socket")
    @patch("samcli.local.docker.utils.random")
    def test_free_port_still_scans_on_other_errors(self, network_interface, mock_random, mock_socket):
        # An in-use port is EADDRINUSE, not EADDRNOTAVAIL: keep scanning the range.
        mock_socket.getaddrinfo.return_value = resolved_address(network_interface)
        probe_socket(mock_socket).bind.side_effect = [OSError(errno.EADDRINUSE, "Address already in use"), None]
        mock_random.randrange = Mock(side_effect=[3093, 3094] * 1000)

        port = find_free_port(network_interface, start=3000, end=4000)

        self.assertEqual(port, 3094)


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
