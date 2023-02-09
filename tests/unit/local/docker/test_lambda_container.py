"""
Unit test for Lambda container management
"""

from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized, param

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.local.docker.lambda_container import LambdaContainer, Runtime
from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX

RUNTIMES_WITH_ENTRYPOINT = [Runtime.dotnetcore31.value, Runtime.dotnet6.value, Runtime.go1x.value]

RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT = [
    Runtime.nodejs12x.value,
    Runtime.nodejs14x.value,
    Runtime.nodejs16x.value,
    Runtime.nodejs18x.value,
    Runtime.python37.value,
    Runtime.python38.value,
    Runtime.python39.value,
    Runtime.dotnet6.value,
]

RUNTIMES_WITH_DEBUG_ENV_VARS_ONLY = [
    Runtime.java11.value,
    Runtime.java8.value,
    Runtime.java8al2.value,
    Runtime.dotnetcore31.value,
    Runtime.dotnet6.value,
    Runtime.go1x.value,
]

RUNTIMES_WITH_ENTRYPOINT_OVERRIDES = RUNTIMES_WITH_ENTRYPOINT + RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT

ALL_RUNTIMES = [r.value for r in Runtime]


class TestLambdaContainer_init(TestCase):
    def setUp(self):
        self.runtime = "nodejs12.x"
        self.handler = "handler"
        self.code_dir = "codedir"
        self.image_config = None
        self.imageuri = None
        self.packagetype = ZIP
        self.env_var = {"var": "value"}
        self.memory_mb = 1024
        self.debug_options = DebugContext(
            debug_args="a=b c=d e=f", debug_ports=[1235], container_env_vars={"debug_var": "debug_value"}
        )
        self.function_name = "function_name"

    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_debug_settings")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    def test_must_configure_container_properly_zip(
        self,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_debug_settings_mock,
        get_exposed_ports_mock,
        get_image_mock,
    ):

        image = IMAGE
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        debug_settings = ([1, 2, 3], {"a": "b"})
        expected_cmd = []

        get_image_mock.return_value = image
        get_exposed_ports_mock.return_value = ports
        get_debug_settings_mock.return_value = debug_settings
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {**self.env_var, **debug_settings[1]}

        image_builder_mock = Mock()

        container = LambdaContainer(
            image_config=self.image_config,
            imageuri=self.imageuri,
            packagetype=self.packagetype,
            runtime=self.runtime,
            handler=self.handler,
            code_dir=self.code_dir,
            layers=[],
            lambda_image=image_builder_mock,
            architecture="arm64",
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            function_full_path=self.function_name,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual("/var/task", container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(debug_settings[0], container._entrypoint)
        self.assertEqual(expected_env_vars, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(
            image_builder_mock, self.runtime, self.packagetype, self.imageuri, [], "arm64", self.function_name
        )
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_debug_settings_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

    @patch.object(LambdaContainer, "_get_config")
    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    @patch.object(LambdaContainer, "_get_debug_settings")
    def test_must_configure_container_properly_image_no_debug(
        self,
        get_debug_settings_mock,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_exposed_ports_mock,
        get_image_mock,
        get_config_mock,
    ):
        self.packagetype = IMAGE
        self.imageuri = "mylambda_image:v1"
        self.runtime = None

        image = IMAGE
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        expected_cmd = ["mycommand"]

        get_image_mock.return_value = image
        get_debug_settings_mock.return_value = (LambdaContainer._DEFAULT_ENTRYPOINT, {})
        get_config_mock.return_value = {
            "Cmd": ["mycommand"],
            "Entrypoint": ["my-additional-entrypoint"],
            "WorkingDir": "/var/mytask",
        }
        get_exposed_ports_mock.return_value = ports
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {**self.env_var}

        image_builder_mock = Mock()

        container = LambdaContainer(
            image_config=self.image_config,
            imageuri=self.imageuri,
            packagetype=self.packagetype,
            runtime=self.runtime,
            handler=self.handler,
            code_dir=self.code_dir,
            layers=[],
            lambda_image=image_builder_mock,
            architecture="arm64",
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            function_full_path=self.function_name,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual(get_config_mock()["WorkingDir"], container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(LambdaContainer._DEFAULT_ENTRYPOINT + get_config_mock()["Entrypoint"], container._entrypoint)
        self.assertEqual({**expected_env_vars, **{"AWS_LAMBDA_FUNCTION_HANDLER": "mycommand"}}, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(
            image_builder_mock, self.runtime, self.packagetype, self.imageuri, [], "arm64", self.function_name
        )
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

    @patch.object(LambdaContainer, "_get_config")
    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    def test_must_configure_container_properly_image_debug(
        self,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_exposed_ports_mock,
        get_image_mock,
        get_config_mock,
    ):
        self.packagetype = IMAGE
        self.imageuri = "mylambda_image:v1"
        self.runtime = None
        self.architecture = "x86_64"

        image = IMAGE
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        expected_cmd = ["mycommand"]

        get_image_mock.return_value = image
        get_config_mock.return_value = {
            "Cmd": ["mycommand"],
            "Entrypoint": ["my-additional-entrypoint"],
            "WorkingDir": "/var/mytask",
        }
        get_exposed_ports_mock.return_value = ports
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {
            **self.env_var,
            **self.debug_options.container_env_vars,
            **{"AWS_LAMBDA_FUNCTION_HANDLER": "mycommand"},
        }

        image_builder_mock = Mock()

        container = LambdaContainer(
            image_config=self.image_config,
            imageuri=self.imageuri,
            packagetype=self.packagetype,
            runtime=self.runtime,
            handler=self.handler,
            code_dir=self.code_dir,
            layers=[],
            lambda_image=image_builder_mock,
            architecture=self.architecture,
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            function_full_path=self.function_name,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual(get_config_mock()["WorkingDir"], container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        # Dis-regard Entrypoint when debug args are present.
        self.assertEqual(
            LambdaContainer._DEFAULT_ENTRYPOINT + self.debug_options.debug_args.split(" "), container._entrypoint
        )
        self.assertEqual(expected_env_vars, container._env_vars)
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(
            image_builder_mock, self.runtime, IMAGE, self.imageuri, [], "x86_64", self.function_name
        )
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

    @patch.object(LambdaContainer, "_get_config")
    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    def test_must_configure_container_properly_image_with_imageconfig_debug(
        self,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_exposed_ports_mock,
        get_image_mock,
        get_config_mock,
    ):
        self.packagetype = IMAGE
        self.imageuri = "mylambda_image:v1"
        self.runtime = None
        self.image_config = {
            "Command": ["my-imageconfig-command"],
            "EntryPoint": ["my-imageconfig-entrypoint"],
            "WorkingDirectory": "/var/myimageconfigtask",
        }

        image = IMAGE
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        expected_cmd = ["my-imageconfig-command"]

        get_image_mock.return_value = image
        get_config_mock.return_value = {
            "Cmd": ["mycommand"],
            "Entrypoint": ["my-additional-entrypoint"],
            "WorkingDir": "/var/mytask",
        }
        get_exposed_ports_mock.return_value = ports
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {**self.env_var, **self.debug_options.container_env_vars}

        image_builder_mock = Mock()

        container = LambdaContainer(
            image_config=self.image_config,
            imageuri=self.imageuri,
            packagetype=self.packagetype,
            runtime=self.runtime,
            handler=self.handler,
            code_dir=self.code_dir,
            layers=[],
            lambda_image=image_builder_mock,
            architecture="x86_64",
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            function_full_path=self.function_name,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual(self.image_config["WorkingDirectory"], container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(
            LambdaContainer._DEFAULT_ENTRYPOINT + self.debug_options.debug_args.split(" "), container._entrypoint
        )
        self.assertEqual(
            {**expected_env_vars, **{"AWS_LAMBDA_FUNCTION_HANDLER": "my-imageconfig-command"}}, container._env_vars
        )
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(
            image_builder_mock, self.runtime, IMAGE, self.imageuri, [], "x86_64", self.function_name
        )
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

    @patch.object(LambdaContainer, "_get_config")
    @patch.object(LambdaContainer, "_get_image")
    @patch.object(LambdaContainer, "_get_exposed_ports")
    @patch.object(LambdaContainer, "_get_additional_options")
    @patch.object(LambdaContainer, "_get_additional_volumes")
    @patch.object(LambdaContainer, "_get_debug_settings")
    def test_must_configure_container_properly_image_with_imageconfig_no_debug(
        self,
        get_debug_settings_mock,
        get_additional_volumes_mock,
        get_additional_options_mock,
        get_exposed_ports_mock,
        get_image_mock,
        get_config_mock,
    ):
        self.packagetype = IMAGE
        self.imageuri = "mylambda_image:v1"
        self.runtime = None
        self.image_config = {
            "Command": ["my-imageconfig-command"],
            "EntryPoint": ["my-imageconfig-entrypoint"],
            "WorkingDirectory": "/var/myimageconfigtask",
        }

        image = IMAGE
        ports = {"a": "b"}
        addtl_options = {}
        addtl_volumes = {}
        expected_cmd = ["my-imageconfig-command"]

        get_image_mock.return_value = image
        get_config_mock.return_value = {
            "Cmd": ["mycommand"],
            "Entrypoint": ["my-additional-entrypoint"],
            "WorkingDir": "/var/mytask",
        }
        get_exposed_ports_mock.return_value = ports
        get_debug_settings_mock.return_value = (LambdaContainer._DEFAULT_ENTRYPOINT, {})
        get_additional_options_mock.return_value = addtl_options
        get_additional_volumes_mock.return_value = addtl_volumes
        expected_env_vars = {**self.env_var}

        image_builder_mock = Mock()

        container = LambdaContainer(
            image_config=self.image_config,
            imageuri=self.imageuri,
            packagetype=self.packagetype,
            runtime=self.runtime,
            handler=self.handler,
            code_dir=self.code_dir,
            layers=[],
            lambda_image=image_builder_mock,
            architecture="x86_64",
            env_vars=self.env_var,
            memory_mb=self.memory_mb,
            debug_options=self.debug_options,
            function_full_path=self.function_name,
        )

        self.assertEqual(image, container._image)
        self.assertEqual(expected_cmd, container._cmd)
        self.assertEqual(self.image_config["WorkingDirectory"], container._working_dir)
        self.assertEqual(self.code_dir, container._host_dir)
        self.assertEqual(ports, container._exposed_ports)
        self.assertEqual(
            LambdaContainer._DEFAULT_ENTRYPOINT + self.image_config["EntryPoint"], container._entrypoint, "x86_64"
        )
        self.assertEqual(
            {**expected_env_vars, **{"AWS_LAMBDA_FUNCTION_HANDLER": "my-imageconfig-command"}}, container._env_vars
        )
        self.assertEqual(self.memory_mb, container._memory_limit_mb)

        get_image_mock.assert_called_with(
            image_builder_mock, self.runtime, self.packagetype, self.imageuri, [], "x86_64", self.function_name
        )
        get_exposed_ports_mock.assert_called_with(self.debug_options)
        get_additional_options_mock.assert_called_with(self.runtime, self.debug_options)
        get_additional_volumes_mock.assert_called_with(self.runtime, self.debug_options)

    def test_must_fail_for_unsupported_runtime(self):

        runtime = "foo"

        image_builder_mock = Mock()

        with self.assertRaises(ValueError) as context:
            LambdaContainer(
                runtime=runtime,
                imageuri=self.imageuri,
                handler=self.handler,
                packagetype=self.packagetype,
                image_config=self.image_config,
                code_dir=self.code_dir,
                layers=[],
                lambda_image=image_builder_mock,
                architecture="x86_64",
            )

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
    def test_must_return_build_image(self):
        expected = f"public.ecr.aws/lambda/foo:1.0-{RAPID_IMAGE_TAG_PREFIX}-x.y.z"

        image_builder = Mock()
        image_builder.build.return_value = expected

        self.assertEqual(
            LambdaContainer._get_image(
                lambda_image=image_builder,
                runtime="foo1.0",
                packagetype=ZIP,
                image=None,
                layers=[],
                function_name=None,
                architecture="x86_64",
            ),
            expected,
        )

        image_builder.build.assert_called_with("foo1.0", ZIP, None, [], "x86_64", function_name=None)


class TestLambdaContainer_get_debug_settings(TestCase):
    def setUp(self):

        self.debug_ports = [1235]
        self.debug_args = "a=b c=d e=f"
        self.debug_options = DebugContext(debug_ports=[1235], debug_args="a=b c=d e=f")

    def test_must_skip_if_debug_port_is_not_specified(self):
        self.assertEqual(
            (LambdaContainer._DEFAULT_ENTRYPOINT, {}),
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
            self.assertEqual(
                ["/var/rapid/aws-lambda-rie", "--log-level", "error"],
                result,
                "{} runtime must not override entrypoint".format(runtime),
            )

        else:
            with self.assertRaises(DebuggingNotSupported):
                LambdaContainer._get_debug_settings(runtime, self.debug_options)

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_DEBUG_ENV_VARS_ONLY])
    def test_must_provide_container_env_vars(self, runtime):
        _, container_env_vars = LambdaContainer._get_debug_settings(runtime, self.debug_options)

        self.assertIsNotNone(container_env_vars)

    @parameterized.expand([param(r) for r in set(RUNTIMES_WITH_BOOTSTRAP_ENTRYPOINT)])
    def test_debug_arg_must_be_split_by_spaces_and_appended_to_bootstrap_based_entrypoint(self, runtime):
        """
        Debug args list is appended as arguments to bootstrap-args, which is past the fourth position in the array
        """
        expected_debug_args = ["a=b", "c=d", "e=f"]
        result, _ = LambdaContainer._get_debug_settings(runtime, self.debug_options)
        actual = result[4:7]

        self.assertTrue(all(debug_arg in actual for debug_arg in expected_debug_args))

    @parameterized.expand([param(r) for r in RUNTIMES_WITH_ENTRYPOINT])
    def test_must_provide_entrypoint_even_without_debug_args(self, runtime):
        debug_options = DebugContext(debug_ports=[1235], debug_args=None)
        result, _ = LambdaContainer._get_debug_settings(runtime, debug_options)

        self.assertIsNotNone(result)

    @parameterized.expand([(2, "-delveAPI=2"), (2, "-delveAPI 2"), (1, None)])
    def test_delve_api_version_can_be_read_from_debug_args(self, version, debug_args):
        debug_options = DebugContext(debug_ports=[1235], debug_args=debug_args)
        _, env_vars = LambdaContainer._get_debug_settings(Runtime.go1x.value, debug_options)

        self.assertEqual(env_vars.get("_AWS_LAMBDA_GO_DELVE_API_VERSION"), version)


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
