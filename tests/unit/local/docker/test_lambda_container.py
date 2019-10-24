"""
Unit test for Lambda container management
"""

import os.path

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.local.docker.lambda_container import LambdaContainer, Runtime
from samcli.local.docker.lambda_debug_entrypoint import DebuggingNotSupported

RUNTIMES_WITH_ENTRYPOINT = [
    Runtime.java8.value,
    Runtime.dotnetcore20.value,
    Runtime.dotnetcore21.value,
    Runtime.go1x.value,
    Runtime.nodejs.value,
    Runtime.nodejs43.value,
    Runtime.nodejs610.value,
    Runtime.nodejs810.value,
    Runtime.python36.value,
    Runtime.python27.value,
]

RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT = [Runtime.nodejs10x.value, Runtime.python37.value]


ALL_RUNTIMES = [r for r in Runtime]


class TestLambdaContainer_init(TestCase):
    def setUp(self):
        self.runtime = "nodejs4.3"
        self.handler = "handler"
        self.code_dir = "codedir"
        self.env_var = {"var": "value"}
        self.memory_mb = 1024
        self.debug_options = DebugContext(debug_args="a=b c=d e=f", debug_ports=[1235])
        self.additional_volumes = {Path.home()}

    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_entry_point")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    @patch.object(LambdaContainer, "_get_debugger_volume")
    def test_must_configure_container_properly(
        self,
        get_debugger_volume_mock,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_entry_point_mock,
        get_exposed_ports_mock,
        get_image_mock,
    ):

        image = "image"
        ports = {"a": "b"}
        addtl_options = {}
        debugger_volume = {}
        addtl_volumes = {}
        entry = [1, 2, 3]
        expected_cmd = [self.handler]

        get_image_mock.return_value = image
        get_exposed_ports_mock.return_value = ports
        get_entry_point_mock.return_value = entry
        get_additional_options_mock.return_value = addtl_options
        get_debugger_volume_mock.return_value = debugger_volume
        get_additional_volumes_mock.return_value = addtl_volumes

        image_builder_mock = Mock()

        container = LambdaContainer(
            self.runtime,
            self.handler,
            self.code_dir,
            layers=[],
            image_builder=image_builder_mock,
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            additional_volumes=self.additional_volumes,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual("/var/task", container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(entry, container._entrypoint)
        self.assertEqual(self.env_var, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(image_builder_mock, self.runtime, [])
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_entry_point_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_debugger_volume_mock.assert_called_with(self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.additional_volumes)

    def test_must_fail_for_unsupported_runtime(self):

        runtime = "foo"

        image_builder_mock = Mock()

        with self.assertRaises(ValueError) as context:
            LambdaContainer(runtime, self.handler, self.code_dir, [], image_builder_mock)

        self.assertEqual(str(context.exception), "Unsupported Lambda runtime foo")


class TestLambdaContainer_get_exposed_ports(TestCase):
    def test_must_map_same_port_on_host_and_container(self):

        debug_options = DebugContext(debug_ports=[12345])
        expected = {port: port for port in debug_options.debug_ports}
        result = LambdaContainer._get_exposed_ports(debug_options)

        self.assertEqual(expected, result)

    def test_must_map_multiple_ports_on_host_and_container(self):

        debug_options = DebugContext(debug_ports=[12345, 67890])
        expected = {port: port for port in debug_options.debug_ports}
        result = LambdaContainer._get_exposed_ports(debug_options)

        self.assertEqual(expected, result)

    def test_empty_ports_list(self):

        debug_options = DebugContext(debug_ports=[])
        result = LambdaContainer._get_exposed_ports(debug_options)

        self.assertEqual(None, result)

    def test_none_ports_specified(self):

        debug_options = DebugContext(debug_ports=None)
        result = LambdaContainer._get_exposed_ports(debug_options)

        self.assertEqual(None, result)

    def test_must_skip_if_port_is_not_given(self):

        self.assertIsNone(LambdaContainer._get_exposed_ports(None), "No ports should be exposed")


class TestLambdaContainer_get_image(TestCase):
    def test_must_return_lambci_image(self):

        expected = "lambci/lambda:foo"

        image_builder = Mock()
        image_builder.build.return_value = expected

        self.assertEqual(LambdaContainer._get_image(image_builder, "foo", []), expected)


class TestLambdaContainer_get_entry_point(TestCase):
    def setUp(self):

        self.debug_ports = [1235]
        self.debug_args = "a=b c=d e=f"
        self.debug_options = DebugContext(debug_ports=[1235], debug_args="a=b c=d e=f")

    def test_must_skip_if_debug_port_is_not_specified(self):
        self.assertIsNone(
            LambdaContainer._get_entry_point("runtime", None), "Must not provide entrypoint if debug port is not given"
        )

    @parameterized.expand([param(r) for r in ALL_RUNTIMES])
    def test_must_provide_entrypoint_for_certain_runtimes_only(self, runtime):

        if runtime in RUNTIMES_WITH_ENTRYPOINT:
            result = LambdaContainer._get_entry_point(runtime, self.debug_options)
            self.assertIsNotNone(result, "{} runtime must provide entrypoint".format(runtime))
        else:
            with self.assertRaises(DebuggingNotSupported):
                LambdaContainer._get_entry_point(runtime, self.debug_options)

    @parameterized.expand([param(r) for r in set(RUNTIMES_WITH_ENTRYPOINT)])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_entrypoint(self, runtime):
        """
        Debug args list is appended starting at second position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result = LambdaContainer._get_entry_point(runtime, self.debug_options)
        actual = result[1:4]

        self.assertEqual(actual, expected_debug_args)

    @parameterized.expand([param(r) for r in set(RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT)])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_bootstrap_based_entrypoint(self, runtime):
        """
        Debug args list is appended as arguments to bootstrap-args, which is past the fourth position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result = LambdaContainer._get_entry_point(runtime, self.debug_options)
        actual = result[4:5][0]

        self.assertTrue(all(debug_arg in actual for debug_arg in expected_debug_args))

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT])
    def test_must_provide_entrypoint_even_without_debug_args(self, runtime):
        debug_options = DebugContext(debug_ports=[1235], debug_args=None)
        result = LambdaContainer._get_entry_point(runtime, debug_options)

        self.assertIsNotNone(result)


class TestLambdaContainer_get_additional_options(TestCase):
    def test_no_additional_options_when_debug_options_is_none(self):
        debug_options = DebugContext(debug_ports=None)

        result = LambdaContainer._get_additional_options("runtime", debug_options)
        self.assertIsNone(result)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if not r.startswith("go")])
    def test_default_value_returned_for_non_go_runtimes(self, runtime):
        debug_options = DebugContext(debug_ports=[1235])

        result = LambdaContainer._get_additional_options(runtime, debug_options)
        self.assertEqual(result, {})

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if r.startswith("go")])
    def test_go_runtime_returns_additional_options(self, runtime):
        expected = {"security_opt": ["seccomp:unconfined"], "cap_add": ["SYS_PTRACE"]}

        debug_options = DebugContext(debug_ports=[1235])

        result = LambdaContainer._get_additional_options(runtime, debug_options)
        self.assertEqual(result, expected)


