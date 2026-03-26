"""
Testing local lambda runner
"""

import os
import posixpath
from unittest import TestCase
from unittest.mock import Mock, patch
from parameterized import parameterized, param
import click

from samcli.lib.utils.architecture import X86_64, ARM64

from samcli.commands.local.lib.local_lambda import RUST_LOCAL_INVOKE_DISCLAIMER, LocalLambdaRunner
from samcli.lib.providers.provider import Function, FunctionBuildInfo, CapacityProviderConfig
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.local.docker.container import ContainerResponseException, ContainerConnectionTimeoutException
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands.local.lib.exceptions import (
    OverridesNotWellDefinedError,
    NoPrivilegeException,
    InvalidIntermediateImageError,
    UnsupportedInlineCodeError,
)


class TestLocalLambda_get_aws_creds(TestCase):
    def setUp(self):
        self.region = "region"
        self.key = "key"
        self.secret = "secret"
        self.token = "token"

        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        self.cwd = "cwd"
        self.env_vars_values = {}
        self.debug_context = None
        self.aws_profile = "myprofile"
        self.aws_region = "region"
        self.real_path = "/real/path"

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
            aws_profile=self.aws_profile,
            aws_region=self.aws_region,
        )

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_get_from_boto_session(self, boto3_mock):
        creds = Mock()
        creds.access_key = self.key
        creds.secret_key = self.secret
        creds.token = self.token

        mock_session = Mock()
        mock_session.region_name = self.region

        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = creds

        expected = {"region": self.region, "key": self.key, "secret": self.secret, "sessiontoken": self.token}

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called_with(profile_name=self.aws_profile, region_name=self.aws_region)

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)
        # assert no more calls to Session, and use the cached one
        self.assertEqual(boto3_mock.session.Session.call_count, 1)

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_region_name(self, boto3_mock):
        creds = Mock()
        creds.access_key = self.key
        creds.secret_key = self.secret
        creds.token = self.token

        mock_session = Mock()
        del mock_session.region_name  # Ask mock to return AttributeError when 'region_name' is accessed

        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = creds

        expected = {"key": self.key, "secret": self.secret, "sessiontoken": self.token}

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called_with(profile_name=self.aws_profile, region_name=self.aws_region)

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_access_key(self, boto3_mock):
        creds = Mock()
        del creds.access_key  # No access key
        creds.secret_key = self.secret
        creds.token = self.token

        mock_session = Mock()
        mock_session.region_name = self.region

        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = creds

        expected = {"region": self.region, "secret": self.secret, "sessiontoken": self.token}

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called_with(profile_name=self.aws_profile, region_name=self.aws_region)

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_secret_key(self, boto3_mock):
        creds = Mock()
        creds.access_key = self.key
        del creds.secret_key  # No secret key
        creds.token = self.token

        mock_session = Mock()
        mock_session.region_name = self.region

        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = creds

        expected = {"region": self.region, "key": self.key, "sessiontoken": self.token}

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called_with(profile_name=self.aws_profile, region_name=self.aws_region)

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_session_token(self, boto3_mock):
        creds = Mock()
        creds.access_key = self.key
        creds.secret_key = self.secret
        del creds.token  # No Token

        mock_session = Mock()
        mock_session.region_name = self.region

        boto3_mock.DEFAULT_SESSION = None
        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = creds

        expected = {"region": self.region, "key": self.key, "secret": self.secret}

        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called()

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_credentials(self, boto3_mock):
        boto3_mock.DEFAULT_SESSION = None
        mock_session = Mock()
        boto3_mock.session.Session.return_value = mock_session
        mock_session.get_credentials.return_value = None

        expected = {"region": mock_session.region_name}
        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called()

    @patch("samcli.commands.local.lib.local_lambda.boto3")
    def test_must_work_with_no_session(self, boto3_mock):
        boto3_mock.DEFAULT_SESSION = None
        boto3_mock.session.Session.return_value = None

        expected = {}
        actual = self.local_lambda.get_aws_creds()
        self.assertEqual(expected, actual)

        boto3_mock.session.Session.assert_called()


