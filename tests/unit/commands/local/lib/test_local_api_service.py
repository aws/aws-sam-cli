"""
Unit test for local API service
"""

from unittest import TestCase
from mock import Mock, patch

from samcli.commands.local.lib.local_api_service import LocalApiService
from samcli.commands.local.lib.exceptions import NoApisDefined
from samcli.commands.local.lib.provider import Api
from samcli.local.apigw.local_apigw_service import Route


class TestLocalApiService_start(TestCase):

    def setUp(self):
        self.port = 123
        self.host = "abc"
        self.static_dir = "static"
        self.cwd = "cwd"
        self.template = {"hello": "world"}

        self.lambda_invoke_context_mock = Mock()
        self.lambda_runner_mock = Mock()
        self.api_provider_mock = Mock()
        self.apigw_service = Mock()
        self.stderr_mock = Mock()

        self.lambda_invoke_context_mock.template = self.template
        self.lambda_invoke_context_mock.local_lambda_runner = self.lambda_runner_mock
        self.lambda_invoke_context_mock.get_cwd = Mock()
        self.lambda_invoke_context_mock.get_cwd.return_value = self.cwd
        self.lambda_invoke_context_mock.stderr = self.stderr_mock

    @patch("samcli.commands.local.lib.local_api_service.LocalApigwService")
    @patch("samcli.commands.local.lib.local_api_service.SamApiProvider")
    @patch.object(LocalApiService, "_make_static_dir_path")
    @patch.object(LocalApiService, "_print_routes")
    @patch.object(LocalApiService, "_make_routing_list")
    def test_must_start_service(self,
                                make_routing_list_mock,
                                log_routes_mock,
                                make_static_dir_mock,
                                SamApiProviderMock,
                                ApiGwServiceMock):

        routing_list = [1, 2, 3]  # something
        static_dir_path = "/foo/bar"

        make_routing_list_mock.return_value = routing_list
        make_static_dir_mock.return_value = static_dir_path

        SamApiProviderMock.return_value = self.api_provider_mock
        ApiGwServiceMock.return_value = self.apigw_service

        # Now start the service
        local_service = LocalApiService(self.lambda_invoke_context_mock, self.port, self.host, self.static_dir)
        local_service.start()

        # Make sure the right methods are called
        SamApiProviderMock.assert_called_with(self.template,
                                              cwd=self.cwd,
                                              parameter_overrides=self.lambda_invoke_context_mock.parameter_overrides)

        make_routing_list_mock.assert_called_with(self.api_provider_mock)
        log_routes_mock.assert_called_with(self.api_provider_mock, self.host, self.port)
        make_static_dir_mock.assert_called_with(self.cwd, self.static_dir)
        ApiGwServiceMock.assert_called_with(routing_list=routing_list,
                                            lambda_runner=self.lambda_runner_mock,
                                            static_dir=static_dir_path,
                                            port=self.port,
                                            host=self.host,
                                            stderr=self.stderr_mock)

        self.apigw_service.create.assert_called_with()
        self.apigw_service.run.assert_called_with()

    @patch("samcli.commands.local.lib.local_api_service.LocalApigwService")
    @patch("samcli.commands.local.lib.local_api_service.SamApiProvider")
    @patch.object(LocalApiService, "_make_static_dir_path")
    @patch.object(LocalApiService, "_print_routes")
    @patch.object(LocalApiService, "_make_routing_list")
    def test_must_raise_if_route_not_available(self,
                                               make_routing_list_mock,
                                               log_routes_mock,
                                               make_static_dir_mock,
                                               SamApiProviderMock,
                                               ApiGwServiceMock):

        routing_list = []  # Empty

        make_routing_list_mock.return_value = routing_list

        SamApiProviderMock.return_value = self.api_provider_mock
        ApiGwServiceMock.return_value = self.apigw_service

        # Now start the service
        local_service = LocalApiService(self.lambda_invoke_context_mock, self.port, self.host, self.static_dir)

        with self.assertRaises(NoApisDefined):
            local_service.start()


class TestLocalApiService_make_routing_list(TestCase):

    def test_must_return_routing_list_from_apis(self):
        api_provider = Mock()
        apis = [
            Api(path="/1", method="GET1", function_name="name1", cors="CORS1"),
            Api(path="/2", method="GET2", function_name="name2", cors="CORS2"),
            Api(path="/3", method="GET3", function_name="name3", cors="CORS3"),
        ]
        expected = [
            Route(path="/1", methods=["GET1"], function_name="name1"),
            Route(path="/2", methods=["GET2"], function_name="name2"),
            Route(path="/3", methods=["GET3"], function_name="name3")
        ]

        api_provider.get_all.return_value = apis

        result = LocalApiService._make_routing_list(api_provider)
        self.assertEquals(len(result), len(expected))
        for index, r in enumerate(result):
            self.assertEquals(r.__dict__, expected[index].__dict__)


class TestLocalApiService_print_routes(TestCase):

    def test_must_print_routes(self):
        host = "host"
        port = 123

        api_provider = Mock()
        apis = [
            Api(path="/1", method="GET", function_name="name1", cors="CORS1"),
            Api(path="/1", method="POST", function_name="name1", cors="CORS1"),
            Api(path="/1", method="DELETE", function_name="othername1", cors="CORS1"),
            Api(path="/2", method="GET2", function_name="name2", cors="CORS2"),
            Api(path="/3", method="GET3", function_name="name3", cors="CORS3"),
        ]
        api_provider.get_all.return_value = apis

        expected = {"Mounting name1 at http://host:123/1 [GET, POST]",
                    "Mounting othername1 at http://host:123/1 [DELETE]",
                    "Mounting name2 at http://host:123/2 [GET2]",
                    "Mounting name3 at http://host:123/3 [GET3]"}

        actual = LocalApiService._print_routes(api_provider, host, port)
        self.assertEquals(expected, set(actual))


class TestLocalApiService_make_static_dir_path(TestCase):

    def test_must_skip_if_none(self):
        result = LocalApiService._make_static_dir_path("something", None)
        self.assertIsNone(result)

    @patch("samcli.commands.local.lib.local_api_service.os")
    def test_must_resolve_with_respect_to_cwd(self, os_mock):
        static_dir = "mydir"
        cwd = "cwd"
        resolved_path = "cwd/mydir"

        os_mock.path.join.return_value = resolved_path
        os_mock.path.exists.return_value = True  # Fake the path to exist

        result = LocalApiService._make_static_dir_path(cwd, static_dir)
        self.assertEquals(resolved_path, result)

        os_mock.path.join.assert_called_with(cwd, static_dir)
        os_mock.path.exists.assert_called_with(resolved_path)

    @patch("samcli.commands.local.lib.local_api_service.os")
    def test_must_return_none_if_path_not_exists(self, os_mock):
        static_dir = "mydir"
        cwd = "cwd"
        resolved_path = "cwd/mydir"

        os_mock.path.join.return_value = resolved_path
        os_mock.path.exists.return_value = False  # Resolved path does not exist

        result = LocalApiService._make_static_dir_path(cwd, static_dir)
        self.assertIsNone(result)