class TestLambdaContainer_get_debugger_volume(TestCase):
    def test_no_debugger_volume_when_debug_options_is_none(self):
        debug_options = DebugContext(debug_ports=None)

        result = LambdaContainer._get_debugger_volume(debug_options)
        self.assertIsNone(result)

    def test_no_debugger_volume_when_debugger_path_is_none(self):
        debug_options = DebugContext(debug_ports=[1234])

        result = LambdaContainer._get_debugger_volume(debug_options)
        self.assertIsNone(result)

    def test_debugger_volume_returns_volume_with_debugger_path_is_set(self):
        expected = {"/somepath": {"bind": "/tmp/lambci_debug_files", "mode": "ro"}}

        debug_options = DebugContext(debug_ports=[1234], debugger_path="/somepath")

        result = LambdaContainer._get_debugger_volume(debug_options)
        self.assertEqual(result, expected)


class TestLambdaContainer_get_additional_volumes(TestCase):
    def test_no_additional_volumes_when_debug_options_is_none(self):
        host_volumes = None
        actual_volumes = LambdaContainer._get_additional_volumes(host_volumes=host_volumes)
        self.assertIsNone(actual_volumes)

    def test_no_additional_volumes_when_debug_options_is_empty(self):
        host_volumes = []
        actual_volumes = LambdaContainer._get_additional_volumes(host_volumes=host_volumes)
        self.assertIsNone(actual_volumes)

    def test_additional_volumes_single_volume(self):
        host_path = Path.home()
        host_volumes = [host_path]

        actual_volumes = LambdaContainer._get_additional_volumes(host_volumes=host_volumes)
        self.assertIsNotNone(actual_volumes)

        expected_remote_path = str(os.path.join(LambdaContainer._VOLUME_MOUNT_PATH, host_path.parts[-1]))
        expected_volume = {host_path: {"bind": expected_remote_path, "mode": ""}}
        self.assertEqual(expected_volume, actual_volumes)

    def test_additional_volumes_multiple_volumes(self):
        host_home_path = Path.home()
        host_cwd_path = Path.cwd()
        host_volumes = [host_home_path, host_cwd_path]

        actual_volumes = LambdaContainer._get_additional_volumes(host_volumes=host_volumes)
        self.assertIsNotNone(actual_volumes)

        expected_home_remote_path = str(os.path.join(LambdaContainer._VOLUME_MOUNT_PATH, host_home_path.parts[-1]))
        expected_cwd_remote_path = str(os.path.join(LambdaContainer._VOLUME_MOUNT_PATH, host_cwd_path.parts[-1]))
        expected_volumes = {
            host_home_path: {"bind": expected_home_remote_path, "mode": ""},
            host_cwd_path: {"bind": expected_cwd_remote_path, "mode": ""},
        }
        self.assertEqual(expected_volumes, actual_volumes)
