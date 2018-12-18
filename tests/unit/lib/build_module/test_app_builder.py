
import os
import docker
import json

from unittest import TestCase
from mock import Mock, call, patch
from parameterized import parameterized

from samcli.lib.build.app_builder import ApplicationBuilder, _get_workflow_config,\
    UnsupportedBuilderLibraryVersionError, UnsupportedRuntimeException, BuildError, \
    LambdaBuilderError


class Test_get_workflow_config(TestCase):

    @parameterized.expand([
        ("python2.7", ),
        ("python3.6", )
    ])
    def test_must_work_for_python(self, runtime):

        result = _get_workflow_config(runtime)
        self.assertEquals(result.language, "python")
        self.assertEquals(result.dependency_manager, "pip")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "requirements.txt")

    @parameterized.expand([
        ("nodejs6.10", ),
        ("nodejs8.10", ),
        ("nodejsX.Y", ),
        ("nodejs", )
    ])
    def test_must_work_for_nodejs(self, runtime):

        result = _get_workflow_config(runtime)
        self.assertEquals(result.language, "nodejs")
        self.assertEquals(result.dependency_manager, "npm")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "package.json")

    def test_must_raise_for_unsupported_runtimes(self):

        runtime = "foobar"

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            _get_workflow_config(runtime)

        self.assertEquals(str(ctx.exception),
                          "'foobar' runtime is not supported")


class TestApplicationBuilder_build(TestCase):

    def setUp(self):
        self.mock_func_provider = Mock()
        self.builder = ApplicationBuilder(self.mock_func_provider,
                                          "builddir",
                                          "basedir")

    def test_must_iterate_on_functions(self):
        func1 = Mock()
        func2 = Mock()
        build_function_mock = Mock()

        self.mock_func_provider.get_all.return_value = [func1, func2]
        self.builder._build_function = build_function_mock

        result = self.builder.build()

        self.assertEquals(result, {
            func1.name: build_function_mock.return_value,
            func2.name: build_function_mock.return_value,
        })

        build_function_mock.assert_has_calls([
            call(func1.name, func1.codeuri, func1.runtime),
            call(func2.name, func2.codeuri, func2.runtime),
        ], any_order=False)


class TestApplicationBuilder_update_template(TestCase):

    def setUp(self):
        self.builder = ApplicationBuilder(Mock(),
                                          "builddir",
                                          "basedir")

        self.template_dict = {
            "Resources": {
                "MyFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "oldvalue"
                    }
                },
                "MyFunction2": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": "oldvalue"
                    }
                },
                "OtherResource": {
                    "Type": "AWS::Lambda::Version",
                    "Properties": {
                        "CodeUri": "something"
                    }
                }
            }
        }

    def test_must_write_relative_build_artifacts_path(self):
        original_template_path = "/path/to/tempate.txt"
        built_artifacts = {
            "MyFunction1": "/path/to/build/MyFunction1",
            "MyFunction2": "/path/to/build/MyFunction2"
        }

        expected_result = {
            "Resources": {
                "MyFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": os.path.join("build", "MyFunction1")
                    }
                },
                "MyFunction2": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": os.path.join("build", "MyFunction2")
                    }
                },
                "OtherResource": {
                    "Type": "AWS::Lambda::Version",
                    "Properties": {
                        "CodeUri": "something"
                    }
                }
            }
        }

        actual = self.builder.update_template(self.template_dict, original_template_path, built_artifacts)
        self.assertEquals(actual, expected_result)

    def test_must_skip_if_no_artifacts(self):

        built_artifacts = {}
        actual = self.builder.update_template(self.template_dict, "/foo/bar/template.txt", built_artifacts)

        self.assertEquals(actual, self.template_dict)