class TestLocalLambda_make_env_vars(TestCase):
    def setUp(self):
        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        self.cwd = "/my/current/working/directory"
        self.real_path = "/real/path"
        self.debug_context = None
        self.aws_profile = "myprofile"
        self.aws_region = "region"
        self.env_vars_values = {}

        self.environ = {"Variables": {"var1": "value1"}}

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
        )

        self.aws_creds = {"key": "key"}
        self.local_lambda.get_aws_creds = Mock()
        self.local_lambda.get_aws_creds.return_value = self.aws_creds

    @parameterized.expand(
        [
            # Override for the function_id exists
            ({"function_id": {"a": "b"}}, {"a": "b"}),
            # Override for the logical_id exists
            ({"logical_id": {"a": "c"}}, {"a": "c"}),
            # Override for the functionname exists
            ({"function_name": {"a": "d"}}, {"a": "d"}),
            # Override for the full_path exists
            ({posixpath.join("somepath", "function_id"): {"a": "d"}}, {"a": "d"}),
            # Override for the function does *not* exist
            ({"otherfunction": {"c": "d"}}, {}),
            # Using a CloudFormation parameter file format
            ({"Parameters": {"p1": "v1"}}, {"p1": "v1"}),
            # Mix of Cloudformation and standard parameter format
            ({"Parameters": {"p1": "v1"}, "logical_id": {"a": "b"}}, {"p1": "v1", "a": "b"}),
            ({"Parameters": {"p1": "v1"}, "logical_id": {"p1": "v2"}}, {"p1": "v2"}),
        ]
    )
    @patch("samcli.commands.local.lib.local_lambda.EnvironmentVariables")
    @patch("samcli.commands.local.lib.local_lambda.os")
    def test_must_work_with_override_values(
        self, env_vars_values, expected_override_value, os_mock, EnvironmentVariablesMock
    ):
        os_environ = {"some": "value"}
        os_mock.environ = os_environ

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=self.environ,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
            logging_config={"LogFormat": "JSON"},
            capacity_provider_config={
                "Arn": "arn:aws:lambda:us-east-1:123456789012:capacity-provider:my-capacity-provider-name",
                "PerExecutionEnvironmentMaxConcurrency": 8,
            },
        )

        self.local_lambda.env_vars_values = env_vars_values

        self.local_lambda._make_env_vars(function)

        EnvironmentVariablesMock.assert_called_with(
            function.name,
            function.memory,
            function.timeout,
            function.handler,
            function.logging_config,
            variables={"var1": "value1"},
            shell_env_values=os_environ,
            override_values=expected_override_value,
            aws_creds=self.aws_creds,
            capacity_provider_configuration=CapacityProviderConfig(
                arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:my-capacity-provider-name",
                execution_environment_max_concurrency=8,
            ),
            is_debugging=False,
        )

    @parameterized.expand(
        [
            # Using a invalid file format
            ({"a": "b"}, OverridesNotWellDefinedError),
            ({"a": False}, OverridesNotWellDefinedError),
            ({"a": [True, False]}, OverridesNotWellDefinedError),
        ]
    )
    @patch("samcli.commands.local.lib.local_lambda.os")
    def test_must_not_work_with_invalid_override_values(self, env_vars_values, expected_exception, os_mock):
        os_environ = {"some": "value"}
        os_mock.environ = os_environ

        function = Function(
            stack_path="",
            function_id="function_name",
            name="function_name",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=self.environ,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )

        self.local_lambda.env_vars_values = env_vars_values

        with self.assertRaises(expected_exception):
            self.local_lambda._make_env_vars(function)

    @parameterized.expand(
        [
            param({"a": "b"}),  # Does not have the "Variables" Key
            param("somestring"),  # Must be a dict type
            param(None),
        ]
    )
    @patch("samcli.commands.local.lib.local_lambda.EnvironmentVariables")
    @patch("samcli.commands.local.lib.local_lambda.os")
    def test_must_work_with_invalid_environment_variable(self, environment_variable, os_mock, EnvironmentVariablesMock):
        os_environ = {"some": "value"}
        os_mock.environ = os_environ

        function = Function(
            stack_path="",
            function_id="function_name",
            name="function_name",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=environment_variable,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )

        self.local_lambda.env_vars_values = {}

        self.local_lambda._make_env_vars(function)

        EnvironmentVariablesMock.assert_called_with(
            function.name,
            function.memory,
            function.timeout,
            function.handler,
            None,
            variables=None,
            shell_env_values=os_environ,
            override_values={},
            aws_creds=self.aws_creds,
            capacity_provider_configuration=None,
            is_debugging=False,
        )


