"""
Unit test for Lambda container management
"""

from unittest import TestCase
from mock import patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.local.docker.lambda_container import LambdaContainer, Runtime, DebuggingNotSupported

RUNTIMES_WITH_ENTRYPOINT = [Runtime.java8.value,
                            Runtime.dotnetcore20.value,
                            Runtime.dotnetcore21.value,
                            Runtime.go1x.value,
                            Runtime.nodejs.value,
                            Runtime.nodejs43.value,
                            Runtime.nodejs610.value,
                            Runtime.nodejs810.value,
                            Runtime.python36.value,
                            Runtime.python27.value]

ALL_RUNTIMES = [r for r in Runtime]


class TestLambdaContainer_init(TestCase):

    def setUp(self):
        self.runtime = "nodejs4.3"
        self.handler = "handler"
        self.code_dir = "codedir"
        self.env_var = {"var": "value"}
        self.memory_mb = 1024
        self.debug_options = DebugContext(debug_args="a=b c=d e=f", debug_port=1235)

    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_entry_point")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    def test_must_configure_container_properly(self,
                                               get_additional_volumes_mock,
                                               get_additional_options_mock,
                                               get_entry_point_mock,
                                               get_exposed_ports_mock,
                                               get_image_mock):

        image = "image"
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        entry = [1, 2, 3]
        expected_cmd = [self.handler]

        get_image_mock.return_value = image
        get_exposed_ports_mock.return_value = ports
        get_entry_point_mock.return_value = entry
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes

        image_builder_mock = Mock()

        container = LambdaContainer(self.runtime,
                                    self.handler,
                                    self.code_dir,
                                    layers=[],
                                    image_builder=image_builder_mock,
                                    env_vars=self.env_var,
                                    memory_mb=self.memory_mb,
                                    debug_options=self.debug_options)

        self.assertEquals(image, container._image)
        self.assertEquals(expected_cmd, container._cmd)
        self.assertEquals("/var/task", container._working_dir)
        self.assertEquals(self.code_dir, container._host_dir)
        self.assertEquals(ports, container._exposed_ports)
        self.assertEquals(entry, container._entrypoint)
        self.assertEquals(self.env_var, container._env_vars)
        self.assertEquals(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(image_builder_mock, self.runtime, [])
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_entry_point_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.debug_options)

    def test_must_fail_for_unsupported_runtime(self):

        runtime = "foo"

        image_builder_mock = Mock()

        with self.assertRaises(ValueError) as context:
            LambdaContainer(runtime, self.handler, self.code_dir, [], image_builder_mock)

        self.assertEquals(str(context.exception), "Unsupported Lambda runtime foo")


class TestLambdaContainer_get_exposed_ports(TestCase):

    def test_must_map_same_port_on_host_and_container(self):

        debug_options = DebugContext(debug_port=12345)
        expected = {debug_options.debug_port: debug_options.debug_port}
        result = LambdaContainer._get_exposed_ports(debug_options)

        self.assertEquals(expected, result)

    def test_must_skip_if_port_is_not_given(self):

        self.assertIsNone(LambdaContainer._get_exposed_ports(None), "No ports should be exposed")


class TestLambdaContainer_get_image(TestCase):

    def test_must_return_lambci_image(self):

        expected = "lambci/lambda:foo"

        image_builder = Mock()
        image_builder.build.return_value = expected

        self.assertEquals(LambdaContainer._get_image(image_builder, 'foo', []), expected)


class TestLambdaContainer_get_entry_point(TestCase):

    def setUp(self):

        self.debug_port = 1235
        self.debug_args = "a=b c=d e=f"
        self.debug_options = DebugContext(debug_port=1235, debug_args="a=b c=d e=f")

    def test_must_skip_if_debug_port_is_not_specified(self):
        self.assertIsNone(LambdaContainer._get_entry_point("runtime", None),
                          "Must not provide entrypoint if debug port is not given")

    @parameterized.expand([param(r) for r in ALL_RUNTIMES])
    def test_must_provide_entrypoint_for_certain_runtimes_only(self, runtime):

        if runtime in RUNTIMES_WITH_ENTRYPOINT:
            result = LambdaContainer._get_entry_point(runtime, self.debug_options)
            self.assertIsNotNone(result, "{} runtime must provide entrypoint".format(runtime))
        else:
            with self.assertRaises(DebuggingNotSupported):
                LambdaContainer._get_entry_point(runtime, self.debug_options)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_entrypoint(self, runtime):
        """
        Debug args list is appended starting at second position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result = LambdaContainer._get_entry_point(runtime, self.debug_options)
        actual = result[1:4]

        self.assertEquals(actual, expected_debug_args)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT])
    def test_must_provide_entrypoint_even_without_debug_args(self, runtime):
        debug_options = DebugContext(debug_port=1235, debug_args=None)
        result = LambdaContainer._get_entry_point(runtime, debug_options)

        self.assertIsNotNone(result)


class TestLambdaContainer_get_additional_options(TestCase):

    def test_no_additional_options_when_debug_options_is_none(self):
        debug_options = DebugContext(debug_port=None)

        result = LambdaContainer._get_additional_options('runtime', debug_options)
        self.assertIsNone(result)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if not r.startswith('go')])
    def test_default_value_returned_for_non_go_runtimes(self, runtime):
        debug_options = DebugContext(debug_port=1235)

        result = LambdaContainer._get_additional_options(runtime, debug_options)
        self.assertEquals(result, {})

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT if r.startswith('go')])
    def test_go_runtime_returns_additional_options(self, runtime):
        expected = {"security_opt": ["seccomp:unconfined"], "cap_add": ["SYS_PTRACE"]}

        debug_options = DebugContext(debug_port=1235)

        result = LambdaContainer._get_additional_options(runtime, debug_options)
        self.assertEquals(result, expected)


class TestLambdaContainer_get_additional_volumes(TestCase):

    def test_no_additional_volumes_when_debug_options_is_none(self):
        debug_options = DebugContext(debug_port=None)

        result = LambdaContainer._get_additional_volumes(debug_options)
        self.assertIsNone(result)

    def test_no_additional_volumes_when_debuggr_path_is_none(self):
        debug_options = DebugContext(debug_port=1234)

        result = LambdaContainer._get_additional_volumes(debug_options)
        self.assertIsNone(result)

    def test_additional_volumes_returns_volume_with_debugger_path_is_set(self):
        expected = {'/somepath': {"bind": "/tmp/lambci_debug_files", "mode": "ro"}}

        debug_options = DebugContext(debug_port=1234, debugger_path='/somepath')

        result = LambdaContainer._get_additional_volumes(debug_options)
        self.assertEquals(result, expected)
