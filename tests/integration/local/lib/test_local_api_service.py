"""
Function test for Local API service
"""

import logging
from unittest import TestCase

from mock import Mock
from six import assertCountEqual
from samcli.local.apigw.local_apigw_service import Route

from samcli.commands.local.lib import provider
from samcli.commands.local.lib.local_api_service import LocalApiService

logging.basicConfig(level=logging.INFO)


class TestRoutingList(TestCase):

    def setUp(self):
        self.function_name = "routingTest"
        apis = [
            provider.Api(path="/get", method="GET", function_name=self.function_name, cors="cors"),
            provider.Api(path="/get", method="GET", function_name=self.function_name, cors="cors", stage_name="Dev"),
            provider.Api(path="/post", method="POST", function_name=self.function_name, cors="cors", stage_name="Prod"),
            provider.Api(path="/get", method="GET", function_name=self.function_name, cors="cors",
                         stage_variables={"test": "data"}),
            provider.Api(path="/post", method="POST", function_name=self.function_name, cors="cors", stage_name="Prod",
                         stage_variables={"data": "more data"}),
        ]
        self.api_provider_mock = Mock()
        self.api_provider_mock.get_all.return_value = apis

    def test_make_routing_list(self):
        routing_list = LocalApiService._make_routing_list(self.api_provider_mock)

        expected_routes = [
            Route(function_name=self.function_name, methods=['GET'], path='/get', stage_name='prod',
                  stage_variables=None),
            Route(function_name=self.function_name, methods=['GET'], path='/get', stage_name='Dev',
                  stage_variables=None),
            Route(function_name=self.function_name, methods=['POST'], path='/post', stage_name='Prod',
                  stage_variables=None),
            Route(function_name=self.function_name, methods=['GET'], path='/get', stage_name='prod',
                  stage_variables={'test': 'data'}),
            Route(function_name=self.function_name, methods=['POST'], path='/post', stage_name='Prod',
                  stage_variables={'data': 'more data'}),
        ]
        assertCountEqual(self, routing_list, expected_routes)
