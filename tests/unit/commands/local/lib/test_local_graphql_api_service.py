"""
Unit test for local GraphQL API service
"""

from unittest import TestCase

from unittest.mock import Mock, patch

from samcli.lib.providers.provider import Api
from samcli.lib.providers.graphql_api_collector import GraphQLApiCollector
from samcli.lib.providers.graphql_api_provider import GraphQLApiProvider
from samcli.commands.local.lib.exceptions import NoApisDefined
from samcli.commands.local.lib.local_graphql_api_service import LocalGraphQLApiService
from samcli.local.appsync.local_appsync_service import Resolver


class TestLocalGraphQLApiService_start(TestCase):
    def setUp(self):
        self.port = 123
        self.host = "abc"
        self.cwd = "cwd"
        self.template = {"hello": "world"}
        self.static_dir = "/foo/bar"

        self.lambda_invoke_context_mock = Mock()
        self.lambda_runner_mock = Mock()
        self.api_provider_mock = Mock()
        self.appsync_service_mock = Mock()
        self.stderr_mock = Mock()

        self.lambda_invoke_context_mock.template = self.template
        self.lambda_invoke_context_mock.local_lambda_runner = self.lambda_runner_mock
        self.lambda_invoke_context_mock.get_cwd = Mock()
        self.lambda_invoke_context_mock.get_cwd.return_value = self.cwd
        self.lambda_invoke_context_mock.stderr = self.stderr_mock

    @patch("samcli.commands.local.lib.local_graphql_api_service.LocalAppSyncService")
    @patch("samcli.commands.local.lib.local_graphql_api_service.GraphQLApiProvider")
    @patch.object(LocalGraphQLApiService, "_make_static_dir_path")
    @patch.object(LocalGraphQLApiService, "_print_resolvers")
    def test_must_start_service(
        self, log_routes_mock, make_static_dir_mock, GraphQLApiProviderMock, LocalAppSyncServiceMock
    ):
        resolver_list = [1, 2, 3]  # something
        resolved_path = "/foo/bar/resolved"

        GraphQLApiProviderMock.return_value = self.api_provider_mock
        LocalAppSyncServiceMock.return_value = self.appsync_service_mock
        make_static_dir_mock.return_value = resolved_path

        # Now start the service
        local_service = LocalGraphQLApiService(self.lambda_invoke_context_mock, self.port, self.host, self.static_dir)
        local_service.api_provider.api.resolvers = resolver_list
        local_service.start()

        # Make sure the right methods are called
        GraphQLApiProviderMock.assert_called_with(
            self.template, cwd=self.cwd, parameter_overrides=self.lambda_invoke_context_mock.parameter_overrides
        )

        log_routes_mock.assert_called_with(resolver_list, self.host, self.port)
        LocalAppSyncServiceMock.assert_called_with(
            api=self.api_provider_mock.api,
            lambda_runner=self.lambda_runner_mock,
            static_dir=resolved_path,
            port=self.port,
            host=self.host,
            stderr=self.stderr_mock,
        )

        self.appsync_service_mock.create.assert_called_with()
        self.appsync_service_mock.run.assert_called_with()

    @patch("samcli.commands.local.lib.local_graphql_api_service.LocalAppSyncService")
    @patch("samcli.commands.local.lib.local_graphql_api_service.GraphQLApiProvider")
    @patch.object(LocalGraphQLApiService, "_print_resolvers")
    @patch.object(GraphQLApiProvider, "_extract_api")
    def test_must_raise_if_resolvers_not_available(
        self, extract_api, log_resolvers_mock, GraphQLApiProviderMock, LocalAppSyncServiceMock
    ):
        resolver_list = []  # Empty
        api = Api()
        extract_api.return_value = api
        GraphQLApiProviderMock.extract_api.return_value = api
        GraphQLApiProviderMock.return_value = self.api_provider_mock
        LocalAppSyncServiceMock.return_value = self.appsync_service_mock

        # Now start the service
        local_service = LocalGraphQLApiService(self.lambda_invoke_context_mock, self.port, self.host, self.static_dir)
        local_service.api_provider.api.resolvers = resolver_list
        with self.assertRaises(NoApisDefined):
            local_service.start()


class TestLocalGraphQLApiService_print_routes(TestCase):
    def test_must_print_routes(self):
        host = "host"
        port = 123

        resolvers = [
            Resolver(
                function_name="fooFunctionName",
                object_type="fooObjectType",
                field_name="fooFieldName",
            ),
            Resolver(
                function_name="barFunctionName",
                object_type="barObjectType",
                field_name="barFieldName",
            ),
        ]
        expected = {
            "Resolving barObjectType.barFieldName using Lambda barFunctionName",
            "Mounting GraphQL endpoint at http://host:123/graphql [POST]",
            "Mounting GraphQL playground at http://host:123/graphql [GET]",
            "Resolving fooObjectType.fooFieldName using Lambda fooFunctionName",
        }

        actual = LocalGraphQLApiService._print_resolvers(resolvers, host, port)
        self.assertEqual(expected, set(actual))