class TestLocalLambda_get_invoke_config(TestCase):
    def setUp(self):
        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        # assuming there is only 1 root stack
        self.function_provider_mock.stacks = [
            Mock(stack_path="", location="template.yaml"),
            Mock(stack_path="ChildStackX", location=os.path.join("ChildStackX", "template.yaml")),
        ]
        self.cwd = "/my/current/working/directory"
        self.aws_profile = "myprofile"
        self.debug_context = None
        self.env_vars_values = {}
        self.aws_region = "region"
        self.real_path = "/real/path"

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
        )

    @patch("samcli.commands.local.lib.local_lambda.resolve_code_path")
    @patch("samcli.commands.local.lib.local_lambda.LocalLambdaRunner.is_debugging")
    @patch("samcli.commands.local.lib.local_lambda.FunctionConfig")
    def test_must_work(self, FunctionConfigMock, is_debugging_mock, resolve_code_path_patch):
        is_debugging_mock.return_value = False

        env_vars = "envvars"
        self.local_lambda._make_env_vars = Mock()
        self.local_lambda._make_env_vars.return_value = env_vars

        codepath = "codepath"
        resolve_code_path_patch.return_value = codepath

        layers = ["layer1", "layer2"]

        function = Function(
            stack_path="",
            function_id="function_name",
            name="function_name",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=layers,
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[ARM64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )

        config = "someconfig"
        FunctionConfigMock.return_value = config
        actual = self.local_lambda.get_invoke_config(function)
        self.assertEqual(actual, config)

        FunctionConfigMock.assert_called_with(
            imageconfig=function.imageconfig,
            imageuri=function.imageuri,
            name=function.functionname,
            packagetype=function.packagetype,
            runtime=function.runtime,
            handler=function.handler,
            code_abs_path=codepath,
            layers=layers,
            memory=function.memory,
            timeout=function.timeout,
            env_vars=env_vars,
            architecture=ARM64,
            full_path=function.full_path,
            runtime_management_config=function.runtime_management_config,
            code_real_path=codepath,
            capacity_provider_configuration=function.capacity_provider_configuration,
            durable_config=function.durable_config,
        )

        resolve_code_path_patch.assert_called_with(self.real_path, function.codeuri)
        self.local_lambda._make_env_vars.assert_called_with(function)

    @patch("samcli.commands.local.lib.local_lambda.resolve_code_path")
    @patch("samcli.commands.local.lib.local_lambda.LocalLambdaRunner.is_debugging")
    @patch("samcli.commands.local.lib.local_lambda.FunctionConfig")
    def test_must_work_with_runtime_option(self, FunctionConfigMock, is_debugging_mock, resolve_code_path_patch):
        is_debugging_mock.return_value = False

        env_vars = "envvars"
        self.local_lambda._make_env_vars = Mock()
        self.local_lambda._make_env_vars.return_value = env_vars

        codepath = "codepath"
        resolve_code_path_patch.return_value = codepath

        layers = ["layer1", "layer2"]

        function = Function(
            stack_path="",
            function_id="function_name",
            name="function_name",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=layers,
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[ARM64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )

        config = "someconfig"
        override_runtime = "python3.11"
        FunctionConfigMock.return_value = config
        actual = self.local_lambda.get_invoke_config(function, override_runtime)
        self.assertEqual(actual, config)

        FunctionConfigMock.assert_called_with(
            imageconfig=function.imageconfig,
            imageuri=function.imageuri,
            name=function.functionname,
            packagetype=function.packagetype,
            runtime=override_runtime,
            handler=function.handler,
            code_abs_path=codepath,
            layers=layers,
            memory=function.memory,
            timeout=function.timeout,
            env_vars=env_vars,
            architecture=ARM64,
            full_path=function.full_path,
            runtime_management_config=function.runtime_management_config,
            code_real_path=codepath,
            capacity_provider_configuration=function.capacity_provider_configuration,
            durable_config=function.durable_config,
        )

        resolve_code_path_patch.assert_called_with(self.real_path, function.codeuri)
        self.local_lambda._make_env_vars.assert_called_with(function)

    @patch("samcli.commands.local.lib.local_lambda.resolve_code_path")
    @patch("samcli.commands.local.lib.local_lambda.LocalLambdaRunner.is_debugging")
    @patch("samcli.commands.local.lib.local_lambda.FunctionConfig")
    def test_timeout_set_to_max_during_debugging(
        self,
        FunctionConfigMock,
        is_debugging_mock,
        resolve_code_path_patch,
    ):
        is_debugging_mock.return_value = True

        env_vars = "envvars"
        self.local_lambda._make_env_vars = Mock()
        self.local_lambda._make_env_vars.return_value = env_vars

        codepath = "codepath"
        resolve_code_path_patch.return_value = codepath

        function = Function(
            stack_path="stackA/stackB",
            function_id="function_name",
            name="function_name",
            functionname="function_name",
            runtime="runtime",
            memory=1234,
            timeout=36000,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            function_url_config=None,
            codesign_config_arn=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )

        config = "someconfig"
        FunctionConfigMock.return_value = config
        actual = self.local_lambda.get_invoke_config(function)
        self.assertEqual(actual, config)

        FunctionConfigMock.assert_called_with(
            imageconfig=function.imageconfig,
            imageuri=function.imageuri,
            name=function.functionname,
            packagetype=function.packagetype,
            runtime=function.runtime,
            handler=function.handler,
            code_abs_path=codepath,
            layers=[],
            memory=function.memory,
            timeout=function.timeout,
            env_vars=env_vars,
            architecture=X86_64,
            full_path=function.full_path,
            runtime_management_config=function.runtime_management_config,
            code_real_path=codepath,
            capacity_provider_configuration=function.capacity_provider_configuration,
            durable_config=function.durable_config,
        )

        resolve_code_path_patch.assert_called_with(self.real_path, "codeuri")
        self.local_lambda._make_env_vars.assert_called_with(function)


class TestLocalLambda_invoke(TestCase):
    def setUp(self):
        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        self.cwd = "/my/current/working/directory"
        self.debug_context = None
        self.aws_profile = "myprofile"
        self.aws_region = "region"
        self.env_vars_values = {}
        self.real_path = "/real/path"

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
        )

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_work(self, patched_validate_architecture_runtime):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="name")
        invoke_config = "config"

        self.function_provider_mock.get_all.return_value = [function]
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

        self.runtime_mock.invoke.assert_called_with(
            invoke_config,
            event,
            None,
            invocation_type="RequestResponse",
            debug_context=None,
            stdout=stdout,
            stderr=stderr,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            durable_execution_name=None,
        )

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_returns_headers(self, patched_validate_architecture_runtime):
        name = "name"
        event = "event"
        function = Mock(functionname="name")
        invoke_config = "config"
        expected_headers = {
            "X-Amz-Durable-Execution-Arn": "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        }

        self.function_provider_mock.get_all.return_value = [function]
        self.local_lambda.get_invoke_config = Mock(return_value=invoke_config)
        self.runtime_mock.invoke.return_value = expected_headers

        result = self.local_lambda.invoke(name, event)

        self.assertEqual(result, expected_headers)

    @patch("click.echo")
    @patch("platform.platform")
    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_displays_rust_disclaimer(self, patched_validate_architecture_runtime, patched_platform, patched_echo):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        metadata = {"BuildMethod": "rust-cargolambda"}
        function = Mock(functionname="name", metadata=metadata)
        patched_platform.return_value = "macOS-14.5-arm64-arm-64bit"

        invoke_config = "config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

        patched_echo.assert_called_once_with(Colored().yellow(RUST_LOCAL_INVOKE_DISCLAIMER))

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_work_packagetype_ZIP(self, patched_validate_architecture_runtime):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="name", handler="app.handler", runtime="test", packagetype=ZIP, inlinecode=None)
        invoke_config = "config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

        self.runtime_mock.invoke.assert_called_with(
            invoke_config,
            event,
            None,
            invocation_type="RequestResponse",
            debug_context=None,
            stdout=stdout,
            stderr=stderr,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            durable_execution_name=None,
        )

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_raise_if_no_privilege(self, patched_validate_architecture_runtime):
        function = Mock()
        function.name = "name"
        function.functionname = "FunctionLogicalId"
        invoke_config = "config"

        self.function_provider_mock.get_all.return_value = [function]
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        os_error = OSError()
        os_error.winerror = 1314
        self.runtime_mock.invoke.side_effect = os_error

        with self.assertRaises(NoPrivilegeException):
            self.local_lambda.invoke("name", "event")

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_raise_os_error(self, patched_validate_architecture_runtime):
        function = Mock()
        function.name = "name"
        function.functionname = "FunctionLogicalId"
        invoke_config = "config"

        self.function_provider_mock.get_all.return_value = [function]
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        os_error = OSError()
        os_error.winerror = 1315
        self.runtime_mock.invoke.side_effect = os_error

        with self.assertRaises(OSError):
            self.local_lambda.invoke("name", "event")

    def test_must_raise_if_function_not_found(self):
        function = Mock()
        function.name = "name"
        function.functionname = "FunctionLogicalId"

        self.function_provider_mock.get.return_value = None  # function not found
        self.function_provider_mock.get_all.return_value = [function]
        with self.assertRaises(FunctionNotFound):
            self.local_lambda.invoke("name", "event")

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_not_raise_if_invoked_container_has_no_response(self, patched_validate_architecture_runtime):
        function = Mock()
        function.name = "name"
        function.functionname = "FunctionLogicalId"
        invoke_config = "invoke_config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config
        self.runtime_mock.invoke = Mock(side_effect=ContainerResponseException)
        # No exception raised back
        self.local_lambda.invoke("name", "event")

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_not_raise_if_container_connection_timeout(self, patched_validate_architecture_runtime):
        """Test that ContainerConnectionTimeoutException is handled gracefully"""
        function = Mock()
        function.name = "name"
        function.functionname = "FunctionLogicalId"
        invoke_config = "invoke_config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config
        self.runtime_mock.invoke = Mock(side_effect=ContainerConnectionTimeoutException("Connection timeout"))
        # No exception raised back
        self.local_lambda.invoke("name", "event")

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_works_if_imageuri_and_Image_packagetype(self, patched_validate_architecture_runtime):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="name", packagetype=IMAGE, imageuri="testimage:tag")
        invoke_config = "config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config
        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)
        self.runtime_mock.invoke.assert_called_with(
            invoke_config,
            event,
            None,
            invocation_type="RequestResponse",
            debug_context=None,
            stdout=stdout,
            stderr=stderr,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            durable_execution_name=None,
        )

    def test_must_raise_if_imageuri_not_found(self):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="name", packagetype=IMAGE, imageuri=None)

        self.function_provider_mock.get.return_value = function

        with self.assertRaises(InvalidIntermediateImageError):
            self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

    def test_must_raise_unsupported_error_if_inlinecode_found(self):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(
            functionname="name",
            handler="app.handler",
            runtime="test",
            packagetype=ZIP,
            inlinecode="| \
        exports.handler = async () => 'Hello World!'",
        )

        self.function_provider_mock.get.return_value = function

        with self.assertRaises(UnsupportedInlineCodeError):
            self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_work_with_nested_stack_name(self, patched_validate_architecture_runtime):
        name = "NestedStack/FunctionName"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="NestedStack/FunctionName")
        invoke_config = "config"

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

        self.runtime_mock.invoke.assert_called_with(
            invoke_config,
            event,
            None,
            invocation_type="RequestResponse",
            durable_execution_name=None,
            debug_context=None,
            stdout=stdout,
            stderr=stderr,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
        )