class TestApplicationBuilder_build_function(TestCase):

    def setUp(self):
        self.builder = ApplicationBuilder(Mock(),
                                          "/build/dir",
                                          "/base/dir")

    @patch("samcli.lib.build.app_builder._get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_process(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        scratch_dir = "scratch"
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_in_process = Mock()

        code_dir = "/base/dir/path/to/source"
        artifacts_dir = "/build/dir/function_name"
        manifest_path = os.path.join(code_dir, config_mock.manifest_name)

        self.builder._build_function(function_name, codeuri, runtime)

        self.builder._build_function_in_process.assert_called_with(config_mock,
                                                                   code_dir,
                                                                   artifacts_dir,
                                                                   scratch_dir,
                                                                   manifest_path,
                                                                   runtime)

    @patch("samcli.lib.build.app_builder._get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        scratch_dir = "scratch"
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_on_container = Mock()

        code_dir = "/base/dir/path/to/source"
        artifacts_dir = "/build/dir/function_name"
        manifest_path = os.path.join(code_dir, config_mock.manifest_name)

        # Settting the container manager will make us use the container
        self.builder._container_manager = Mock()
        self.builder._build_function(function_name, codeuri, runtime)

        self.builder._build_function_on_container.assert_called_with(config_mock,
                                                                     code_dir,
                                                                     artifacts_dir,
                                                                     scratch_dir,
                                                                     manifest_path,
                                                                     runtime)


class TestApplicationBuilder_build_function_in_process(TestCase):

    def setUp(self):
        self.builder = ApplicationBuilder(Mock(),
                                          "/build/dir",
                                          "/base/dir")

    @patch("samcli.lib.build.app_builder.LambdaBuilder")
    def test_must_use_lambda_builder(self, lambda_builder_mock):
        config_mock = Mock()
        builder_instance_mock = lambda_builder_mock.return_value = Mock()

        result = self.builder._build_function_in_process(config_mock,
                                                         "source_dir",
                                                         "artifacts_dir",
                                                         "scratch_dir",
                                                         "manifest_path",
                                                         "runtime")
        self.assertEquals(result, "artifacts_dir")

        lambda_builder_mock.assert_called_with(language=config_mock.language,
                                               dependency_manager=config_mock.dependency_manager,
                                               application_framework=config_mock.application_framework)

        builder_instance_mock.build.assert_called_with("source_dir",
                                                       "artifacts_dir",
                                                       "scratch_dir",
                                                       "manifest_path",
                                                       runtime="runtime")

    @patch("samcli.lib.build.app_builder.LambdaBuilder")
    def test_must_raise_on_error(self, lambda_builder_mock):
        config_mock = Mock()
        builder_instance_mock = lambda_builder_mock.return_value = Mock()
        builder_instance_mock.build.side_effect = LambdaBuilderError()

        with self.assertRaises(BuildError):
            self.builder._build_function_in_process(config_mock,
                                                    "source_dir",
                                                    "artifacts_dir",
                                                    "scratch_dir",
                                                    "manifest_path",
                                                    "runtime")


class TestApplicationBuilder_build_function_on_container(TestCase):

    def setUp(self):
        self.container_manager = Mock()
        self.builder = ApplicationBuilder(Mock(),
                                          "/build/dir",
                                          "/base/dir",
                                          container_manager=self.container_manager)
        self.builder._parse_builder_response = Mock()

    @patch("samcli.lib.build.app_builder.LambdaBuildContainer")
    @patch("samcli.lib.build.app_builder.lambda_builders_protocol_version")
    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container(self, osutils_mock, LOGMock, protocol_version_mock, LambdaBuildContainerMock):
        config = Mock()
        log_level = LOGMock.getEffectiveLevel.return_value = 'foo'
        stdout_data = "container stdout response data"
        response = {
            "result": {
                "artifacts_dir": "/some/dir"
            }

        }

        def mock_wait_for_logs(stdout, stderr):
            stdout.write(stdout_data.encode('utf-8'))

        # Wire all mocks correctly
        container_mock = LambdaBuildContainerMock.return_value = Mock()
        container_mock.wait_for_logs = mock_wait_for_logs
        self.builder._parse_builder_response.return_value = response

        result = self.builder._build_function_on_container(config,
                                                           "source_dir",
                                                           "artifacts_dir",
                                                           "scratch_dir",
                                                           "manifest_path",
                                                           "runtime")
        self.assertEquals(result, "artifacts_dir")

        LambdaBuildContainerMock.assert_called_once_with(protocol_version_mock,
                                                         config.language,
                                                         config.dependency_manager,
                                                         config.application_framework,
                                                         "source_dir",
                                                         "manifest_path",
                                                         "runtime",
                                                         log_level=log_level,
                                                         optimizations=None,
                                                         options=None)

        self.container_manager.run.assert_called_with(container_mock)
        self.builder._parse_builder_response.assert_called_once_with(stdout_data, container_mock.image)
        container_mock.copy.assert_called_with(response["result"]["artifacts_dir"] + "/.",
                                               "artifacts_dir")

    @patch("samcli.lib.build.app_builder.LambdaBuildContainer")
    def test_must_raise_on_unsupported_container(self, LambdaBuildContainerMock):
        config = Mock()

        container_mock = LambdaBuildContainerMock.return_value = Mock()
        container_mock.image = "image name"
        container_mock.executable_name = "myexecutable"

        self.container_manager.run.side_effect = docker.errors.APIError("Bad Request: 'lambda-builders' "
                                                                        "executable file not found in $PATH")

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._build_function_on_container(config,
                                                      "source_dir",
                                                      "artifacts_dir",
                                                      "scratch_dir",
                                                      "manifest_path",
                                                      "runtime")

        msg = "You are running an outdated version of Docker container 'image name' that is not compatible with" \
              "this version of SAM CLI. Please upgrade to continue to continue with build. " \
              "Reason: 'myexecutable executable not found in container'"

        self.assertEquals(str(ctx.exception), msg)


class TestApplicationBuilder_parse_builder_response(TestCase):

    def setUp(self):
        self.image_name = "name"
        self.builder = ApplicationBuilder(Mock(),
                                          "/build/dir",
                                          "/base/dir")

    def test_must_parse_json(self):
        data = {"valid": "json"}

        result = self.builder._parse_builder_response(json.dumps(data), self.image_name)
        self.assertEquals(result, data)

    def test_must_fail_on_invalid_json(self):
        data = "{invalid: json}"

        with self.assertRaises(ValueError):
            self.builder._parse_builder_response(data, self.image_name)

    def test_must_raise_on_user_error(self):
        msg = "invalid params"
        data = {"error": {"code": 488, "message": msg}}

        with self.assertRaises(BuildError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        self.assertEquals(str(ctx.exception), msg)

    def test_must_raise_on_version_mismatch(self):
        msg = "invalid params"
        data = {"error": {"code": 505, "message": msg}}

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        expected = str(UnsupportedBuilderLibraryVersionError(self.image_name, msg))
        self.assertEquals(str(ctx.exception), expected)

    def test_must_raise_on_method_not_found(self):
        msg = "invalid method"
        data = {"error": {"code": -32601, "message": msg}}

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        expected = str(UnsupportedBuilderLibraryVersionError(self.image_name, msg))
        self.assertEquals(str(ctx.exception), expected)

    def test_must_raise_on_all_other_codes(self):
        msg = "builder crashed"
        data = {"error": {"code": 1, "message": msg}}

        with self.assertRaises(ValueError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        self.assertEquals(str(ctx.exception), msg)
