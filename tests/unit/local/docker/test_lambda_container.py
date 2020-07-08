"""
Unit test for Lambda container management
"""

from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized, param

from pathlib import Path

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.local.docker.lambda_container import LambdaContainer, Runtime
from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported

RUNTIMES_WITH_ENTRYPOINT = [Runtime.dotnetcore21.value, Runtime.go1x.value]

RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT = [
    Runtime.nodejs10x.value,
    Runtime.nodejs12x.value,
    Runtime.python37.value,
    Runtime.python38.value,
    Runtime.python36.value,
    Runtime.python27.value,
]

RUNTIMES_WITH_DEBUG_ENV_VARS_ONLY = [Runtime.java11.value, Runtime.java8.value, Runtime.dotnetcore21.value]

RUNTIMES_WITH_ENTRYPOINT_OVERRIDES = RUNTIMES_WITH_ENTRYPOINT + RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT

ALL_RUNTIMES = [r.value for r in Runtime]


class TestLambdaContainer_init(TestCase):
    def setUp(self):
        self.runtime = "nodejs12.x"
        self.handler = "handler"
        self.code_dir = "codedir"
        self.env_var = {"var": "value"}
        self.memory_mb = 1024
        self.debug_options = DebugContext(debug_args="a=b c=d e=f", debug_ports=[1235])

    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_debug_settings")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    def test_must_configure_container_properly(
        self,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_debug_settings_mock,
        get_exposed_ports_mock,
        get_image_mock,
    ):

        image = "image"
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        debug_settings = ([1, 2, 3], {"a": "b"})
        expected_cmd = [self.handler]

        get_image_mock.return_value = image
        get_exposed_ports_mock.return_value = ports
        get_debug_settings_mock.return_value = debug_settings
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {**self.env_var, **debug_settings[1]}

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
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual("/var/task", container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(debug_settings[0], container._entrypoint)
        self.assertEqual(expected_env_vars, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(image_builder_mock, self.runtime, [], self.debug_options)
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_debug_settings_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

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
    def test_must_return_lambci_image_with_debug(self):
        debug_options = DebugContext(debug_ports=[1235], debugger_path="a", debug_args="a=b c=d e=f")

        expected = "lambci/lambda:foo"

        image_builder = Mock()
        image_builder.build.return_value = expected

        self.assertEqual(LambdaContainer._get_image(image_builder, "foo", [], debug_options), expected)

        image_builder.build.assert_called_with("foo", [], True)

    def test_must_return_lambci_image_without_debug(self):
        debug_options = DebugContext()

        expected = "lambci/lambda:foo"

        image_builder = Mock()
        image_builder.build.return_value = expected

        self.assertEqual(LambdaContainer._get_image(image_builder, "foo", [], debug_options), expected)

        image_builder.build.assert_called_with("foo", [], False)


class TestLambdaContainer_get_debug_settings(TestCase):
    def setUp(self):

        self.debug_ports = [1235]
        self.debug_args = "a=b c=d e=f"
        self.debug_options = DebugContext(debug_ports=[1235], debug_args="a=b c=d e=f")

    def test_must_skip_if_debug_port_is_not_specified(self):
        self.assertEqual(
            ("/var/rapid/init", {}),
            LambdaContainer._get_debug_settings("runtime", None),
            "Must not provide entrypoint if debug port is not given",
        )

    @parameterized.expand([param(r) for r in ALL_RUNTIMES])
    def test_must_provide_entrypoint_for_certain_runtimes_only(self, runtime):
        if runtime in RUNTIMES_WITH_ENTRYPOINT_OVERRIDES:
            result, _ = LambdaContainer._get_debug_settings(runtime, self.debug_options)
            self.assertIsNotNone(result, "{} runtime must provide entrypoint".format(runtime))

        elif runtime in RUNTIMES_WITH_DEBUG_ENV_VARS_ONLY:
            result, _ = LambdaContainer._get_debug_settings(runtime, self.debug_options)
            self.assertEquals("/var/rapid/init", result, "{} runtime must not override entrypoint".format(runtime))

        else:
            with self.assertRaises(DebuggingNotSupported):
                LambdaContainer._get_debug_settings(runtime, self.debug_options)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_DEBUG_ENV_VARS_ONLY])
    def test_must_provide_debug_env_vars(self, runtime):
        _, debug_env_vars = LambdaContainer._get_debug_settings(runtime, self.debug_options)

        self.assertIsNotNone(debug_env_vars)

    @parameterized.expand([param(r) for r in set(RUNTIMES_WITH_ENTRYPOINT) if not r.startswith("dotnetcore2")])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_entrypoint(self, runtime):
        """
        Debug args list is appended starting at second position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result, _ = LambdaContainer._get_debug_settings(runtime, self.debug_options)
        actual = result[1:4]

        self.assertEqual(actual, expected_debug_args)

    @parameterized.expand([param(r) for r in set(RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT)])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_bootstrap_based_entrypoint(self, runtime):
        """
        Debug args list is appended as arguments to bootstrap-args, which is past the fourth position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result, _ = LambdaContainer._get_debug_settings(runtime, self.debug_options)
        actual = result[4:5][0]

        self.assertTrue(all(debug_arg in actual for debug_arg in expected_debug_args))

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT])
    def test_must_provide_entrypoint_even_without_debug_args(self, runtime):
        debug_options = DebugContext(debug_ports=[1235], debug_args=None)
        result, _ = LambdaContainer._get_debug_settings(runtime, debug_options)

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


class TestLambdaContainer_get_additional_volumes(TestCase):
    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if r.startswith("go")])
    def test_no_additional_volumes_when_debug_options_is_none(self, runtime):
        expected = {}

        debug_options = DebugContext(debug_ports=None)

        result = LambdaContainer._get_additional_volumes(runtime, debug_options)
        self.assertEqual(result, expected)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if r.startswith("go")])
    def test_no_additional_volumes_when_debuggr_path_is_none(self, runtime):
        expected = {}
        debug_options = DebugContext(debug_ports=[1234])

        result = LambdaContainer._get_additional_volumes(runtime, debug_options)

        self.assertEqual(result, expected)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if r.startswith("go")])
    def test_additional_volumes_returns_volume_with_debugger_path_is_set(self, runtime):
        expected = {
            "/somepath": {"bind": "/tmp/lambci_debug_files", "mode": "ro"},
        }

        debug_options = DebugContext(debug_ports=[1234], debugger_path="/somepath")

        result = LambdaContainer._get_additional_volumes(runtime, debug_options)
        print(result)
        self.assertEqual(result, expected)