class TestLocalLambda_invoke_with_container_host_option(TestCase):
    def setUp(self):
        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        self.cwd = "/my/current/working/directory"
        self.debug_context = None
        self.aws_profile = "myprofile"
        self.aws_region = "region"
        self.env_vars_values = {}
        self.container_host = "localhost"
        self.container_host_interface = "127.0.0.1"
        self.real_path = "/real/path"

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
        )

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_must_work(self, patched_validate_architecture_runtime):
        name = "name"
        event = "event"
        stdout = "stdout"
        stderr = "stderr"
        function = Mock(functionname="name")
        invoke_config = "config"

        self.function_provider_mock.get_all.return_value = [function]
        self.local_lambda.get_invoke_config = Mock()
        self.local_lambda.get_invoke_config.return_value = invoke_config

        self.local_lambda.invoke(name, event, tenant_id=None, stdout=stdout, stderr=stderr)

        self.runtime_mock.invoke.assert_called_with(
            invoke_config,
            event,
            None,
            invocation_type="RequestResponse",
            debug_context=None,
            stdout=stdout,
            stderr=stderr,
            container_host="localhost",
            container_host_interface="127.0.0.1",
            extra_hosts=None,
            durable_execution_name=None,
        )


class TestLocalLambda_is_debugging(TestCase):
    def setUp(self):
        self.runtime_mock = Mock()
        self.function_provider_mock = Mock()
        self.cwd = "/my/current/working/directory"
        self.debug_context = Mock()
        self.aws_profile = "myprofile"
        self.aws_region = "region"
        self.env_vars_values = {}
        self.real_path = "/real/path"

        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            real_path=self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=self.debug_context,
        )

    def test_must_be_on(self):
        self.assertTrue(self.local_lambda.is_debugging())

    def test_must_be_off(self):
        self.local_lambda = LocalLambdaRunner(
            self.runtime_mock,
            self.function_provider_mock,
            self.cwd,
            self.real_path,
            env_vars_values=self.env_vars_values,
            debug_context=None,
        )

        self.assertFalse(self.local_lambda.is_debugging())


class TestLocalLambda_tenant_id_validation(TestCase):
    def setUp(self):
        self.function_provider_mock = Mock()
        self.local_lambda = LocalLambdaRunner(
            local_runtime=Mock(),
            function_provider=self.function_provider_mock,
            cwd="cwd",
            debug_context=Mock(),
            real_path="real_path",
        )

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_multi_tenant_function_without_tenant_id_raises_error(self, mock_validate_arch):
        """Test that multi-tenant function without tenant-id raises ClickException"""
        function = Function(
            function_id="id",
            name="name",
            functionname="functionname",
            runtime="python3.9",
            memory=128,
            timeout=30,
            handler="app.handler",
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
            stack_path="",
            logging_config=None,
            tenancy_config={"TenantIsolationMode": "PER_TENANT"},
        )

        self.function_provider_mock.get.return_value = function

        with self.assertRaises(click.ClickException) as context:
            self.local_lambda.invoke("functionname", "{}")

        self.assertIn("Add a valid tenant ID", str(context.exception))

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_non_multi_tenant_function_with_tenant_id_raises_error(self, mock_validate_arch):
        """Test that non-multi-tenant function with tenant-id raises ClickException"""
        function = Function(
            function_id="id",
            name="name",
            functionname="functionname",
            runtime="python3.9",
            memory=128,
            timeout=30,
            handler="app.handler",
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
            stack_path="",
            logging_config=None,
            tenancy_config=None,
        )

        self.function_provider_mock.get.return_value = function

        with self.assertRaises(click.ClickException) as context:
            self.local_lambda.invoke("functionname", "{}", tenant_id="customer-123")

        self.assertIn("Remove the tenant ID", str(context.exception))

    @patch("samcli.commands.local.lib.local_lambda.validate_architecture_runtime")
    def test_multi_tenant_function_with_tenant_id_succeeds(self, mock_validate_arch):
        """Test that multi-tenant function with tenant-id proceeds without error"""
        function = Function(
            function_id="id",
            name="name",
            functionname="functionname",
            runtime="python3.9",
            memory=128,
            timeout=30,
            handler="app.handler",
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            function_url_config=None,
            runtime_management_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
            stack_path="",
            logging_config=None,
            tenancy_config={"TenantIsolationMode": "PER_TENANT"},
        )

        self.function_provider_mock.get.return_value = function
        self.local_lambda.get_invoke_config = Mock(return_value="config")

        # This should not raise an exception
        try:
            self.local_lambda.invoke("functionname", "{}", tenant_id="customer-123")
        except click.ClickException:
            self.fail("invoke() raised ClickException unexpectedly")
